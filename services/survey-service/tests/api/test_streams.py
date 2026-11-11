"""응답 문장 스트림(startSessionStream, submitTurnStream): 계약 README '응답 문장 스트림' 1~9항.

가짜 model-runtime 이 조각을 내고, 시간은 시험이 쥐는 시계와 이벤트 문으로만 다룬다(실제 대기 없음).
"""

import asyncio
import uuid
from typing import Any

import httpx
import pytest
from tests.support.asgi import Call, parse_events
from tests.support.flows import activate, issue, start, turn_body
from tests.support.harness import DEADLINE, UNAVAILABLE, Harness, StreamPlan, extraction, value, xfcc

from survey_service.contract.models import SessionStartStreamEvent, TurnStreamEvent

pytestmark = pytest.mark.anyio
KIOSK = xfcc("kiosk-01")
OTHER = xfcc("kiosk-02")


async def stream(
    c: httpx.AsyncClient, path: str, body: dict[str, Any], headers: dict[str, str] = KIOSK
) -> httpx.Response:
    return await c.post(path, json=body, headers=headers)


def events_of(response: httpx.Response) -> list[tuple[str, dict[str, Any]]]:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store, no-transform"
    assert "content-encoding" not in response.headers
    return parse_events(response.content)


def turn_path(sid: str) -> str:
    return f"/v1/sessions/{sid}/turns/stream"


async def to_q2(h: Harness, c: httpx.AsyncClient, sid: str, body: dict[str, str], text: str) -> httpx.Response:
    """Q1 에 답해 Q2 로 가는 턴을 스트림으로 보낸다."""
    h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
    h.model.will_respond(text)
    return await stream(c, turn_path(sid), body)


# ------------------------------------------------------------ 조각 전달과 result


async def test_start_stream_relays_deltas_in_order_and_result_equals_json_body(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        code = await issue(h, c)
        h.model.will_respond("안녕하세요. 먼저 질환부터 여쭤볼게요.")
        r = await stream(c, "/v1/sessions/stream", {"start_code": code})
        events = events_of(r)
        kinds = [k for k, _ in events]
        assert kinds[-1] == "result" and set(kinds[:-1]) == {"delta"} and len(kinds) > 2
        pieces = [d["text"] for k, d in events if k == "delta"]
        assert "".join(pieces) == "안녕하세요. 먼저 질환부터 여쭤볼게요."
        for _, data in events:  # 모든 이벤트가 계약의 data 스키마를 만족한다
            SessionStartStreamEvent.model_validate(data)
        result = events[-1][1]["result"]
        # result 는 JSON 작업의 성공 본문과 같다: 같은 코드를 JSON 으로 다시 보내면(재생) 같은 본문이다
        again = await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)
        assert again.status_code == 200 and again.json() == result


async def test_turn_stream_relays_deltas_in_order_and_result_equals_json_body(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        body = turn_body("진단 받았어요")
        events = events_of(await to_q2(h, c, sid, body, "진단은 받으셨군요. 술은 드시나요?"))
        assert [k for k, _ in events][-1] == "result"
        assert "".join(d["text"] for k, d in events if k == "delta") == "진단은 받으셨군요. 술은 드시나요?"
        for _, data in events:
            TurnStreamEvent.model_validate(data)
        result = events[-1][1]["result"]
        assert result["response_text"] == "진단은 받으셨군요. 술은 드시나요?" and result["current_item_id"] == "Q2"
        json_replay = await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)
        assert json_replay.json() == result


async def test_deltas_are_relayed_before_the_sentence_is_complete(harness: Harness) -> None:
    """모아 두었다 한꺼번에 보내지 않는다: 모델이 멈춘 동안에도 이미 낸 조각이 연결에 나와 있다."""
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
    hold = asyncio.Event()
    plan = StreamPlan(["술은 ", "드시나요?"], hold=hold)
    h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
    h.model.will_respond(plan)
    call = Call(h.app, turn_path(sid), turn_body(), KIOSK)
    headers = await call.open()
    assert call.status == 200 and headers["cache-control"] == "no-store, no-transform"
    first = await call.chunk()
    assert first is not None and parse_events(first)[0][1]["text"] == "술은 "
    assert plan.reached.is_set() and not hold.is_set()  # 문장은 아직 끝나지 않았다
    hold.set()
    rest = b""
    while (piece := await call.chunk()) is not None:
        rest += piece
    last = parse_events(rest)
    assert [k for k, _ in last] == ["delta", "result"] and last[-1][1]["result"]["response_text"] == "술은 드시나요?"
    await call.finish()


# ------------------------------------------------------------ 받아들이기 전의 실패는 JSON 상태 코드


