"""모델 입출력 v3(계약 9.4.0)의 턴: 확인의 다음 자리, previous_screen_action, ask_back_source 의 저장·이어 받기,
설명 요청 연속 한도의 직원 도움 안내, 되묻기 한도의 LIMIT_REACHED 문장. 실제 저장소(SQLite, -m postgres 면
PostgreSQL)와 가짜 model-runtime 으로 본다."""

import uuid
from dataclasses import replace
from typing import Any

import httpx
import pytest
from tests.support.asgi import parse_events
from tests.support.flows import activate, start, turn_body
from tests.support.harness import UNAVAILABLE, Harness, extraction, value, xfcc

from survey_service.contract.models import AskBackSource, ResponseGenerationRequest, TurnStreamEvent
from survey_service.main import create_app
from survey_service.store.repository import SqlStore
from survey_service.types import SessionRecord, StaffHelpText

pytestmark = pytest.mark.anyio
KIOSK = xfcc("kiosk-01")
V3 = "model-io-v3"
Q1_TEXT = "뇌졸중으로 진단받으셨거나 약을 드시나요?"
Q2_TEXT = "술을 드시나요?"
REASK = extraction(
    "REASK", "Q1", [value("Q1.diagnosed", None, "MISSING", "unspecified")], reason="MISSING", targets=["Q1.diagnosed"]
)
ASK_MEANING = extraction("REDIRECT", "Q1", [], reason="ASK_MEANING")
ASK_HOW = extraction("REDIRECT", "Q1", [], reason="ASK_HOW")
OFF_TOPIC = extraction("REDIRECT", "Q1", [], reason="OFF_TOPIC")
ANSWER_Q1 = extraction("NEXT", "Q2", [value("Q1.diagnosed", True), value("Q1.on_medication", False)])
CONFIRM_Q1 = extraction(
    "CONFIRM",
    "Q1",
    [value("Q1.diagnosed", False, "CONFLICT")],
    reason="CONFLICT_WITH_PREVIOUS",
    targets=["Q1.diagnosed"],
)


async def say(
    h: Harness, c: httpx.AsyncClient, sid: str, body: dict[str, Any], reply: str | None, *, text: str = "네"
) -> dict[str, Any]:
    h.model.will_extract(body)
    if reply is not None:
        h.model.will_respond(reply)
    r = await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(text), headers=KIOSK)
    assert r.status_code == 200, r.text
    return dict(r.json())


async def stored(h: Harness, sid: str) -> SessionRecord:
    async with h.runtime.store.transaction() as tx:
        found = await tx.get_session(uuid.UUID(sid))
    assert found is not None
    return found


def source_of(request: ResponseGenerationRequest) -> dict[str, Any]:
    """응답 생성 요청에서 AskBackSource 의 칸만 뽑은 것(이어 받을 원본의 기대값)."""
    dumped = request.model_dump(mode="json", exclude_none=True)
    return {k: v for k, v in dumped.items() if k in AskBackSource.model_fields}


def last_respond(h: Harness) -> dict[str, Any]:
    return h.model.respond_requests[-1].model_dump(mode="json", exclude_none=True)


async def test_confirm_of_an_earlier_item_asks_that_item_and_marks_the_screen(harness: Harness) -> None:
    """할 일 1·2: 확인이 앞 문항을 가리키면 B 의 SAME 은 그 문항이고, 다음 턴의 두 요청은 CONFIRM 화면이라고 알린다."""
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        await say(h, c, sid, ANSWER_Q1, "네, 술은 드시나요?")
        assert h.model.extract_requests[-1].previous_screen_action is not None
        assert h.model.extract_requests[-1].previous_screen_action.value == "START"
        assert last_respond(h)["previous_screen_action"] == "START"
        body = await say(
            h, c, sid, CONFIRM_Q1, "아까는 진단받으셨다고 하셨는데, 아니신가요?", text="아 뇌졸중은 아니에요"
        )
        assert last_respond(h)["question_id"] == "Q2" and last_respond(h)["previous_screen_action"] == "NEXT"
        assert last_respond(h)["next"] == {"type": "SAME", "question_id": "Q1", "text": Q1_TEXT}
        assert body["current_item_id"] == "Q1"
        await say(h, c, sid, extraction("CORRECT", "Q2", [value("Q1.diagnosed", False, "CORRECTION")]), "고쳤어요.")
        extract_req = h.model.extract_requests[-1].model_dump(mode="json", exclude_none=True)
        assert extract_req["question_id"] == "Q1" and extract_req["previous_screen_action"] == "CONFIRM"
        assert last_respond(h)["previous_screen_action"] == "CONFIRM"
        assert (await stored(h, sid)).screen_action is not None


