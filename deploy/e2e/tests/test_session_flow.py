"""⑤ 세션 단계의 연속 실패 한도(계약 9.3.0 TurnFailureLimit) 판정: 서비스를 흉내 내는 정해진 응답으로 시험한다(네트워크 없음).

가짜 서비스는 계약의 규칙(서로 다른 turn_id 마다 연속 실패 +1, 재전송은 세지 않음, 한도에 닿으면 건너뜀)을 그대로 따른다. 버그를 심은 변형(재전송을 세는 서비스 등)으로 단계가 실패하는지도 본다.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from openit_e2e import scenario
from openit_e2e.contract import Contract, StepFailure
from openit_e2e.sse import StreamOutcome

REPO = Path(__file__).resolve().parents[3]
CONTRACT = Contract(REPO / "contracts")
ITEMS = ["Q1.D01", "Q1.D02", "Q1.D03", "Q1.D04", "Q1.D05", "Q1.D06", "Q1.D07", "Q1.D08"]
FIXED = "다음 질문으로 넘어가겠습니다."  # 가짜 서비스의 고정 안내 문장. 시험은 이 글을 비교하지 않는다


class FakeService:
    """한 세션. count_resend 가 참이면 재전송도 세는 잘못된 서비스, never_skip 이 참이면 한도에서도 실패 신호를 내는 잘못된 서비스다."""

    def __init__(
        self, *, count_resend: bool = False, never_skip: bool = False, empty_sentence: bool = False, stay_on_skip: bool = False
    ) -> None:
        self.index = 0
        self.streak = 0
        self.seen: set[str] = set()
        self.recorded: dict[str, dict[str, Any]] = {}
        self.count_resend, self.never_skip, self.empty_sentence, self.stay_on_skip = count_resend, never_skip, empty_sentence, stay_on_skip
        self.blanks: list[dict[str, Any]] = []

    @property
    def item(self) -> str:
        return ITEMS[self.index]

    def turn(self, turn_id: str) -> dict[str, Any]:
        if turn_id in self.recorded:
            return self.recorded[turn_id]
        if turn_id not in self.seen or self.count_resend:
            self.streak += 1
        self.seen.add(turn_id)
        if self.streak >= 3 and not self.never_skip:
            self.blanks.append({"item_id": self.item, "key": f"{self.item}.diagnosed", "reason": "FAILURE_LIMIT"})
            if not self.stay_on_skip:
                self.index += 1
            self.streak = 0
            reply = {
                "turn_id": turn_id,
                "status": "ACTIVE",
                "response_text": "" if self.empty_sentence else FIXED,
                "current_item_id": self.item,
            }
            self.recorded[turn_id] = reply
            return reply
        return {"turn_id": turn_id, "status": "ACTIVE", "current_item_id": self.item, "failure_signal": "EXTRACTION_UNAVAILABLE"}


def make_ctx(service: FakeService, monkeypatch: pytest.MonkeyPatch, mode: str = "pipeline") -> SimpleNamespace:
    def stream(
        ctx: Any, client: Any, operation: str, label: str, checks: list[str], *, path: Any = None, body: Any = None
    ) -> dict[str, Any]:
        if operation == "startSessionStream":
            return {
                "session_id": "s",
                "status": "ACTIVE",
                "questionnaire_id": scenario.QUESTIONNAIRE_ID,
                "response_text": "안녕하세요",
                "current_item_id": service.item,
            }
        return service.turn(body["turn_id"])

    monkeypatch.setattr(scenario, "_stream_result", stream)
    monkeypatch.setattr(scenario.script, "BY_ITEM", {item: scenario.script.SCRIPT[0] for item in ITEMS})

    def call(client: Any, svc: str, operation: str, **kwargs: Any) -> SimpleNamespace:
        body = {"status": "ACTIVE"} if operation == "getSessionState" else {"status": "ENDED_PARTIAL"}
        return SimpleNamespace(body=body, status=200)

    return SimpleNamespace(
        contract=CONTRACT,
        mode=mode,
        kiosk=lambda: None,
        call=call,
        start_code="123456",
        session_id="",
        questionnaire=SimpleNamespace(flow={"start_item": ITEMS[0]}),
        turn_failures=0,
        turn_successes=0,
        turn_skips=0,
        skipped=[],
        streams=[StreamOutcome(deltas=1)],
        last_status="",
        model_notes=[],
    )


def test_neutral_pipeline_skips_on_third_failure_and_repeats(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeService()
    ctx = make_ctx(service, monkeypatch)
    checks: list[str] = []
    scenario.session(ctx, checks, [])  # type: ignore[arg-type]
    assert ctx.skipped == [
        ("Q1.D01", "Q1.D02"),
        ("Q1.D02", "Q1.D03"),
    ]  # 3번째와 6번째 턴이 건너뜀: 건너뛴 뒤 수가 0 으로 돌아가 같은 모양이 되풀이된다
    assert ctx.turn_skips == 2 and ctx.turn_failures == 5  # 실패 신호 4번(1,2,4,5번째 턴) + 재전송 1번
    assert any("다시 보내도" in line and "그대로" in line for line in checks)
    assert any("건너뜀" in line and "Q1.D01 -> Q1.D02" in line for line in checks)


def test_retransmission_counted_by_service_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """재전송을 세는 서비스는 2번째 새 턴에서 건너뛴다. 그 턴은 실패 신호가 없어 ⑤에서는 성공과 같게 보이므로 ⑥의 빈칸 대조가 잡는다."""
    service = FakeService(count_resend=True)
    ctx = make_ctx(service, monkeypatch)
    scenario.session(ctx, [], [])  # type: ignore[arg-type]
    assert {source for source, _ in ctx.skipped} != {
        blank["item_id"] for blank in service.blanks
    }  # 서비스가 건너뛴 문항과 시험이 센 문항이 다르다
    with pytest.raises(StepFailure, match=r"세지 않았다|FAILURE_LIMIT 가 없다"):
        scenario.check_limit_blanks(ctx, {"blanks": service.blanks}, [])  # type: ignore[arg-type]


def test_missing_failure_limit_blank_for_a_skipped_item_is_a_failure() -> None:
    ctx = SimpleNamespace(mode="pipeline", skipped=[("Q1.D01", "Q1.D02")])
    with pytest.raises(StepFailure, match="FAILURE_LIMIT 가 없다"):
        scenario.check_limit_blanks(ctx, {"blanks": [{"item_id": "Q1.D01", "reason": "UNCLEAR"}]}, [])  # type: ignore[arg-type]


def test_product_records_a_skip_without_failing() -> None:
    ctx = SimpleNamespace(mode="product", skipped=[])
    checks: list[str] = []
    scenario.check_limit_blanks(ctx, {"blanks": [{"item_id": "Q3", "reason": "FAILURE_LIMIT"}]}, checks)  # type: ignore[arg-type]
    assert checks == ["연속 실패 한도로 건너뛴 문항 1개가 결과에 있다(실패로 보지 않음): Q3"]


def test_service_that_never_skips_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = make_ctx(FakeService(never_skip=True), monkeypatch)
    with pytest.raises(StepFailure, match="한도에 닿으면 그 문항을 건너뛴 결과"):
        scenario.session(ctx, [], [])  # type: ignore[arg-type]


def test_skip_without_sentence_or_without_moving_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(StepFailure, match="response_text"):
        scenario.session(make_ctx(FakeService(empty_sentence=True), monkeypatch), [], [])  # type: ignore[arg-type]
    with pytest.raises(StepFailure, match="건너뛰어야 하는데"):
        scenario.session(make_ctx(FakeService(stay_on_skip=True), monkeypatch), [], [])  # type: ignore[arg-type]


def test_failure_before_the_limit_must_not_move_the_item() -> None:
    ctx = SimpleNamespace(contract=CONTRACT, turn_failures=0, turn_successes=0, turn_skips=0, skipped=[])
    ledger = scenario.TurnLedger(limit=3)
    moved = {"status": "ACTIVE", "current_item_id": "Q1.D02", "failure_signal": "DEADLINE_EXCEEDED"}
    with pytest.raises(StepFailure, match="지금 문항이"):
        scenario._check_turn(ctx, "Q1.D01", moved, {}, ledger)  # type: ignore[arg-type]


def test_success_resets_the_streak() -> None:
    ctx = SimpleNamespace(contract=CONTRACT, turn_failures=0, turn_successes=0, turn_skips=0, skipped=[])
    ledger = scenario.TurnLedger(limit=3)
    failed = {"status": "ACTIVE", "current_item_id": "Q1.D01", "failure_signal": "EXTRACTION_UNAVAILABLE"}
    ok = {"status": "ACTIVE", "current_item_id": "Q1.D02", "response_text": "네"}
    for reply in (failed, ok, failed, failed):
        scenario._check_turn(ctx, "Q1.D01", reply, {}, ledger)  # type: ignore[arg-type]
    assert (ctx.turn_successes, ctx.turn_skips, ledger.streak) == (1, 0, 2)  # 성공이 수를 되돌렸으므로 뒤의 실패 둘은 아직 한도 밖이다


def test_end_of_questionnaire_skip_is_accepted() -> None:
    ctx = SimpleNamespace(contract=CONTRACT, turn_failures=0, turn_successes=0, turn_skips=0, skipped=[])
    ledger = scenario.TurnLedger(limit=3, streak=2)
    scenario._check_turn(ctx, "Q10", {"status": "ENDED_COMPLETE", "response_text": "수고하셨습니다"}, {}, ledger)  # type: ignore[arg-type]
    assert ctx.skipped == [("Q10", None)]


# ---------------------------------------------------------------- ⑥⑦ 빈칸과 FHIR
def fhir_with(code: str, link_id: str = "Q1.D01.diagnosed") -> dict[str, Any]:
    url = scenario.ABSENT_REASON_URL
    return {
        "resourceType": "QuestionnaireResponse",
        "status": "stopped",
        "item": [{"linkId": "Q1.D01", "item": [{"linkId": link_id, "extension": [{"url": url, "valueCode": code}]}]}],
    }


RESULT = {"blanks": [{"item_id": "Q1.D01", "key": "Q1.D01.diagnosed", "reason": "FAILURE_LIMIT"}, {"item_id": "Q2", "reason": "UNASKED"}]}


def test_fhir_failure_limit_blank_must_be_error() -> None:
    assert scenario.check_fhir_blanks(RESULT, fhir_with("error")) is not None
    with pytest.raises(StepFailure, match="asked-unknown"):
        scenario.check_fhir_blanks(RESULT, fhir_with("asked-unknown"))
    with pytest.raises(StepFailure, match="data-absent-reason 없음"):
        scenario.check_fhir_blanks(RESULT, {"resourceType": "QuestionnaireResponse", "status": "stopped"})


def test_fhir_check_is_silent_without_failure_limit_blanks() -> None:
    assert scenario.check_fhir_blanks({"blanks": [{"item_id": "Q2", "reason": "UNASKED"}]}, {}) is None


def test_item_level_blank_uses_item_id_as_link_id() -> None:
    result = {"blanks": [{"item_id": "Q1.D01", "reason": "FAILURE_LIMIT"}]}
    assert scenario.check_fhir_blanks(result, fhir_with("error", "Q1.D01")) is not None  # 같은 linkId 가 바깥 item 에도 있다


class LoopService:
    """모델이 확인을 되풀이하는 모양: 두 문항을 번갈아 지금 문항으로 준다(실패 신호 없음). 2026-11-23 product 실행(a_8b_1029)에서 본 Q1.D01↔Q1.D02 반복."""

    def __init__(self) -> None:
        self.count = 0

    @property
    def item(self) -> str:
        return ITEMS[0]

    def turn(self, turn_id: str) -> dict[str, Any]:
        self.count += 1
        return {"turn_id": turn_id, "status": "ACTIVE", "current_item_id": ITEMS[self.count % 2], "response_text": "확인할게요."}


def test_product_model_failure_signals_are_recorded_not_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """프레임워크 시험: product 에서 모델의 실패 신호는 모델 관찰로 남고 단계는 실패하지 않는다. 시스템 규칙(한도에서 건너뜀)은 그대로 본다."""
    service = FakeService()
    monkeypatch.setattr(scenario, "PRODUCT_TURN_GUARD", 12)  # 가짜 서비스의 문항 8개 안에서 끝낸다
    ctx = make_ctx(service, monkeypatch, mode="product")
    checks: list[str] = []
    scenario.session(ctx, checks, [])  # type: ignore[arg-type]
    assert ctx.turn_failures > 0 and ctx.skipped
    assert any("실패 신호 EXTRACTION_UNAVAILABLE" in note for note in ctx.model_notes)
    assert any(line.startswith("모델 관찰(판정 밖)") for line in checks)


def test_product_system_rule_violation_still_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """모델 관찰로 넘기는 것은 모델의 결과뿐이다: 한도에서도 실패 신호를 내는 서비스(계약 위반)는 product 에서도 실패다."""
    ctx = make_ctx(FakeService(never_skip=True), monkeypatch, mode="product")
    with pytest.raises(StepFailure, match="건너뛴 결과여야 한다"):
        scenario.session(ctx, [], [])  # type: ignore[arg-type]


def test_product_repeat_guard_stops_and_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """같은 문항이 PRODUCT_REPEAT_LIMIT 번을 넘어 돌아오면 세션을 끝내고 반복을 기록한다(상한 30턴까지 쓰지 않는다)."""
    service = LoopService()
    ctx = make_ctx(service, monkeypatch, mode="product")  # type: ignore[arg-type]
    scenario.session(ctx, [], [])  # type: ignore[arg-type]
    assert service.count == 2 * scenario.PRODUCT_REPEAT_LIMIT
    assert any("되돌아와" in note for note in ctx.model_notes)
    assert any("끝까지 가지 않았다" in note for note in ctx.model_notes)
