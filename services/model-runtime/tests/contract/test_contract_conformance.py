"""영역의 OpenAPI 계약(contracts/openapi/<이름>.yaml)으로 이 서비스의 FastAPI 앱을 시험한다.

Schemathesis 가 ASGI 로 앱을 직접 부른다(네트워크 없음). 계약이 정한 모든 작업에 대해 계약의 요청 스키마로
입력을 만들고, 응답의 상태 코드·내용 형식·헤더·본문이 계약과 맞는지 본다.
"""

# schemathesis 는 일부 타입이 제네릭 인자 없이 열려 있어 그 경계에서만 pyright 의 Unknown 보고를 끈다
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import tomllib
from pathlib import Path
from typing import Any

import pytest
import schemathesis
from hypothesis import HealthCheck, given, settings
from schemathesis import Case
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_headers_conformance,
    response_schema_conformance,
    status_code_conformance,
)

from model_runtime.main import Settings, create_app

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT.parents[1] / "contracts"

# 왜 not_a_server_error 를 빼나: 계약이 503(준비 안 됨)을 정의한 응답으로 둔다.
# 정의된 응답은 아래 넷이 상태 코드·형식·헤더·본문을 본다
CHECKS = [
    status_code_conformance,
    content_type_conformance,
    response_headers_conformance,
    response_schema_conformance,
]


def _openapi_names() -> list[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["openit"]["contract"]
    return list(config.get("openapi", []))


async def _down() -> bool:
    return False


# 왜 앱 둘: 준비된 앱(200)과 준비되지 않은 앱(503)의 응답을 둘 다 계약으로 본다
APPS = {"ready": create_app(Settings()), "not_ready": create_app(Settings(), {"database": _down})}


@pytest.mark.parametrize("openapi", _openapi_names())
@pytest.mark.parametrize("state", sorted(APPS))
def test_app_conforms_to_contract(openapi: str, state: str) -> None:
    schema = schemathesis.openapi.from_path(CONTRACTS / "openapi" / f"{openapi}.yaml")
    schema.app = APPS[state]
    operations = [result.ok() for result in schema.get_all_operations()]  # pyright: ignore[reportAttributeAccessIssue]
    assert operations, "계약에 작업이 없다"
    for operation in operations:

        # 왜 deadline=None, database=None: 시간 상한은 라이브러리 타이머라 시험하지 않는다.
        # 저장소에 상태 파일도 남기지 않는다
        @settings(
            deadline=None,
            max_examples=25,
            suppress_health_check=list(HealthCheck),  # pyright: ignore[reportArgumentType]
            database=None,
        )
        @given(case=operation.as_strategy())
        def check(case: Case[Any]) -> None:
            case.call_and_validate(checks=CHECKS)

        check()