async def test_ask_back_source_is_saved_carried_chained_and_cleared(harness: Harness) -> None:
    """할 일 3: 되묻기 화면의 요청(반영 전)을 DB 에 남기고, 설명 요청이 이어지면 처음 원본을 그대로 싣고,
    다른 절차로 넘어가면 지운다. 실패 턴의 재전송과 앱 재시작 뒤에도 같다."""
    h = harness
    h.model.version = V3
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        await say(h, c, sid, REASK, "진단받으신 적이 있는지 다시 여쭤볼게요.", text="글쎄요")
        original = source_of(h.model.respond_requests[-1])
        assert original["slots"] == []  # 반영 전: 이 턴이 남긴 MISSING 자리는 들어가지 않는다
        saved = await stored(h, sid)
        assert (
            saved.ask_back_source is not None
            and saved.ask_back_source.model_dump(mode="json", exclude_none=True) == original
        )
        assert [a.status for a in saved.answers.values()] == ["MISSING"]
        # 설명 요청 턴이 실패하고 같은 turn_id 로 다시 보내도 원본은 그대로다(실패한 턴은 세션을 바꾸지 않는다)
        retry = turn_body("무슨 말이에요?")
        h.model.will_extract(UNAVAILABLE)
        h.model.will_extract(UNAVAILABLE)
        failed = await c.post(f"/v1/sessions/{sid}/turns", json=retry, headers=KIOSK)
        assert failed.json()["failure_signal"] == "EXTRACTION_UNAVAILABLE"
        h.model.will_extract(ASK_MEANING)
        h.model.will_respond("뇌졸중 진단을 받으신 적이 있는지 여쭤본 거예요.")
        assert (await c.post(f"/v1/sessions/{sid}/turns", json=retry, headers=KIOSK)).status_code == 200
        assert last_respond(h)["ask_back_source"] == original
    # 앱을 새로 만들어도(새 저장소 객체, 같은 DB) 원본이 이어진다
    restarted = create_app(replace(h.runtime, store=SqlStore(h.engine)), h.app.state.authenticator)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url="https://survey-service") as c:
        await say(h, c, sid, ASK_HOW, "네, 아니요로 답하시면 돼요.", text="어떻게 말해요?")
        assert last_respond(h)["ask_back_source"] == original  # 두 번째 설명 요청도 처음 원본
        await say(h, c, sid, OFF_TOPIC, "문진으로 돌아갈게요.", text="오늘 날씨 좋네요")
        assert "ask_back_source" not in last_respond(h)
        assert (await stored(h, sid)).ask_back_source is None
        await say(h, c, sid, ASK_MEANING, "뜻을 설명드릴게요.", text="무슨 뜻이에요?")
        assert "ask_back_source" not in last_respond(h)  # 직전 화면이 다른 REDIRECT 였다


async def test_three_explain_requests_get_the_staff_help_notice(harness: Harness) -> None:
    """할 일 4: 같은 문항의 ASK_MEANING·ASK_HOW 셋째에 고정 문장을 붙이고 staff_help_notice 를 참으로 준다.
    재전송은 같은 결과, 다른 절차는 연속을 끊는다. 설명 요청은 되묻기 한도에 세지 않는다."""
    h = harness
    h.model.version = V3
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        first = await say(h, c, sid, ASK_MEANING, "진단을 받으셨는지 여쭤본 거예요.")
        second = await say(h, c, sid, ASK_HOW, "네나 아니요로 답하시면 돼요.")
        assert "staff_help_notice" not in first and "staff_help_notice" not in second
        h.model.will_extract(ASK_MEANING)
        h.model.will_respond("뇌졸중이라는 병을 진단받으셨는지예요.")
        body = turn_body("모르겠어요")
        third = (await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)).json()
        assert third["staff_help_notice"] is True and third["current_item_id"] == "Q1"
        assert third["response_text"] == f"뇌졸중이라는 병을 진단받으셨는지예요. {StaffHelpText.EXPLAIN_STAFF_HELP}"
        replay = (await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)).json()
        assert replay == third
        saved = await stored(h, sid)
        assert saved.explain_streak == 3 and saved.reask_count == 0
        await say(h, c, sid, OFF_TOPIC, "문진으로 돌아갈게요.")
        assert (await stored(h, sid)).explain_streak == 0
        again = await say(h, c, sid, ASK_MEANING, "뜻을 말씀드릴게요.")
        assert "staff_help_notice" not in again


async def test_staff_help_notice_on_the_stream_result(harness: Harness) -> None:
    h = harness
    h.model.version = V3
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        await say(h, c, sid, ASK_MEANING, "뜻은 이래요.")
        await say(h, c, sid, ASK_HOW, "이렇게 답해요.")
        h.model.will_extract(ASK_MEANING)
        h.model.will_respond("다시 말씀드리면")
        r = await c.post(f"/v1/sessions/{sid}/turns/stream", json=turn_body("네?"), headers=KIOSK)
        events = parse_events(r.content)
        assert [e for e, _ in events][-1] == "result"
        result = TurnStreamEvent.model_validate(events[-1][1]).model_dump(mode="json", exclude_none=True)
        assert "".join(d["text"] for e, d in events if e == "delta") == "다시 말씀드리면"
        assert result["result"]["staff_help_notice"] is True
        assert result["result"]["response_text"].endswith(str(StaffHelpText.EXPLAIN_STAFF_HELP))


