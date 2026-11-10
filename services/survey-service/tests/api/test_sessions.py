"""세션과 턴: 시작 코드 판정, 기기 격리, 멱등, 실패 신호, 유휴 만료, 정지·재개."""

import uuid
from dataclasses import replace
from datetime import datetime, timedelta

import httpx
import pytest
from tests.support.flows import activate, idem, issue, start, turn_body
from tests.support.harness import DEADLINE, UNAVAILABLE, Harness, extraction, question_set, value, xfcc

from survey_service.components import trace
from survey_service.main import create_app

pytestmark = pytest.mark.anyio
KIOSK = xfcc("kiosk-01")
OTHER = xfcc("kiosk-02")


async def test_start_code_errors(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        invalid = await c.post("/v1/sessions", json={"start_code": "000000"}, headers=KIOSK)
        assert invalid.status_code == 422 and invalid.json()["reason"] == "START_CODE_INVALID"
        code = await issue(h, c)
        h.clock.advance(301)
        expired = await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)
        assert expired.status_code == 409 and expired.json()["reason"] == "START_CODE_EXPIRED"
        fresh = await issue(h, c)
        h.model.will_respond("안녕하세요")
        assert (await c.post("/v1/sessions", json={"start_code": fresh}, headers=KIOSK)).status_code == 201
        used = await c.post("/v1/sessions", json={"start_code": fresh}, headers=OTHER)
        assert used.status_code == 409 and used.json()["reason"] == "START_CODE_USED"


async def test_failed_attempts_are_limited_per_device(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        for _ in range(h.runtime.limits.start_failure_limit):
            assert (await c.post("/v1/sessions", json={"start_code": "000000"}, headers=KIOSK)).status_code == 422
        blocked = await c.post("/v1/sessions", json={"start_code": "000000"}, headers=KIOSK)
        assert blocked.status_code == 429 and 0 < int(blocked.headers["retry-after"]) <= 120
        assert (await c.post("/v1/sessions", json={"start_code": "000000"}, headers=OTHER)).status_code == 422


async def test_code_ttl_and_questionnaire_choice(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c, question_set("a-set", "가"))
        await activate(h, c, question_set("b-set", "나"))
        listing = await c.get("/v1/questionnaires", headers=KIOSK)
        assert {q["questionnaire_id"] for q in listing.json()["questionnaires"]} == {"a-set", "b-set"}
        code = await issue(h, c)
        # 활성 문진표가 둘 이상이면 환자가 고르는 값이 필요하다
        h.model.will_respond("안녕하세요")
        assert (await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)).status_code == 400
        chosen = await c.post("/v1/sessions", json={"start_code": code, "questionnaire_id": "b-set"}, headers=KIOSK)
        assert chosen.status_code == 201 and chosen.json()["questionnaire_id"] == "b-set"
        # 코드에 묶인 문진표가 요청보다 앞선다
        bound = await issue(h, c, questionnaire="a-set")
        h.model.will_respond("안녕하세요")
        first = await c.post("/v1/sessions", json={"start_code": bound, "questionnaire_id": "b-set"}, headers=OTHER)
        assert first.json()["questionnaire_id"] == "a-set"
        issued = await c.post("/v1/start-codes", json={"subject_ref": "s"}, headers={**h.human("staff"), **idem()})
        issued_at = datetime.fromisoformat(issued.json()["issued_at"])
        assert datetime.fromisoformat(issued.json()["expires_at"]) - issued_at == timedelta(
            seconds=300
        )  # 기본 유효 시간


async def test_idempotent_issue_and_one_time_codes(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        key = idem()
        body = {"subject_ref": "subj-9"}
        a = await c.post("/v1/start-codes", json=body, headers={**h.human("staff"), **key})
        b = await c.post("/v1/start-codes", json=body, headers={**h.human("staff"), **key})
        other = await c.post("/v1/start-codes", json=body, headers={**h.human("staff"), **idem()})
        assert a.json() == b.json() and a.json()["code"] != other.json()["code"]
        unknown = await c.post(
            "/v1/start-codes",
            json={"subject_ref": "s", "questionnaire_id": "nope"},
            headers={**h.human("staff"), **idem()},
        )
        assert unknown.status_code == 400
        missing_key = await c.post("/v1/start-codes", json=body, headers=h.human("staff"))
        assert missing_key.status_code == 400


async def test_placement_picks_default_questionnaire(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c, question_set("a-set", "가"))
        await activate(h, c, question_set("b-set", "나"))
    placed = replace(h.runtime, device_placements={"kiosk-01": "b-set"})
    app = create_app(placed, h.app.state.authenticator)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://survey-service") as c:
        code = await issue(h, c)
        h.model.will_respond("안녕하세요")
        r = await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)
        assert r.status_code == 201 and r.json()["questionnaire_id"] == "b-set"


