"""LoRA-A 입력(state 포함)을 구조화된 요청 값에서 만든다. 데이터셋 정본(labels.py a_input·a_state, IO_SPEC.md 2.1,
SQL.md 7.1, prev_state.py).

state 에는 세 문항의 저장 값만 넣는다: 지금 문항, 직전에 물은 문항(대화 순서, 건너뛰기 반영: 서비스가 알려 준다), 참조
원천 문항(taxonomy 의 REF_SOURCE).
다시 묻는 중인 칸(MISSING·UNCLEAR)은 값 없이 상태만 넣는다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from model_io.core.jsonvalue import as_list, as_map, as_str
from model_io.core.slots import try_parse_slot
from model_io.core.taxonomy_port import REF_SOURCE

_REF_SOURCE: Mapping[str, str] = cast("Mapping[str, str]", REF_SOURCE)


def reference_item(question_id: str) -> str | None:
    """참조 원천 문항(정본 REF_SOURCE). 없는 문항이면 None."""
    return _REF_SOURCE.get(question_id)


def select_state(
    slots: Sequence[Mapping[str, object]],
    question_id: str,
    previous_question_id: str | None,
    *,
    previous_screen_action: str | None = None,
) -> dict[str, dict[str, object]]:
    """저장된 칸들에서 모델 입력 state 를 고른다. 키 순서가 그대로 모델 입력의 칸 순서다.

    같은 칸이 다시 나오면 값은 나중 것, 자리는 처음 자리다(labels.py a_state 가 dict 에 쓰는 규칙).
    칸의 순서(묶음 순서): 지금 문항의 확정 값, 직전 문항의 확정 값, 참조 원천 문항의 확정 값, 그리고 다시 묻는 칸들.
    학습 파일 A 입력 state 의 묶음 순서와 98.48% 일치한다(나머지는 학습 데이터가 시나리오 정보로 정한 순서, OPEN_GAPS
    G13).
    환자가 답한 화면이 확인(CONFIRM)이면 지금 문항(확인하는 문항)의 칸만 고른다(계약 9.4.0 previous_screen_action).
    """
    merged: dict[str, tuple[object, str]] = {}
    for raw in slots:
        key, status = as_str(raw.get("key")), as_str(raw.get("status"))
        if key is not None and status is not None:
            merged[key] = (raw.get("value"), status)
    wanted = [question_id, previous_question_id, reference_item(question_id)]
    if previous_screen_action == "CONFIRM":
        # 왜 확인하는 문항만: dataset1118 fixaug.py confirm_state 가 확인 다음 턴의 state 를 그 문항의 칸으로만 만든다
        # (실측 P17 4,050/4,050행). v2 데이터에는 확인 다음 턴의 행이 따로 없다
        wanted = [question_id]

    def keys(item: str | None, answered: bool) -> list[str]:
        found = [
            k
            for k, (_, s) in merged.items()
            if (s == "ANSWERED") is answered and (slot := try_parse_slot(k)) and slot[0] == item
        ]
        return found if item is not None else []

    ordered: list[str] = []
    for item in wanted:
        ordered += [k for k in keys(item, True) if k not in ordered]
    for item in wanted:
        ordered += [k for k in keys(item, False) if k not in ordered]
    # 왜 다시 묻는 칸이 마지막: 정본 prev_state.py 의 a_state(answered, pending) 가 확정 값 뒤에 다시 묻는 칸을 붙인다
    return {k: {"value": merged[k][0], "status": merged[k][1]} for k in ordered}


def compose_extraction_input(
    question_id: str,
    current_question: str,
    user_utterance: str,
    slots: Sequence[Mapping[str, object]],
    previous_question_id: str | None,
    *,
    previous_screen_action: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """LoRA-A 모델 입력의 객체(`ActionExtractionInput` 모양)와 state 의 칸 순서. 직렬화는
    `serialize_extraction_input` 이 한다."""
    state = select_state(slots, question_id, previous_question_id, previous_screen_action=previous_screen_action)
    payload: dict[str, Any] = {
        "question_id": question_id,
        "current_question": current_question,
        "user_utterance": user_utterance,
        "state": state,
    }
    return payload, list(state)


def next_item_of(next_place: Mapping[str, object]) -> str:
    """응답 요청의 next 에서 A 출력의 next_item 값(END 이면 END)."""
    if next_place.get("type") == "END":
        return "END"
    return as_str(next_place.get("question_id")) or ""


def as_slot_list(value: object) -> list[Mapping[str, object]]:
    """JSON 배열의 저장된 칸 목록을 읽는다(요청은 낸 쪽이 검증했다)."""
    items = as_list(value) or []
    return [m for item in items if (m := as_map(item)) is not None]
