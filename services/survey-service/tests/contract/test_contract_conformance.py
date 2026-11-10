"""영역의 OpenAPI 계약(contracts/openapi/survey-service.yaml)으로 이 서비스의 FastAPI 앱을 시험한다.

Schemathesis 가 계약의 모든 작업에서 입력을 만들고, 앱(ASGI, 네트워크 없음)의 응답이 상태 코드·내용
형식·헤더·본문 스키마에서
계약과 맞는지 본다. 인증이 있는 작업은 작업의 security 요구에 맞는 신원(기기 헤더, 서명한 접근 토큰, 기계
토큰)을 붙여 부른다.
두 번 돈다: 식별자가 모두 모르는 값인 빈 DB 와, 실제 세션·사례·알림·문항 세트를 심어 두고 경로 식별자를 그
값으로 바꾼 DB.

streamStaffAlerts 는 끝나지 않는 응답이라 Schemathesis 가 읽을 수 없어 뺀다(tests/unit/test_stream.py 가 따로 본다).
"""

# schemathesis 는 일부 타입이 제네릭 인자 없이 열려 있어 그 경계에서만 pyright 의 Unknown 보고를 끈다
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import uuid
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

from tests.support.harness import Harness, extraction, question_set, value, xfcc

pytestmark = pytest.mark.anyio

CONTRACT = Path(__file__).resolve().parents[4] / "contracts" / "openapi" / "survey-service.yaml"
# 왜 not_a_server_error 를 빼나: 계약이 503(준비 안 됨, 처리 불가)을 정의한 응답으로 둔다. 정의된 응답은 아래 넷이 본다
CHECKS = [status_code_conformance, content_type_conformance, response_headers_conformance, response_schema_conformance]
EXCLUDED = {"streamStaffAlerts"}
EXAMPLES = 25  # 왜 25: ADR 0020 의 영역 시험 예시 수. 생성한 입력 수의 임의 값이고 측정이 아니다
PATH_KEYS = {"session_id", "case_id", "question_set_version_id"}


def auth_headers(h: Harness, security: list[dict[str, list[str]]] | None) -> dict[str, str]:
    """작업의 security 요구(대안 목록)에서 첫 대안에 맞는 신원을 만든다. 요구가 없으면 헤더 없음."""
    if not security:
        return {}
    first = security[0]
    if "device_mtls" in first:
        return xfcc("kiosk-01")
    if "machine_token" in first:
        name = {"result-reader": "hospital", "risk-detector": "risk-engine", "case-reader": "model-lab"}[
            first["machine_token"][0]
        ]
        return h.machine(name)
    return h.human(first["oidc"][0])


async def seed(h: Harness) -> dict[str, str]:
    """실제 세션·사례·알림·문항 세트를 심고 경로 식별자를 돌려준다."""
    async with h.client() as c:
        up = await c.post(
            "/v1/question-set-versions",
            json=question_set(),
            headers={**h.human("author"), "Idempotency-Key": str(uuid.uuid4())},
        )
        qsv = up.json()["question_set_version_id"]
        await c.post(f"/v1/question-set-versions/{qsv}/activation", headers=h.human("author"))
        code = (
            await c.post(
                "/v1/start-codes",
                json={"subject_ref": "subj-1"},
                headers={**h.human("staff"), "Idempotency-Key": str(uuid.uuid4())},
            )
        ).json()["code"]
        h.model.will_respond("안녕하세요")
        sid = (await c.post("/v1/sessions", json={"start_code": code}, headers=xfcc("kiosk-01"))).json()["session_id"]
        h.model.will_extract(h_unavailable())
        h.model.will_extract(h_unavailable())
        await c.post(
            f"/v1/sessions/{sid}/turns",
            json={"turn_id": str(uuid.uuid4()), "utterance": "음"},
            headers=xfcc("kiosk-01"),
        )
        await c.post(f"/v1/sessions/{sid}/staff-calls", headers=xfcc("kiosk-01"))
        h.model.will_extract(extraction("NEXT", "END", [value("Q1.diagnosed", True)]))
        return {"session_id": sid, "question_set_version_id": qsv}


def h_unavailable() -> Any:
    from tests.support.harness import UNAVAILABLE

    return UNAVAILABLE


async def seed_case(h: Harness) -> str:
    from survey_service.jobs import detect_failures

    await detect_failures(h.runtime.store, h.clock())
    async with h.client() as c:
        page = (await c.get("/v1/cases", headers=h.human("reviewer"))).json()
    return page["items"][0]["case_id"]


async def run_conformance(h: Harness, ids: dict[str, str]) -> dict[str, set[int]]:
    schema = schemathesis.openapi.from_path(CONTRACT)
    operations = [r.ok() for r in schema.get_all_operations() if r.ok().label.split()[0] != ""]
    assert len(operations) == 29  # 계약의 작업 26개 + healthz·readyz·metrics
    seen: dict[str, set[int]] = {}
    async with h.client() as client:
        for operation in operations:
            if operation.definition.raw.get("operationId") in EXCLUDED:
                continue
            security = operation.definition.raw.get("security")
            collected: list[Case[Any]] = []

            @settings(deadline=None, max_examples=EXAMPLES, suppress_health_check=list(HealthCheck), database=None)  # pyright: ignore[reportArgumentType]
            @given(case=operation.as_strategy())
            def collect(case: Case[Any]) -> None:
                collected.append(case)

            collect()
            for case in collected:
                if ids and case.path_parameters:
                    case.path_parameters = {k: ids.get(k, v) for k, v in case.path_parameters.items()}
                kwargs = case.as_transport_kwargs(base_url="https://survey-service")
                mine = auth_headers(h, security)
                # 왜 지우나: 계약의 헤더 매개변수(X-Forwarded-Client-Cert)를 Schemathesis 가 임의 값으로
                # 채운다. 신원은 우리가 정한다
                kept = {
                    k: v for k, v in (kwargs.get("headers") or {}).items() if k.lower() not in {m.lower() for m in mine}
                }
                kwargs["headers"] = {**kept, **mine}
                kwargs.pop("cookies", None)
                response = await client.request(**kwargs)
                case.validate_response(response, checks=CHECKS, transport_kwargs=kwargs)
                seen.setdefault(str(operation.definition.raw.get("operationId")), set()).add(response.status_code)
    return seen


async def test_empty_service_conforms(harness: Harness) -> None:
    seen = await run_conformance(harness, {})
    # 인증을 붙였으므로 인증 단계는 지나 계약이 정의한 본 응답(성공 또는 404·400)에 닿는다
    assert all(401 not in codes for codes in seen.values()), seen


async def test_seeded_service_conforms(harness: Harness) -> None:
    ids = await seed(harness)
    ids["case_id"] = await seed_case(harness)
    seen = await run_conformance(harness, ids)
    # 심어 둔 값이 있으면 읽기 작업은 성공 응답까지 간다(성공 본문이 계약과 맞는지 본다)
    for operation_id in (
        "listActiveQuestionnaires", "getSessionState", "listStaffAlerts", "listResults", "getResult", "getResultFhir",
        "listFailureCases", "getFailureCase", "getDeidentifiedTrace", "listQuestionSetVersions",
        "getQuestionSetVersion",
        "listFailureCaseExports", "getPushConfig", "surveyServiceHealthz",
    ):  # fmt: skip
        assert 200 in seen[operation_id], (operation_id, seen[operation_id])