async def test_v3_limit_skip_asks_lora_b_for_the_limit_sentence(harness: Harness) -> None:
    """할 일 5: v3 에서 되묻기 한도로 넘길 때 B 에 SKIP/LIMIT_REACHED 를 보내 문장을 받는다. 빈칸 원인은 REASK_LIMIT."""
    h = harness
    h.model.version = V3
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        await say(h, c, sid, REASK, "다시 여쭤볼게요.")
        await say(h, c, sid, REASK, "한 번 더 여쭤볼게요.")
        h.model.will_extract(REASK)
        h.model.will_respond("이 질문은 넘어갈게요. 술을 드시나요?")
        body = (await c.post(f"/v1/sessions/{sid}/turns", json=turn_body("음..."), headers=KIOSK)).json()
        assert body["response_text"] == "이 질문은 넘어갈게요. 술을 드시나요?" and body["current_item_id"] == "Q2"
        sent = last_respond(h)
        assert {k: sent[k] for k in ("action", "reason", "question_id", "user_utterance", "values", "next")} == {
            "action": "SKIP", "reason": "LIMIT_REACHED", "question_id": "Q1", "user_utterance": "음...", "values": [],
            "next": {"type": "NEXT", "question_id": "Q2", "text": Q2_TEXT},
        }  # fmt: skip
        assert "targets" not in sent and sent["previous_screen_action"] == "REASK"
        assert [(s["key"], s["status"]) for s in sent["slots"]] == [("Q1.diagnosed", "MISSING")]  # 반영 전 값
        saved = await stored(h, sid)
        assert [b.reason.value for b in saved.blanks] == ["REASK_LIMIT"] and saved.screen_action is not None
        assert saved.screen_action.value == "SKIP" and saved.ask_back_source is None


async def test_v2_or_end_keeps_the_fixed_limit_sentence(harness: Harness) -> None:
    """할 일 5: v2 이거나 다음 자리가 END 면 지금처럼 고정 문장이고 B 를 부르지 않는다."""
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        await say(h, c, sid, REASK, "다시 여쭤볼게요.")
        await say(h, c, sid, REASK, "한 번 더 여쭤볼게요.")
        calls = len(h.model.respond_requests)
        body = await say(h, c, sid, REASK, None)
        assert body["response_text"] == f"{StaffHelpText.REASK_LIMIT_SKIP} {Q2_TEXT}"
        assert len(h.model.respond_requests) == calls
        # v3 라도 끝(END)으로 넘기면 고정 문장(P22 에 END 행이 없다, 계약 ResponseGenerationRequest)
        h.model.version = V3
        await say(h, c, sid, extraction("NEXT", "Q2_1", [value("Q2.answer", True)]), "몇 잔 드시나요?")
        for reply in ("다시요.", "또요."):
            await say(h, c, sid, extraction("REASK", "Q2_1", [], reason="MISSING", targets=["Q2_1.amount"]), reply)
        calls = len(h.model.respond_requests)
        end = await say(h, c, sid, extraction("REASK", "Q2_1", [], reason="MISSING", targets=["Q2_1.amount"]), None)
        assert end["response_text"] == f"{StaffHelpText.REASK_LIMIT_SKIP} {StaffHelpText.FINISHED}"
        assert end["status"] == "ENDED_COMPLETE" and len(h.model.respond_requests) == calls


async def test_v3_limit_sentence_failure_is_a_failed_turn_and_keeps_the_session(harness: Harness) -> None:
    """할 일 5: 한도 문장을 받지 못하면 다른 LoRA-B 실패와 같이 실패 신호이고 세션(되묻기 수 포함)은 그대로다.
    연속 실패 한도 경로(고정 문장)는 바꾸지 않았다."""
    h = harness
    h.model.version = V3
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        await say(h, c, sid, REASK, "다시 여쭤볼게요.")
        await say(h, c, sid, REASK, "한 번 더 여쭤볼게요.")
        h.model.will_extract(REASK)
        h.model.will_respond(UNAVAILABLE)
        h.model.will_respond(UNAVAILABLE)
        body = (await c.post(f"/v1/sessions/{sid}/turns", json=turn_body("음..."), headers=KIOSK)).json()
        assert body["failure_signal"] == "RESPONSE_UNAVAILABLE" and body["current_item_id"] == "Q1"
        saved = await stored(h, sid)
        assert saved.reask_count == 2 and saved.blanks == () and len(saved.failed_turn_ids) == 1
