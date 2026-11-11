"""연속 턴 실패 한도(계약 TurnFailureLimit 3): 세는 단위, 초기화, 건너뛰기, 원자성, 스트림, FHIR 대응.

가짜 model-runtime 과 시험이 쥐는 시계·이벤트 문만 쓴다(실제 시간을 기다리지 않는다).
"""

import asyncio
import uuid
from typing import Any

import httpx
import pytest
from tests.support.asgi import parse_events
from tests.support.flows import activate, issue, start, turn_body
from tests.support.harness import UNAVAILABLE, Harness, StreamPlan, extraction, value, xfcc
from tests.unit.test_components import make_session

from survey_service.components import session
from survey_service.contract.models import ExtractionResult
from survey_service.types import StaffHelpText

pytestmark = pytest.mark.anyio
KIOSK = xfcc("kiosk-01")
SKIP_Q2 = f"{StaffHelpText.REASK_LIMIT_SKIP} 술을 드시나요?"
SKIP_END = f"{StaffHelpText.REASK_LIMIT_SKIP} {StaffHelpText.FINISHED}"


def events_of(response: httpx.Response) -> list[tuple[str, dict[str, Any]]]:
    assert response.status_code == 200, response.text
    return parse_events(response.content)


async def fail(h: Harness, c: httpx.AsyncClient, sid: str, body: dict[str, str] | None = None) -> dict[str, Any]:
    """추출이 출력 불가로 실패하는 턴(같은 요청 1회 재시도까지 실패)."""
    h.model.will_extract(UNAVAILABLE)
    h.model.will_extract(UNAVAILABLE)
    r = await c.post(f"/v1/sessions/{sid}/turns", json=body or turn_body(), headers=KIOSK)
    assert r.status_code == 200, r.text
    return dict(r.json())


async def failed_ids(h: Harness, sid: str) -> tuple[uuid.UUID, ...]:
    async with h.runtime.store.transaction() as tx:
        found = await tx.get_session(uuid.UUID(sid))
    assert found is not None
    return found.failed_turn_ids


async def test_success_resets_the_count(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        assert "failure_signal" in await fail(h, c, sid) and "failure_signal" in await fail(h, c, sid)
        assert len(await failed_ids(h, sid)) == 2
        h.model.will_extract(extraction("HOLD", "Q1", [], reason="UNCERTAIN", targets=["Q1.on_medication"]))
        h.model.will_respond("괜찮아요. 다시 여쭤볼게요.")
        ok = await c.post(f"/v1/sessions/{sid}/turns", json=turn_body("몰라요"), headers=KIOSK)
        assert "failure_signal" not in ok.json() and await failed_ids(h, sid) == ()
        # 성공으로 0 이 되었으니 두 번 더 실패해도 아직 건너뛰지 않는다
        assert "failure_signal" in await fail(h, c, sid) and "failure_signal" in await fail(h, c, sid)
        assert (await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)).json()["status"] == "ACTIVE"


