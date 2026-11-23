"""session: 세션 상태와 진행(다음 문항, 되묻기 한도, 시간 한도, 위험 정지, 종료).

입력은 세션 명령과 검증된 추출 결과, 출력은 새 세션 상태다. 모델 출력의 뜻은 다시 검사하지 않는다(R7).
저장·모델 호출은 모른다. 한도에 닿아 건너뛸 때 갈 자리는 순서표를 아는 쪽이 계산해 넘겨준다(컴포넌트는 서로 모른다).
"""

from datetime import datetime, timedelta
from uuid import UUID

from survey_service.contract.models import (
    ActionExtraction,
    ActionReason,
    BlankReason,
    ExtractionAction,
    PauseReason,
    ResponseAction,
    SessionStatus,
    ValueStatus,
)
from survey_service.types import AnswerRecord, BlankRecord, SessionRecord, SessionTransition, unwrap

END = "END"
# 왜 3: 계약 TurnFailureLimit(const 3, 사용자 결정 2026-11-11, 측정하지 않은 값). 설치마다 바꾸지 않는다고 계약이 정해
# 환경 변수·설정으로 받지 않는다(시험이 계약의 const 와 같은지 본다)
TURN_FAILURE_LIMIT = 3
ENDED = frozenset({SessionStatus.ENDED_COMPLETE, SessionStatus.ENDED_PARTIAL, SessionStatus.EXPIRED})
# 설명 요청(계약 ExplainStreakLimit, 모델 입출력 v3): 되묻기 한도에 세지 않고 따로 이어진 수를 센다
EXPLAIN_REASONS = frozenset({ActionReason.ASK_MEANING, ActionReason.ASK_HOW})


def start(
    *,
    session_id: UUID,
    device_id: str,
    subject_ref: str,
    questionnaire_id: str,
    question_set_version_id: UUID,
    runtime_contract_version: int,
    first_item_id: str,
    greeting: str,
    model_io_version: str | None,
    now: datetime,
) -> SessionRecord:
    """새 세션. 첫 문항을 묻는 중이고 화면에 보인 말은 첫 인사다."""
    return SessionRecord(
        session_id=session_id,
        device_id=device_id,
        subject_ref=subject_ref,
        questionnaire_id=questionnaire_id,
        question_set_version_id=question_set_version_id,
        runtime_contract_version=runtime_contract_version,
        status=SessionStatus.ACTIVE,
        current_item_id=first_item_id,
        asked_items=(first_item_id,),
        last_assistant_text=greeting,
        started_at=now,
        last_activity_at=now,
        model_io_version=model_io_version,
        screen_action=ResponseAction.START,
    )


def expire_if_idle(session: SessionRecord, now: datetime, idle_seconds: int) -> SessionRecord:
    """진행 중인 세션이 유휴 시간을 넘겼으면 EXPIRED 로 만든다. 멈춘 세션은 만료하지 않는다(KioskIdleResetSeconds)."""
    if session.status is SessionStatus.ACTIVE and now - session.last_activity_at >= timedelta(seconds=idle_seconds):
        return session.model_copy(update={"status": SessionStatus.EXPIRED, "ended_at": now})
    return session


def pause(session: SessionRecord, reason: PauseReason, now: datetime) -> SessionRecord:
    """위험 신호나 직원 호출로 세션을 멈춘다."""
    return session.model_copy(update={"status": SessionStatus.PAUSED, "pause_reason": reason, "last_activity_at": now})


def resume(session: SessionRecord, now: datetime) -> SessionRecord:
    """직원이 정지를 푼다. 다음 발화 턴 전까지 키오스크는 이어가는 문장을 받는다."""
    return session.model_copy(
        update={
            "status": SessionStatus.ACTIVE,
            "pause_reason": None,
            "resume_pending": True,
            "failed_turn_ids": (),  # 왜 비우나: 직원이 다시 이으면 연속 실패 수를 0 으로 되돌린다(TurnFailureLimit 2항)
            "last_activity_at": now,
        }
    )


def end(session: SessionRecord, now: datetime) -> SessionRecord:
    """환자가 끝낸다. 이미 끝난 세션은 그대로다. 문항을 모두 마치지 않았으면 부분 종료다."""
    if session.status in ENDED:
        return session
    return session.model_copy(update={"status": SessionStatus.ENDED_PARTIAL, "ended_at": now, "pause_reason": None})


