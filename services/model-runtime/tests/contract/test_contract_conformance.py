"""영역의 OpenAPI 계약(contracts/openapi/model-runtime.yaml)으로 이 서비스의 FastAPI 앱을 시험한다.

Schemathesis 가 ASGI 로 앱을 직접 부른다(네트워크 없음). 계약이 정한 모든 작업에 대해 계약의 요청 스키마로
입력을 만들고, 응답의 상태 코드·내용 형식·헤더·본문이 계약과 맞는지 본다. 앱 셋을 시험한다:
- 활성 패키지가 적재된 앱, 적재 전의 앱(503 MODEL_NOT_LOADED)
- 인증 없이 부른 경우(401), 작업이 요구하는 신원으로 부른 경우(본문 검증과 도메인 오류까지 들어간다)
"""

# schemathesis 는 일부 타입이 제네릭 인자 없이 열려 있어 그 경계에서만 pyright 의 Unknown 보고를 끈다
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import pytest
import schemathesis
from fastapi import FastAPI
from hypothesis import HealthCheck, given, settings
from schemathesis import Case
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_headers_conformance,
    response_schema_conformance,
    status_code_conformance,
)

from scenario.world import World, world
from support import Identity, make_app, settings_for

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT.parents[1] / "contracts"

# 왜 not_a_server_error 를 빼나: 계약이 503 을 정의한 응답으로 둔다(준비 안 됨, 출력 불가, 엔진 실패).
# 정의된 응답은 아래 넷이 상태 코드·형식·헤더·본문을 본다
CHECKS = [status_code_conformance, content_type_conformance, response_headers_conformance, response_schema_conformance]
IDENTITY = Identity.new()


def _openapi_names() -> list[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["openit"]["contract"]
    return list(config.get("openapi", []))


async def _activate(app: FastAPI, digest: str) -> None:
    runtime = app.state.runtime
    async with app.router.lifespan_context(app):
        await runtime.activate(digest, "시험", "approver")
        await runtime.wait_idle()
        assert runtime.ready()


@pytest.fixture(scope="module")
def apps(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, FastAPI]]:
    tmp = tmp_path_factory.mktemp("conformance")
    with world(tmp) as w:
        digest = w.publish("conformance")
        yield {"not_loaded": _build(w, tmp / "cache-a"), "loaded": _loaded(w, tmp / "cache-b", digest)}


def _build(w: World, cache: Path) -> FastAPI:
    return make_app(settings_for(w.tmp, w.pki, w.registry_url, model_cache_dir=cache), w.pki, IDENTITY, w.engine)


def _loaded(w: World, cache: Path, digest: str) -> FastAPI:
    app = _build(w, cache)
    anyio.run(_activate, app, digest)
    return app


def _auth(path: str, method: str) -> dict[str, str]:
    """작업이 계약의 security 로 요구하는 신원."""
    if path in ("/v1/extractions", "/v1/responses", "/v1/model-status"):
        return {"Authorization": f"Bearer {IDENTITY.machine_token()}"}
    if path == "/v1/model-activations":
        return {"Authorization": f"Bearer {IDENTITY.token(['release-approver'])}"}
    if path.startswith("/v1/model-"):  # 롤백과 패키지 읽기는 운영자
        return {"Authorization": f"Bearer {IDENTITY.token(['operator'])}"}
    return {}


@pytest.mark.parametrize("openapi", _openapi_names())
@pytest.mark.parametrize("authenticated", [False, True], ids=["anonymous", "authenticated"])
@pytest.mark.parametrize("state", ["loaded", "not_loaded"])
def test_app_conforms_to_contract(apps: dict[str, FastAPI], openapi: str, state: str, authenticated: bool) -> None:
    schema = schemathesis.openapi.from_path(CONTRACTS / "openapi" / f"{openapi}.yaml")
    schema.app = apps[state]
    operations = [result.ok() for result in schema.get_all_operations()]  # pyright: ignore[reportAttributeAccessIssue]
    assert len(operations) == 10, "계약의 작업이 일곱 개와 건강 확인 셋이다"
    for operation in operations:
        # 왜 deadline=None, database=None: 시간 상한은 라이브러리 타이머라 시험하지 않는다.
        # 저장소에 상태 파일도 남기지 않는다
        @settings(deadline=None, max_examples=25, suppress_health_check=list(HealthCheck), database=None)  # pyright: ignore[reportArgumentType]
        @given(case=operation.as_strategy())
        def check(case: Case[Any]) -> None:
            if authenticated:
                case.headers = {**(case.headers or {}), **_auth(case.path, case.method)}  # pyright: ignore[reportAttributeAccessIssue]
            case.call_and_validate(checks=CHECKS)

        check()
