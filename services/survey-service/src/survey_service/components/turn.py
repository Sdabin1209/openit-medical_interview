"""turn: 턴 하나의 모델 요청 만들기(추출 요청, 응답 문장 요청)와 고정 문장.

입력은 발화·세션 상태·문항 세트, 출력은 model-runtime 에 보낼 계약 요청이다. 모델 호출 자체는 모른다
(link_model_client 가 한다). 모델 입력의 글 조각(topic, known, ask, previous, current, hold)은 문항 세트의 질문 문장과
칸 규격에서만 만든다. 데이터셋의 칸 설명표·문장 틀 표는 계약에 없다(변경 요청 survey-service-002).
"""

from collections.abc import Mapping

from survey_service.contract.models import (
    ActionExtraction,
    ExtractionAction,
    ExtractionRequest,
    QuestionFieldSpec,
    QuestionSetContent,
    ResponseGenerationRequest,
)
from survey_service.types import (
    AnswerRecord,
    SessionRecord,
    SessionTransition,
    SlotValue,
    StaffHelpText,
    split_slot,
    unwrap,
)

END = "END"
# 왜 이 길이들: 계약 TopicText 88, KnownText 124, AskText 92, Previous·CurrentValueText 30, HoldText 36 의 maxLength
TOPIC_MAX, KNOWN_MAX, ASK_MAX, VALUE_MAX, HOLD_MAX = 88, 124, 92, 30, 36
# 왜 18: 계약 CollectedState 의 maxProperties(학습 데이터 관측 최대 9 의 2배)
STATE_MAX = 18


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _spec_of(content: QuestionSetContent, key: str) -> QuestionFieldSpec | None:
    parts = split_slot(key)
    if parts is None:
        return None
    for item in content.bank.items.root:
        if item.item_id.root == parts[0]:
            for spec in item.fields.root:
                if spec.field_name.root == parts[2]:
                    return spec
    return None


def value_text(content: QuestionSetContent, key: str, value: SlotValue) -> str:
    """칸 값을 사람 말로. 선택지는 환자용 이름으로, 예·아니오는 예/아니오로, 수는 단위를 붙여 쓴다."""
    spec = _spec_of(content, key)
    if value is None:
        return "모름"
    if isinstance(value, bool):
        return "예" if value else "아니오"
    if isinstance(value, str):
        if spec is not None and spec.options is not None:
            for option in spec.options.root:
                if option.option_code.root == value:
                    return option.label.root
        return value
    number = str(int(value)) if float(value).is_integer() else str(value)
    unit = spec.unit.root if spec is not None and spec.unit is not None else ""
    return f"{number}{unit}"


def _label(key: str) -> str:
    parts = split_slot(key)
    return key if parts is None else parts[2].replace("_", " ")


def _entry(content: QuestionSetContent, answer: AnswerRecord) -> dict[str, object]:
    return {"value": answer.value, "status": answer.status}


def extraction_request(session: SessionRecord, content: QuestionSetContent, utterance: str) -> ExtractionRequest:
    """추출 요청. state 는 지금 문항과 직전 문항의 값(다시 물은 칸 포함)이다(IO_SPEC 2.1)."""
    if session.current_item_id is None:
        raise ValueError("진행 중인 세션이 아니다")
    wanted = {session.current_item_id, *([session.previous_item_id] if session.previous_item_id else [])}
    state: dict[str, dict[str, object]] = {}
    for key, answer in session.answers.items():
        parts = split_slot(key)
        if parts is not None and parts[0] in wanted:
            state[key] = _entry(content, answer)
    kept = list(state)[-STATE_MAX:]
    fields = [spec for item in content.bank.items.root for spec in item.fields.root]
    return ExtractionRequest.model_validate(
        {
            "runtime_contract_version": session.runtime_contract_version,
            "input": {
                "question_id": session.current_item_id,
                "current_question": session.last_assistant_text,
                "user_utterance": utterance,
                "state": {key: state[key] for key in kept},
            },
            "state_key_order": kept,
            "flow": content.flow.model_dump(mode="json", exclude_none=True),
            "fields": [spec.model_dump(mode="json", exclude_none=True) for spec in fields],
        }
    )