def _answer_for(value_key: str, value: object, precision: str, status: str) -> AnswerRecord:
    return AnswerRecord.model_validate({"key": value_key, "value": value, "precision": precision, "status": status})


def apply_extraction(
    session: SessionRecord,
    extraction: ActionExtraction,
    *,
    skip_target: str,
    reask_limit: int,
    now: datetime,
    explain_streak_limit: int | None = None,
) -> SessionTransition:
    """검증된 추출 결과를 세션에 반영한다.

    REASK 와 CONFIRM 이 한 문항에서 reask_limit 번을 넘어 이어지면 서비스가 그 문항을 건너뛴다(빈칸 원인 REASK_LIMIT).
    건너뛰어 갈 자리(skip_target)는 호출한 쪽이 순서표로 계산해 넘긴다.
    설명 요청(REDIRECT 의 ASK_MEANING·ASK_HOW)은 되묻기 수에 세지 않고 같은 문항에서 이어진 수를 따로 센다. 그 수가
    explain_streak_limit 에 닿으면 직원 도움 안내를 붙이라고 알린다(없으면 기능이 꺼진 것, 모델 입출력 v2).
    """
    action = extraction.action
    current = session.current_item_id
    answers = dict(session.answers)
    blanks = list(session.blanks)
    for item in extraction.values.root:
        key = item.key.root
        raw = unwrap(item.value)
        if item.save.root:
            answers[key] = _answer_for(key, raw, item.precision.value, "ANSWERED")
            blanks = [b for b in blanks if b.key != key]
        elif item.status in (ValueStatus.MISSING, ValueStatus.UNCLEAR):
            # 왜 자리만 남기나: 다음 턴 모델 입력 state 에 '다시 물은 칸'(값 null)으로 실어야 한다
            answers[key] = _answer_for(key, None, "unspecified", item.status.value)
    targets = [t.root for t in extraction.targets.root] if extraction.targets is not None else []
    limit_skip = False
    next_item = extraction.next_item.root
    reask_count = session.reask_count
    if action in (ExtractionAction.REASK, ExtractionAction.CONFIRM):
        reask_count += 1
        if reask_count > reask_limit:
            limit_skip = True
            next_item = skip_target
            blanks += _blanks_for_item(current, answers, BlankReason.REASK_LIMIT)
    elif action is ExtractionAction.HOLD:
        blanks += _target_blanks(current, targets, BlankReason.UNKNOWN)
    elif action is ExtractionAction.SKIP:
        blanks += _target_blanks(current, targets, BlankReason.REJECTED)
    # 왜 REDIRECT 는 세지 않나: 문진과 상관없는 말은 되묻기가 아니다(행동별 규칙은 데이터셋 정본, IO_SPEC 1장).
    # 설명 요청(ASK_MEANING·ASK_HOW)도 REDIRECT 라 세지 않는다(계약 ReaskLimit, ModelIoFeature MEANING_ASKED_EXEMPTION).
    # UNCLEAR_TARGET 은 REASK 라 위에서 센다
    if limit_skip or action in (
        ExtractionAction.NEXT,
        ExtractionAction.CORRECT,
        ExtractionAction.HOLD,
        ExtractionAction.SKIP,
    ):
        reask_count = 0
    explaining = action is ExtractionAction.REDIRECT and extraction.reason in EXPLAIN_REASONS and next_item == current
    # 왜 이렇게 끊나: 다른 절차가 끼거나 문항이 바뀌면 '이어진' 설명 요청이 아니다(계약 ExplainStreakLimit)
    explain_streak = session.explain_streak + 1 if explaining else 0
    update: dict[str, object] = {
        "answers": answers,
        "blanks": tuple(blanks),
        "reask_count": reask_count,
        "explain_streak": explain_streak,
        # 다음 화면을 만드는 LoRA-B 요청의 절차. 한도로 건너뛰면 서비스가 SKIP 화면을 만든다
        # (고정 문장이든 LIMIT_REACHED 든)
        "screen_action": ResponseAction.SKIP if limit_skip else ResponseAction(action.value),
        "last_activity_at": now,
        "resume_pending": False,
        "failed_turn_ids": (),  # 왜 비우나: 턴이 기록되면 연속 실패 수는 0 이다(TurnFailureLimit 2항)
    }
    # 왜 한도 이상마다: 셋째 뒤에도 설명 요청이 이어지면 환자는 아직 도움이 필요하다. 안내를 한 번만 하고 거두지 않는다
    notice = explaining and explain_streak_limit is not None and explain_streak >= explain_streak_limit
    moved = _moved(session, update, current=current, next_item=next_item, now=now, limit_skip=limit_skip)
    return moved.model_copy(update={"staff_help_notice": notice}) if notice else moved


