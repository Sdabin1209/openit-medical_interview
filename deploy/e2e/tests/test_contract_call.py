"""계약 호출 검증: 상태 코드와 응답 스키마를 어기면 단계가 실패한다(가짜 서버, 네트워크 없음)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from openit_e2e.contract import Contract, StepFailure

REPO = Path(__file__).resolve().parents[3]
CONTRACT = Contract(REPO / "contracts")
SESSION = "11111111-2222-4333-8444-555555555555"


def client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(base_url="https://x.invalid", transport=handler)


def test_valid_response_passes() -> None:
    answer = {"session_id": SESSION, "status": "ACTIVE"}
    http = client(httpx.MockTransport(lambda request: httpx.Response(200, json=answer)))
    reply = CONTRACT.call(http, "survey-service", "getSessionState", expect=(200,), path={"session_id": SESSION})
    assert reply.status == 200 and reply.body == answer


def test_response_that_breaks_the_schema_fails() -> None:
    http = client(httpx.MockTransport(lambda request: httpx.Response(200, json={"session_id": SESSION, "status": "NOT_A_STATUS"})))
    with pytest.raises(StepFailure, match="응답이 계약"):
        CONTRACT.call(http, "survey-service", "getSessionState", expect=(200,), path={"session_id": SESSION})


def test_missing_required_field_fails() -> None:
    http = client(httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "ACTIVE"})))
    with pytest.raises(StepFailure, match="응답이 계약"):
        CONTRACT.call(http, "survey-service", "getSessionState", expect=(200,), path={"session_id": SESSION})


def test_unexpected_status_fails_and_status_not_in_contract_fails() -> None:
    http = client(httpx.MockTransport(lambda request: httpx.Response(404, json={})))
    with pytest.raises(StepFailure, match=r"상태 404\(기대 \[200\]\)"):
        CONTRACT.call(http, "survey-service", "getSessionState", expect=(200,), path={"session_id": SESSION})
    teapot = client(httpx.MockTransport(lambda request: httpx.Response(418, json={})))
    with pytest.raises(StepFailure, match="계약에 없다"):
        CONTRACT.call(teapot, "survey-service", "getSessionState", expect=(418,), path={"session_id": SESSION})


def test_request_body_that_breaks_the_contract_is_caught_before_sending() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(201, json={})

    with pytest.raises(StepFailure, match="보내려던 요청 본문"):
        CONTRACT.call(client(httpx.MockTransport(handler)), "survey-service", "startSession", expect=(201,), body={"start_code": "12"})
    assert sent == []


def test_idempotency_key_is_sent_when_asked() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["Idempotency-Key"])
        return httpx.Response(201, json={"code": "123456", "issued_at": "2026-11-11T00:00:00Z", "expires_at": "2026-11-11T00:10:00Z"})

    CONTRACT.call(
        client(httpx.MockTransport(handler)), "survey-service", "issueStartCode", expect=(201,), body={"subject_ref": "s1"}, idempotent=True
    )
    assert len(seen) == 1 and len(seen[0]) == 36


def test_format_assertion_is_on() -> None:
    http = client(
        httpx.MockTransport(
            lambda request: httpx.Response(201, json={"code": "123456", "issued_at": "not-a-time", "expires_at": "2026-11-11T00:10:00Z"})
        )
    )
    with pytest.raises(StepFailure, match="응답이 계약"):
        CONTRACT.call(http, "survey-service", "issueStartCode", expect=(201,), body={"subject_ref": "s1"}, idempotent=True)


def test_model_load_limit_is_read_from_the_contract_time_budget() -> None:
    assert CONTRACT.integer_constant("ModelLoadLimitSeconds") == 180
    with pytest.raises(StepFailure, match="정수가 아니다"):
        CONTRACT.integer_constant("ModelLoadState")  # const 가 없는 스키마는 KeyError 가 아니라 계약 위반으로 알린다