def _item_text(content: QuestionSetContent, item_id: str) -> str:
    for item in content.bank.items.root:
        if item.item_id.root == item_id:
            return item.text.root
    return item_id


def _next(content: QuestionSetContent, action: ExtractionAction, current: str, next_item: str) -> dict[str, object]:
    if action in (ExtractionAction.REASK, ExtractionAction.CONFIRM, ExtractionAction.REDIRECT):
        return {"type": "SAME", "question_id": current, "text": _item_text(content, current)}
    if next_item == END:
        return {"type": "END"}
    return {"type": "NEXT", "question_id": next_item, "text": _item_text(content, next_item)}


def start_response_request(
    content: QuestionSetContent, first_item_id: str, runtime_contract_version: int
) -> ResponseGenerationRequest:
    """문진 시작 인사 요청(START). LoRA-A 를 거치지 않는다(IO_SPEC 5.1)."""
    return ResponseGenerationRequest.model_validate(
        {
            "runtime_contract_version": runtime_contract_version,
            "input": {
                "action": "START",
                "topic": _clip(_item_text(content, first_item_id), TOPIC_MAX),
                "next": {"type": "NEXT", "question_id": first_item_id, "text": _item_text(content, first_item_id)},
            },
        }
    )


def response_request(
    *,
    session: SessionRecord,
    content: QuestionSetContent,
    extraction: ActionExtraction,
    transition: SessionTransition,
    utterance: str,
) -> ResponseGenerationRequest:
    """응답 문장 요청. 값은 문항 세트의 문장과 칸 규격에서만 만든다(모델 호출 없음, IO_SPEC 3장)."""
    if session.current_item_id is None:
        raise ValueError("진행 중인 세션이 아니다")
    action = extraction.action
    current = session.current_item_id
    new_answers: Mapping[str, AnswerRecord] = transition.session.answers
    known = ", ".join(f"{_label(k)}: {value_text(content, k, new_answers[k].value)}" for k in transition.saved_keys)
    targets = [t.root for t in extraction.targets.root] if extraction.targets is not None else []
    body: dict[str, object] = {
        "action": action.value,
        "topic": _clip(_item_text(content, current), TOPIC_MAX),
        "user_utterance": utterance,
        "known": _clip(known, KNOWN_MAX),
        "next": _next(content, action, current, transition.next_item_id),
    }
    if extraction.reason is not None:
        body["reason"] = extraction.reason.value
    if action in (ExtractionAction.REASK, ExtractionAction.CONFIRM):
        body["ask"] = _clip(_item_text(content, current), ASK_MAX)
    if action is ExtractionAction.CONFIRM:
        key = targets[0] if targets else next((v.key.root for v in extraction.values.root), "")
        old = transition.previous_answers.get(key)
        new = next((v for v in extraction.values.root if v.key.root == key), None)
        body["previous"] = _clip(value_text(content, key, old.value if old else None), VALUE_MAX)
        raw = None if new is None else unwrap(new.value)
        body["current"] = _clip(value_text(content, key, raw), VALUE_MAX)
    if action in (ExtractionAction.HOLD, ExtractionAction.SKIP):
        names = ", ".join(_label(t) for t in targets) or _item_text(content, current)
        body["hold"] = _clip(names, HOLD_MAX)
    if extraction.note is not None:
        body["note"] = extraction.note.root
    return ResponseGenerationRequest.model_validate(
        {"runtime_contract_version": session.runtime_contract_version, "input": body}
    )


def limit_skip_text(content: QuestionSetContent, next_item_id: str) -> str:
    """되묻기 한도로 건너뛸 때 환자에게 보일 고정 문장과 다음 질문(모델이 쓰지 않는다)."""
    if next_item_id == END:
        return f"{StaffHelpText.REASK_LIMIT_SKIP} {StaffHelpText.FINISHED}"
    return f"{StaffHelpText.REASK_LIMIT_SKIP} {_item_text(content, next_item_id)}"


def resume_text(content: QuestionSetContent, current_item_id: str | None) -> str:
    """정지가 풀린 뒤 다음 발화 턴 전까지 보일 문장(직전 질문을 다시 묻는다)."""
    if current_item_id is None:
        return str(StaffHelpText.RESUMED)
    return f"{StaffHelpText.RESUMED} {_item_text(content, current_item_id)}"