async def test_refusals_before_the_stream_use_json_status_codes(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        invalid = await stream(c, "/v1/sessions/stream", {"start_code": "000000"})
        assert invalid.status_code == 422 and invalid.json()["reason"] == "START_CODE_INVALID"
        assert invalid.headers["content-type"].startswith("application/problem+json")
        bad = await stream(c, "/v1/sessions/stream", {"start_code": "x"})
        assert bad.status_code == 400
        sid = await start(h, c)
        assert (await stream(c, turn_path(sid), turn_body(), OTHER)).status_code == 404
        assert (await stream(c, turn_path(str(uuid.uuid4())), turn_body())).status_code == 404
        assert (await stream(c, turn_path(sid), {"turn_id": "x"})).status_code == 400
        h.clock.advance(61)  # 유휴 만료
        expired = await stream(c, turn_path(sid), turn_body())
        assert expired.status_code == 409 and expired.json()["reason"] == "SESSION_NOT_ACTIVE"
        assert "retry-after" in expired.headers


# ------------------------------------------------------------ LoRA-B 실패 (D86)


@pytest.mark.parametrize(
    ("failure", "signal"), [(UNAVAILABLE, "RESPONSE_UNAVAILABLE"), (DEADLINE, "DEADLINE_EXCEEDED")]
)
async def test_turn_stream_failing_after_deltas_ends_with_failure_signal_and_records_nothing(
    harness: Harness, failure: Any, signal: str
) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        body = turn_body("진단 받았어요")
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond(StreamPlan(["술은 ", "드시"], fail=failure))
        before = len(h.model.respond_requests)
        events = events_of(await stream(c, turn_path(sid), body))
        assert [k for k, _ in events] == ["delta", "delta", "result"]  # 조각을 보낸 뒤라도 result 로 끝난다
        result = events[-1][1]["result"]
        assert (
            result["failure_signal"] == signal and "response_text" not in result and result["current_item_id"] == "Q1"
        )
        # 조각을 이미 흘렸으므로 다시 보내지 않는다(글이 섞인다)
        assert len(h.model.respond_requests) == before + 1
        state = await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)
        assert state.json()["status"] == "ACTIVE"
        # 기록하지 않았다: 같은 turn_id 를 다시 보내면 재생이 아니라 다시 처리한다
        again = events_of(await to_q2(h, c, sid, body, "술은 드시나요?"))
        assert again[0][0] == "delta" and again[-1][1]["result"]["current_item_id"] == "Q2"