def _moved(
    session: SessionRecord,
    update: dict[str, object],
    *,
    current: str | None,
    next_item: str,
    now: datetime,
    limit_skip: bool,
) -> SessionTransition:
    """다음 자리로 옮긴 세션. 되묻기 한도 건너뛰기와 연속 실패 한도 건너뛰기가 같은 규칙을 쓴다."""
    if next_item == END:
        update.update(
            status=SessionStatus.ENDED_COMPLETE, current_item_id=None, ended_at=now, reask_count=0, explain_streak=0
        )
    else:
        update["current_item_id"] = next_item
        if next_item != current:
            update["previous_item_id"] = current
            update["reask_count"] = 0
            update["explain_streak"] = 0
            if next_item not in session.asked_items:
                update["asked_items"] = (*session.asked_items, next_item)
    return SessionTransition(
        session=session.model_copy(update=update),
        next_item_id=next_item,
        limit_skip=limit_skip,
    )


def count_failure(session: SessionRecord, turn_id: UUID) -> tuple[SessionRecord, bool]:
    """실패한 턴을 연속 실패 수에 센다(TurnFailureLimit 1항). 이미 센 turn_id 의 재전송은 다시 세지 않는다.

    호출한 쪽이 세션 행을 잠근 트랜잭션 안에서 부른다(3항, 수를 더하고 판정하는 일이 한 번에 일어난다).
    돌려주는 참거짓은 이 더함이 한도에 닿았는지다.
    """
    if turn_id in session.failed_turn_ids:
        return session, False
    ids = (*session.failed_turn_ids, turn_id)
    return session.model_copy(update={"failed_turn_ids": ids}), len(ids) >= TURN_FAILURE_LIMIT


def skip_for_failure_limit(session: SessionRecord, *, skip_target: str, now: datetime) -> SessionTransition:
    """연속 실패 한도에 닿은 턴이 지금 문항을 건너뛴다(TurnFailureLimit 4항).

    이번 턴의 값은 저장하지 않고(건너뛰어 갈 자리는 그 값 없이 호출한 쪽이 순서표로 계산해 넘긴다),
    문항에서 저장되지 않은 칸에 FAILURE_LIMIT 를 남긴다.
    """
    current = session.current_item_id
    blanks = (*session.blanks, *_blanks_for_item(current, session.answers, BlankReason.FAILURE_LIMIT))
    update: dict[str, object] = {
        "blanks": blanks,
        "reask_count": 0,
        "explain_streak": 0,
        "screen_action": ResponseAction.SKIP,  # 서비스의 고정 문장으로 건너뛴 화면
        "ask_back_source": None,  # 되묻기·확인 화면이 아니다(fix3.md 1장(2))
        "last_activity_at": now,
        "resume_pending": False,
        "failed_turn_ids": (),
    }
    return _moved(session, update, current=current, next_item=skip_target, now=now, limit_skip=False)


def _target_blanks(item_id: str | None, keys: list[str], reason: BlankReason) -> list[BlankRecord]:
    if item_id is None:
        return []
    return [BlankRecord(item_id=item_id, key=key, reason=reason) for key in keys]


def _blanks_for_item(item_id: str | None, answers: dict[str, AnswerRecord], reason: BlankReason) -> list[BlankRecord]:
    """지금 문항에서 값이 비어 있는 칸들(자리만 남은 칸). 없으면 문항 전체가 빈칸이다."""
    if item_id is None:
        return []
    keys = [key for key in answers if key.startswith(f"{item_id}.") or key.startswith(f"{item_id}[")]
    open_keys = [key for key in keys if answers[key].status != "ANSWERED"]
    if open_keys:
        return [BlankRecord(item_id=item_id, key=key, reason=reason) for key in open_keys]
    return [BlankRecord(item_id=item_id, key=None, reason=reason)]
