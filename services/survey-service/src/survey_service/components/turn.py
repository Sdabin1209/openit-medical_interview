"""turn: 턴 하나의 모델 요청 만들기(추출 요청, 응답 문장 요청)와 고정 문장.

입력은 발화·세션 상태·문항 세트, 출력은 model-runtime 에 보낼 계약 요청이다. 모델 호출 자체는
모른다(link_model_client 가 한다).
요청에는 구조화된 값만 싣는다: 문항 식별자, 직전 문항, 화면에 보인 질문 문장, 발화, 저장된 칸 값, 순서표, 칸
규격, A 출력의 값·칸·노트,
다음 자리와 그 질문 문장(문항 세트의 문장). 모델 입력에 들어가는 글(topic, known, ask 등)과 state 에 넣을 문항의 선택은
model-runtime 이 데이터셋 정본으로 만든다(계약 8.0.0, 영역 ADR 0013).
모델 입출력 v3(계약 9.4.0)의 화면 절차(previous_screen_action), 설명 요청이 이어 받는 원본(ask_back_source), 되묻기
한도의 문장 요청(SKIP/LIMIT_REACHED)도 여기서 만든다(영역 ADR 0020).
"""

from survey_service.contract.models import (
    ActionExtraction,
    ActionReason,
    AskBackSource,
    ExtractionAction,
    ExtractionRequest,
    QuestionSetContent,
    ResponseAction,
    ResponseGenerationRequest,
)
from survey_service.types import SessionRecord, SessionTransition, StaffHelpText

END = "END"
# 왜 344: 계약 ResponseSentence 의 maxLength(화면 문장 한 개의 상한). 고정 문장을 붙여도 넘지 않게 한다
SENTENCE_MAX = 344
# 설명 요청(계약 AskBackSource 의 조건, fix3.md 1장(1))과 그 원본이 될 수 있는 화면(fix3.md 1장(2))
_EXPLAIN = frozenset({ActionReason.ASK_MEANING, ActionReason.ASK_HOW})
_SOURCE_ACTIONS = frozenset({ResponseAction.REASK, ResponseAction.CONFIRM})
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
    if session.screen_action is not None:
        body["previous_screen_action"] = session.screen_action.value
    return ExtractionRequest.model_validate(body)


def _item_text(content: QuestionSetContent, item_id: str) -> str:
    for item in content.bank.items.root:
        if item.item_id.root == item_id:
            return item.text.root
    return item_id


def _next(content: QuestionSetContent, action: ExtractionAction, current: str, next_item: str) -> dict[str, object]:
    if action in (ExtractionAction.REASK, ExtractionAction.CONFIRM, ExtractionAction.REDIRECT):
        # 왜 next_item: 정본 labels.py b_input 은 SAME 의 문항과 문장을 A 출력의 next_item 에서 만든다. CONFIRM 은 앞
        # 문항을 확인할 수 있다(v3 실측 2,754행). END 는 계약이 SAME 절차에 허용하지 않아 묻던 문항으로 둔다
        same = next_item if next_item != END else current
        return {"type": "SAME", "question_id": same, "text": _item_text(content, same)}
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
    _common(body, session)
    if extraction.reason is not None:
        body["reason"] = extraction.reason.value
    if extraction.targets is not None:
        body["targets"] = extraction.targets.model_dump(mode="json")
    if extraction.note is not None:
        body["note"] = extraction.note.root
    explaining = extraction.action is ExtractionAction.REDIRECT and extraction.reason in _EXPLAIN
    if explaining and session.ask_back_source is not None:
        body["ask_back_source"] = session.ask_back_source.model_dump(mode="json", exclude_none=True)
    return ResponseGenerationRequest.model_validate(body)


def _common(body: dict[str, object], session: SessionRecord) -> None:
    """A 를 부를 때와 같게 싣는 칸(직전 문항, 환자가 답한 화면의 절차)."""
    if session.previous_item_id is not None:
        body["previous_question_id"] = session.previous_item_id
    if session.screen_action is not None:
        body["previous_screen_action"] = session.screen_action.value


def limit_reached_request(
    *, session: SessionRecord, content: QuestionSetContent, utterance: str, next_item_id: str
) -> ResponseGenerationRequest:
    """되묻기 한도로 문항을 넘길 때의 문장 요청(SKIP/LIMIT_REACHED, 모델 입출력 v3, dataset1118 P22).

    A 출력이 없어 values 는 비고 targets 는 없다. 다음 자리는 호출한 쪽이 정한 건너뛸 자리(END 가 아니다: 계약은 END 면
    서비스의 고정 문장을 쓰게 한다).
    """
    if session.current_item_id is None or next_item_id == END:
        raise ValueError("한도 문장은 진행 중인 문항에서 END 가 아닌 다음 문항으로 넘길 때만 만든다")
    body: dict[str, object] = {
        "runtime_contract_version": session.runtime_contract_version,
        "action": ResponseAction.SKIP.value,
        "reason": ActionReason.LIMIT_REACHED.value,
        "question_id": session.current_item_id,
        "user_utterance": utterance,
        "slots": _slots(session),
        "values": [],
        "next": {"type": "NEXT", "question_id": next_item_id, "text": _item_text(content, next_item_id)},
    }
    _common(body, session)
    return ResponseGenerationRequest.model_validate(body)


def ask_back_source_after(request: ResponseGenerationRequest | None) -> AskBackSource | None:
    """이 요청으로 만든 화면 다음의 설명 요청이 이어 받을 원본(fix3.md 1장(2), 계약 AskBackSource).

    되묻기·확인이면 그 요청 자체(반영 전 값), 설명 요청이면 그 요청이 이어 받은 것 그대로(처음 원본), 그 밖의 화면과
    서비스의 고정 문장(request 없음)이면 없다.
    """
    if request is None:
        return None
    if request.action in _SOURCE_ACTIONS:
        if request.reason is None or request.targets is None:
            # 왜: 계약은 REASK·CONFIRM 에 reason·targets 를 요구하지만 생성 타입은 조건부 규칙을 검사하지 않는다.
            # 원본이 될 수 없는 요청 때문에 턴이 깨지지 않게 이어 받지 않는다(설명 요청은 원본 없이 간다)
            return None
        dumped = request.model_dump(mode="json", exclude_none=True)
        return AskBackSource.model_validate({k: v for k, v in dumped.items() if k in AskBackSource.model_fields})
    if request.action is ResponseAction.REDIRECT and request.reason in _EXPLAIN:
        return request.ask_back_source
    return None


def with_staff_help(text: str, content: QuestionSetContent, item_id: str) -> str:
    """설명 요청 연속 한도의 응답: LoRA-B 문장 뒤에 직원 도움 안내 고정 문장을 붙인다(계약 StaffHelpNotice).

    붙여서 화면 문장의 상한을 넘으면 고정 안내와 지금 문항의 질문으로 바꾼다(안내가 잘리지 않는 쪽을 고른다).
    """
    joined = f"{text} {StaffHelpText.EXPLAIN_STAFF_HELP}"
    if len(joined) <= SENTENCE_MAX:
        return joined
    return f"{StaffHelpText.EXPLAIN_STAFF_HELP} {_item_text(content, item_id)}"


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