async def test_session_is_hidden_from_other_devices(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        for method, path in (("GET", "state"), ("POST", "end"), ("POST", "staff-calls")):
            r = await c.request(method, f"/v1/sessions/{sid}/{path}", headers=OTHER)
            assert r.status_code == 404, (path, r.text)
        r = await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=OTHER)
        assert r.status_code == 404


async def test_failed_turn_leaves_session_unchanged_and_can_be_resent(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        body = turn_body("진단 받았어요")
        h.model.will_extract(UNAVAILABLE)  # 출력 불가는 같은 요청 1회 재시도 뒤 실패 신호
        h.model.will_extract(UNAVAILABLE)
        failed = await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)
        assert failed.status_code == 200 and failed.json()["failure_signal"] == "EXTRACTION_UNAVAILABLE"
        assert failed.json()["current_item_id"] == "Q1" and len(h.model.extract_requests) == 2
        state = await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)
        assert state.json()["status"] == "ACTIVE"
        # 같은 turn_id 로 다시 보내면 처음부터 다시 처리한다
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond("술은 드시나요?")
        ok = await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)
        assert ok.json()["current_item_id"] == "Q2" and "failure_signal" not in ok.json()


async def test_one_retry_succeeds_and_response_failure_signal(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        h.model.will_extract(UNAVAILABLE)  # 첫 시도 실패, 재시도 성공
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond(UNAVAILABLE)
        h.model.will_respond(UNAVAILABLE)
        failed = await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK)
        assert failed.json()["failure_signal"] == "RESPONSE_UNAVAILABLE"
        assert (await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)).json()["status"] == "ACTIVE"
        h.model.will_extract(DEADLINE)  # 시간 초과는 다시 보내지 않는다
        late = await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK)
        assert late.json()["failure_signal"] == "DEADLINE_EXCEEDED" and not h.model.extractions


async def test_same_turn_id_returns_stored_result_without_calling_model(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        body = turn_body()
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond("술은 드시나요?")
        first = await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)
        calls = len(h.model.extract_requests)
        again = await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)
        assert again.status_code == 200 and again.json() == first.json() and len(h.model.extract_requests) == calls


async def test_turn_in_progress_and_stale_processing(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        body = turn_body()
        async with h.runtime.store.transaction() as tx:
            current = await tx.get_session(uuid.UUID(sid))
            assert current is not None
            await tx.begin_turn(
                trace.begin(current, uuid.UUID(body["turn_id"]), body["utterance"], h.clock()), h.clock()
            )
        busy = await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)
        assert busy.status_code == 409 and busy.json()["reason"] == "TURN_IN_PROGRESS" and "retry-after" in busy.headers
        h.clock.advance(h.runtime.limits.turn_seconds + 1)  # 오래 멈춘 처리 중 기록은 다시 시작한다
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond("술은 드시나요?")
        assert (await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)).status_code == 200


async def test_idle_session_expires(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        h.clock.advance(59)
        assert (await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)).json()["status"] == "ACTIVE"
        h.clock.advance(2)  # 상태 읽기는 활동이 아니다: 마지막 활동에서 61초
        assert (await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)).json()["status"] == "EXPIRED"
        late = await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK)
        assert late.status_code == 409 and late.json()["reason"] == "SESSION_NOT_ACTIVE"