async def test_three_consecutive_failures_skip_the_item_with_blank_reason_and_fhir_error(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        await fail(h, c, sid)
        await fail(h, c, sid)
        responds = len(h.model.respond_requests)
        third = turn_body("진단 받았어요")
        # LoRA-A 는 값을 냈고 LoRA-B 가 실패해도 그 턴의 값은 저장하지 않는다
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond(UNAVAILABLE)
        h.model.will_respond(UNAVAILABLE)
        skipped = (await c.post(f"/v1/sessions/{sid}/turns", json=third, headers=KIOSK)).json()
        assert skipped == {
            "turn_id": third["turn_id"], "status": "ACTIVE", "response_text": SKIP_Q2, "current_item_id": "Q2",
        }  # fmt: skip
        assert await failed_ids(h, sid) == ()
        # 다시 보내면 같은 결과이고 모델을 다시 부르지 않는다
        calls = (len(h.model.extract_requests), len(h.model.respond_requests))
        replay = (await c.post(f"/v1/sessions/{sid}/turns", json=third, headers=KIOSK)).json()
        assert replay == skipped and calls == (len(h.model.extract_requests), len(h.model.respond_requests))
        assert calls[1] == responds + 2  # 건너뛴 턴 안에서 응답 문장 시도 둘, 그 뒤로는 없다
        await c.post(f"/v1/sessions/{sid}/end", headers=KIOSK)
        reader = h.human("clinician")
        result = (await c.get(f"/v1/results/{sid}", headers=reader)).json()
        assert result["answers"] == []
        assert {"item_id": "Q1", "reason": "FAILURE_LIMIT"} in result["blanks"]
        fhir = (await c.get(f"/v1/results/{sid}/fhir", headers=h.machine("hospital"))).json()
        codes = [e["valueCode"] for i in fhir["item"] if i["linkId"] == "Q1" for x in i["item"] for e in x["extension"]]
        assert codes == ["error"]


async def test_retransmitting_the_same_failed_turn_is_not_counted(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        first, second = turn_body(), turn_body()
        for _ in range(3):  # 같은 turn_id 를 몇 번 다시 보내도 1 이다
            assert "failure_signal" in await fail(h, c, sid, first)
        assert await failed_ids(h, sid) == (uuid.UUID(first["turn_id"]),)
        assert "failure_signal" in await fail(h, c, sid, second)
        assert "failure_signal" in await fail(h, c, sid, first)  # A, B, A 도 2 다
        assert len(await failed_ids(h, sid)) == 2
        third = await fail(h, c, sid)
        assert third["response_text"] == SKIP_Q2


async def test_limit_on_the_last_item_ends_the_session_complete(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        for item, answer, nxt in (("Q1", "Q1.diagnosed", "Q2"), ("Q2", "Q2.answer", "Q2_1")):
            h.model.will_extract(extraction("NEXT", nxt, [value(answer, True)]))
            h.model.will_respond(f"{nxt} 질문")
            assert (await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK)).json()[
                "current_item_id"
            ] == nxt, item
        await fail(h, c, sid)
        await fail(h, c, sid)
        last = await fail(h, c, sid)
        assert last["status"] == "ENDED_COMPLETE" and last["response_text"] == SKIP_END
        assert "current_item_id" not in last
        assert (await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)).json()["status"] == "ENDED_COMPLETE"
        result = (await c.get(f"/v1/results/{sid}", headers=h.human("clinician"))).json()
        assert {"item_id": "Q2_1", "reason": "FAILURE_LIMIT"} in result["blanks"]
        alerts = (await c.get("/v1/staff-alerts", headers=h.human("clinician"))).json()["items"]
        assert [(a["kind"], a["session_id"]) for a in alerts] == [("RESULT_READY", sid)]  # 끝났으니 결과 도착 알림 하나


async def test_staff_resume_resets_the_count(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        await fail(h, c, sid)
        await fail(h, c, sid)
        assert (await c.post(f"/v1/sessions/{sid}/staff-calls", headers=KIOSK)).status_code == 201
        resumed = await c.post(f"/v1/sessions/{sid}/intervention", json={"action": "RESUME"}, headers=h.human("staff"))
        assert resumed.json()["status"] == "ACTIVE" and await failed_ids(h, sid) == ()
        assert "failure_signal" in await fail(h, c, sid) and "failure_signal" in await fail(h, c, sid)
        assert (await fail(h, c, sid))["response_text"] == SKIP_Q2


async def test_idempotent_start_replay_does_not_change_the_count(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        code = await issue(h, c)
        h.model.will_respond("안녕하세요.")
        sid = (await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)).json()["session_id"]
        await fail(h, c, sid)
        replay = await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)
        assert replay.status_code == 200 and len(await failed_ids(h, sid)) == 1


async def test_stream_limit_replaces_deltas_with_the_skip_result(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        await fail(h, c, sid)
        await fail(h, c, sid)
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond(StreamPlan(["술은 ", "드시나요?"], fail=UNAVAILABLE))  # 조각을 보낸 뒤 실패(재시도 없음)
        body = turn_body("진단 받았어요")
        events = events_of(await c.post(f"/v1/sessions/{sid}/turns/stream", json=body, headers=KIOSK))
        assert [k for k, _ in events] == ["delta", "delta", "result"]
        assert events[-1][1]["result"] == {
            "turn_id": body["turn_id"], "status": "ACTIVE", "response_text": SKIP_Q2, "current_item_id": "Q2",
        }  # fmt: skip
        replay = events_of(await c.post(f"/v1/sessions/{sid}/turns/stream", json=body, headers=KIOSK))
        assert [k for k, _ in replay] == ["result"] and replay[0][1] == events[-1][1]


async def test_overlapping_failing_turns_skip_exactly_one_item(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """수가 2 일 때 같은 세션에서 실패하는 두 턴이 겹쳐도 한도에 닿는 더함은 하나뿐이라 문항을 한 번만 건너뛴다."""
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        await fail(h, c, sid)
        await fail(h, c, sid)
        entered = 0
        both_in = asyncio.Event()

        async def gated(_request: object) -> ExtractionResult:
            nonlocal entered
            entered += 1
            if entered >= 2:  # 두 턴의 첫 호출이 모두 들어오면 풀어 준다(겹침을 보장)
                both_in.set()
            await both_in.wait()
            raise UNAVAILABLE

        monkeypatch.setattr(h.model, "extract", gated)
        results = await asyncio.gather(
            *(c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK) for _ in range(2))
        )
        bodies = [r.json() for r in results]
        assert [r.status_code for r in results] == [200, 200], bodies
        skips = [b for b in bodies if "response_text" in b]
        assert len(skips) == 1 and skips[0]["current_item_id"] == "Q2", bodies
        assert [b["failure_signal"] for b in bodies if "failure_signal" in b] == ["EXTRACTION_UNAVAILABLE"]
        async with h.runtime.store.transaction() as tx:
            final = await tx.get_session(uuid.UUID(sid))
        assert final is not None and final.current_item_id == "Q2"
        assert [b.reason.value for b in final.blanks] == ["FAILURE_LIMIT"] and len(final.failed_turn_ids) == 1


def test_count_failure_unit() -> None:
    base = make_session()
    one, two = uuid.uuid4(), uuid.uuid4()
    s1, hit1 = session.count_failure(base, one)
    s1b, hit1b = session.count_failure(s1, one)
    s2, hit2 = session.count_failure(s1, two)
    s3, hit3 = session.count_failure(s2, uuid.uuid4())
    assert (hit1, hit1b, hit2, hit3) == (False, False, False, True) and s1b is s1 and len(s3.failed_turn_ids) == 3
    assert session.TURN_FAILURE_LIMIT == 3
    assert session.resume(s2, s2.last_activity_at).failed_turn_ids == ()
