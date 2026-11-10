"""turn: 턴 하나의 모델 요청 만들기(추출 요청, 응답 문장 요청)와 고정 문장.

입력은 발화·세션 상태·문항 세트, 출력은 model-runtime 에 보낼 계약 요청이다. 모델 호출 자체는
모른다(link_model_client 가 한다).
요청에는 구조화된 값만 싣는다: 문항 식별자, 직전 문항, 화면에 보인 질문 문장, 발화, 저장된 칸 값, 순서표, 칸
규격, A 출력의 값·칸·노트,
다음 자리와 그 질문 문장(문항 세트의 문장). 모델 입력에 들어가는 글(topic, known, ask 등)과 state 에 넣을 문항의 선택은
model-runtime 이 데이터셋 정본으로 만든다(계약 8.0.0, 영역 ADR 0013).
"""

from survey_service.contract.models import (
    ActionExtraction,
    ExtractionAction,
    ExtractionRequest,
    QuestionSetContent,
    ResponseGenerationRequest,
)
from survey_service.types import SessionRecord, SessionTransition, StaffHelpText

END = "END"
# 왜 136: 계약 StoredSlots 의 maxItems. 이 수를 넘으면 가장 최근에 넣은 칸부터 남긴다(문항 세트 검증이 칸
# 수를 묶어 실제로는 넘기 어렵다)
SLOTS_MAX = 136


def _slots(current: SessionRecord) -> list[dict[str, object]]:
    """세션에 저장된 모든 칸 값과 다시 묻는 중인 칸. 넣은 순서가 모델 입력 state 의 칸 순서다(StoredSlots)."""
    slots: list[dict[str, object]] = [
        {"key": a.key, "value": a.value, "status": a.status} for a in current.answers.values()
    ]
    return slots[-SLOTS_MAX:]


def extraction_request(session: SessionRecord, content: QuestionSetContent, utterance: str) -> ExtractionRequest:
    """추출 요청. 이번 턴을 반영하기 전의 세션 값을 싣는다."""
    if session.current_item_id is None:
        raise ValueError("진행 중인 세션이 아니다")
    body: dict[str, object] = {
        "runtime_contract_version": session.runtime_contract_version,
        "question_id": session.current_item_id,
        "current_question": session.last_assistant_text,
        "user_utterance": utterance,
        "slots": _slots(session),
        "flow": content.flow.model_dump(mode="json", exclude_none=True),
        "fields": [
            spec.model_dump(mode="json", exclude_none=True)
            for item in content.bank.items.root
            for spec in item.fields.root
        ],
    }
    if session.previous_item_id is not None:
        body["previous_question_id"] = session.previous_item_id
    return ExtractionRequest.model_validate(body)


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
            "action": "START",
            "next": {"type": "NEXT", "question_id": first_item_id, "text": _item_text(content, first_item_id)},
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
    """응답 문장 요청. A 출력의 행동·사유·값·칸·노트를 그대로 싣고, 다음 자리의 질문 문장만 문항 세트에서 붙인다."""
    if session.current_item_id is None:
        raise ValueError("진행 중인 세션이 아니다")
    current = session.current_item_id
    body: dict[str, object] = {
        "runtime_contract_version": session.runtime_contract_version,
        "action": extraction.action.value,
        "question_id": current,
        "user_utterance": utterance,
        "slots": _slots(session),
        "values": extraction.values.model_dump(mode="json", exclude_none=True),
        "next": _next(content, extraction.action, current, transition.next_item_id),
    }
    if session.previous_item_id is not None:
        body["previous_question_id"] = session.previous_item_id
    if extraction.reason is not None:
        body["reason"] = extraction.reason.value
    if extraction.targets is not None:
        body["targets"] = extraction.targets.model_dump(mode="json")
    if extraction.note is not None:
        body["note"] = extraction.note.root
    return ResponseGenerationRequest.model_validate(body)


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