async def test_staff_call_pauses_and_resume_restores(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        created = await c.post(f"/v1/sessions/{sid}/staff-calls", headers=KIOSK)
        again = await c.post(f"/v1/sessions/{sid}/staff-calls", headers=KIOSK)
        assert created.status_code == 201 and again.status_code == 200 and created.json() == again.json()
        assert created.json()["kind"] == "CALL_STAFF" and created.json()["device_id"] == "kiosk-01"
        state = (await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)).json()
        assert state["status"] == "PAUSED" and state["pause_reason"] == "STAFF_CALL"
        paused = await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK)
        assert paused.status_code == 409 and paused.json()["reason"] == "SESSION_NOT_ACTIVE"
        assert [a["kind"] for a in (await c.get("/v1/staff-alerts", headers=h.human("staff"))).json()["items"]] == [
            "CALL_STAFF"
        ]
        assert (await c.get("/v1/staff-alerts", headers=h.human("clinician"))).json()["items"] == []
        ack = await c.post(f"/v1/sessions/{sid}/intervention", json={"action": "ACKNOWLEDGE"}, headers=h.human("staff"))
        assert ack.json()["status"] == "PAUSED"
        resumed = await c.post(f"/v1/sessions/{sid}/intervention", json={"action": "RESUME"}, headers=h.human("staff"))
        assert resumed.json()["status"] == "ACTIVE" and "뇌졸중" in resumed.json()["resume_text"]
        state = (await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)).json()
        assert state["status"] == "ACTIVE" and "resume_text" in state
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond("술은 드시나요?")
        assert (await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK)).status_code == 200
        assert "resume_text" not in (await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)).json()
        again = await c.post(f"/v1/sessions/{sid}/intervention", json={"action": "RESUME"}, headers=h.human("staff"))
        assert again.status_code == 200  # 멈추지 않은 세션에 다시 풀어도 같은 결과
        listed = (await c.get("/v1/staff-alerts", headers=h.human("staff"))).json()["items"]
        assert listed[0]["resolved_at"]


async def test_end_partial_and_idempotent(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        first = await c.post(f"/v1/sessions/{sid}/end", headers=KIOSK)
        h.clock.advance(5)
        second = await c.post(f"/v1/sessions/{sid}/end", headers=KIOSK)
        assert first.json()["status"] == "ENDED_PARTIAL" and first.json() == second.json()
        result = (await c.get(f"/v1/results/{sid}", headers=h.human("clinician"))).json()
        assert result["status"] == "ENDED_PARTIAL" and result["answers"] == []
        assert {b["item_id"] for b in result["blanks"]} == {"Q2", "Q2_1"} and all(
            b["reason"] == "UNASKED" for b in result["blanks"]
        )
        assert [a["kind"] for a in (await c.get("/v1/staff-alerts", headers=h.human("clinician"))).json()["items"]] == [
            "RESULT_READY"
        ]
        assert (await c.post(f"/v1/sessions/{sid}/staff-calls", headers=KIOSK)).status_code == 409


async def test_model_failure_at_start_does_not_burn_the_code(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        code = await issue(h, c)
        h.model.will_respond(UNAVAILABLE)
        h.model.will_respond(UNAVAILABLE)
        down = await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)
        assert down.status_code == 503 and "retry-after" in down.headers
        h.model.will_respond("안녕하세요")
        assert (await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)).status_code == 201


async def test_questionnaire_and_extraction_request_content(harness: Harness) -> None:
    """추출 요청에는 발화, 순서표, 칸 규격, 문항 은행 버전, 직전 화면 문장이 실린다."""
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True), value("Q1.on_medication", False)]))
        h.model.will_respond("술은 드시나요?")
        await c.post(f"/v1/sessions/{sid}/turns", json=turn_body("진단은 받았어요"), headers=KIOSK)
        req = h.model.extract_requests[0]
        assert req.runtime_contract_version.root == 1 and req.input.user_utterance.root == "진단은 받았어요"
        assert req.input.current_question.root == "안녕하세요. 먼저 질환부터 여쭤볼게요."
        assert req.flow.start_item.root == "Q1" and len(req.fields.root) == 4
        resp = h.model.respond_requests[-1].input
        assert resp.action.value == "NEXT" and resp.next.question_id is not None and resp.next.question_id.root == "Q2"
        assert resp.known is not None and "diagnosed: 예" in resp.known.root
        h.model.will_extract(extraction("NEXT", "END", [value("Q2.answer", False)]))
        h.model.will_respond("끝")
        await c.post(f"/v1/sessions/{sid}/turns", json=turn_body("안 마셔요"), headers=KIOSK)
        state_req = h.model.extract_requests[1].input.state.root
        assert {k for k in state_req} == {"Q1.diagnosed", "Q1.on_medication"}  # 직전 문항의 저장 값이 state 에 실린다