async def test_failure_before_any_delta_is_retried_once_like_the_json_operation(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond(UNAVAILABLE)
        h.model.will_respond("술은 드시나요?")
        events = events_of(await stream(c, turn_path(sid), turn_body()))
        assert events[-1][1]["result"]["response_text"] == "술은 드시나요?"
        assert "".join(d["text"] for k, d in events if k == "delta") == "술은 드시나요?"


# ------------------------------------------------------------ 시작 되돌리기


async def test_start_stream_failure_leaves_nothing_and_ends_with_error(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        code = await issue(h, c)
        h.model.will_respond(StreamPlan(["안녕", "하세"], fail=UNAVAILABLE))
        events = events_of(await stream(c, "/v1/sessions/stream", {"start_code": code}))
        assert [k for k, _ in events] == ["delta", "delta", "error"]
        error = events[-1][1]
        assert error["problem"]["status"] == 503 and error["problem"]["reason"] == "DEADLINE_EXCEEDED"
        assert error["retry_after_seconds"] == h.runtime.limits.retry_after_seconds
        # 아무것도 남지 않았다: 코드는 쓰이지 않았고 처리 중 표시도 없어 같은 코드로 처음부터 다시 만든다
        h.model.will_respond("안녕하세요")
        retried = events_of(await stream(c, "/v1/sessions/stream", {"start_code": code}))
        assert retried[-1][0] == "result" and retried[-1][1]["result"]["status"] == "ACTIVE"


# ------------------------------------------------------------ 재생은 조각이 없다


async def test_replays_and_turns_without_lora_b_are_a_single_result(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        code = await issue(h, c)
        h.model.will_respond("안녕하세요")
        first = events_of(await stream(c, "/v1/sessions/stream", {"start_code": code}))
        calls = len(h.model.respond_requests)
        replay = events_of(await stream(c, "/v1/sessions/stream", {"start_code": code}))
        assert [k for k, _ in replay] == ["result"] and replay[0][1]["result"] == first[-1][1]["result"]
        assert len(h.model.respond_requests) == calls
        sid = first[-1][1]["result"]["session_id"]
        # 기록한 턴의 재전송
        body = turn_body()
        recorded = events_of(await to_q2(h, c, sid, body, "술은 드시나요?"))
        calls = len(h.model.respond_requests)
        again = events_of(await stream(c, turn_path(sid), body))
        assert [k for k, _ in again] == ["result"] and again[0][1]["result"] == recorded[-1][1]["result"]
        assert len(h.model.respond_requests) == calls
        # LoRA-A 가 값을 만들지 못한 턴은 LoRA-B 를 부르지 않는다
        h.model.will_extract(UNAVAILABLE)
        h.model.will_extract(UNAVAILABLE)
        none = events_of(await stream(c, turn_path(sid), turn_body()))
        assert [k for k, _ in none] == ["result"] and none[0][1]["result"]["failure_signal"] == "EXTRACTION_UNAVAILABLE"
        assert len(h.model.respond_requests) == calls


async def test_reask_limit_skip_is_a_single_result_with_the_fixed_sentence(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        for n in range(h.runtime.limits.reask_limit):
            h.model.will_extract(extraction("REASK", "Q1", [value("Q1.diagnosed", None, "UNCLEAR")]))
            h.model.will_respond(f"다시 여쭤볼게요 {n}")
            assert events_of(await stream(c, turn_path(sid), turn_body("음")))[-1][0] == "result"
        calls = len(h.model.respond_requests)
        h.model.will_extract(extraction("REASK", "Q1", [value("Q1.diagnosed", None, "UNCLEAR")]))
        skipped = events_of(await stream(c, turn_path(sid), turn_body("음")))
        assert [k for k, _ in skipped] == ["result"] and len(h.model.respond_requests) == calls
        assert skipped[0][1]["result"]["response_text"]


# ------------------------------------------------------------ 끊겨도 끝까지, 재전송


async def test_turn_continues_after_disconnect_and_retransmit_is_409_then_replay(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
    body = turn_body("진단 받았어요")
    hold = asyncio.Event()
    plan = StreamPlan(["술은 ", "드시나요?"], hold=hold)
    h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
    h.model.will_respond(plan)
    call = Call(h.app, turn_path(sid), body, KIOSK)
    await call.open()
    assert await call.chunk() is not None  # 첫 조각을 받고
    call.disconnect()  # 키오스크가 끊는다
    await call.finish()
    async with h.client() as c:
        busy = await stream(c, turn_path(sid), body)  # 처리는 아직 끝나지 않았다
        assert busy.status_code == 409 and busy.json()["reason"] == "TURN_IN_PROGRESS" and "retry-after" in busy.headers
        hold.set()
        await h.app.state.background.drain()  # 끊긴 요청의 처리가 끝까지 간다
        replay = events_of(await stream(c, turn_path(sid), body))
        assert [k for k, _ in replay] == ["result"]
        assert replay[0][1]["result"]["response_text"] == "술은 드시나요?"
        state = await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)
        assert state.json()["status"] == "ACTIVE"
    assert len(h.model.respond_requests) == 2  # 시작 인사 하나와 이 턴 하나뿐이다


async def test_start_continues_after_disconnect_and_retransmit_is_409_then_replay(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        code = await issue(h, c)
    hold = asyncio.Event()
    plan = StreamPlan(["안녕", "하세요"], hold=hold)
    h.model.will_respond(plan)
    call = Call(h.app, "/v1/sessions/stream", {"start_code": code}, KIOSK)
    await call.open()
    assert await call.chunk() is not None
    call.disconnect()
    await call.finish()
    async with h.client() as c:
        for path in ("/v1/sessions/stream", "/v1/sessions"):  # JSON 작업도 같은 규칙이다
            busy = await c.post(path, json={"start_code": code}, headers=KIOSK)
            assert busy.status_code == 409 and busy.json()["reason"] == "SESSION_START_IN_PROGRESS", path
            assert "retry-after" in busy.headers
        hold.set()
        await h.app.state.background.drain()
        replay = events_of(await stream(c, "/v1/sessions/stream", {"start_code": code}))
        assert [k for k, _ in replay] == ["result"] and replay[0][1]["result"]["response_text"] == "안녕하세요"
        json_replay = await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)
        assert json_replay.status_code == 200 and json_replay.json() == replay[0][1]["result"]


async def test_stuck_start_mark_is_taken_over_after_the_deadline(harness: Harness) -> None:
    """프로세스가 죽어 남은 처리 중 표시는 마감(SurveyTurnLimitSeconds)이 지나면 넘겨받는다(턴의 PROCESSING 과 같다)."""
    h = harness
    async with h.client() as c:
        await activate(h, c)
        code = await issue(h, c)
        async with h.runtime.store.transaction() as tx:
            assert await tx.begin_start_attempt("kiosk-01", code, h.clock(), h.clock())
        busy = await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)
        assert busy.status_code == 409 and busy.json()["reason"] == "SESSION_START_IN_PROGRESS"
        h.clock.advance(h.runtime.limits.turn_seconds + 1)
        h.model.will_respond("안녕하세요")
        assert (await c.post("/v1/sessions", json={"start_code": code}, headers=KIOSK)).status_code == 201
