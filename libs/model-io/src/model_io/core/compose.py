"""구조화된 값 → 모델 입력의 글 조각. 데이터셋 정본(labels.py, IO_SPEC.md 3장)의 '표 찾기'를 서빙에서 한다(ADR 0019).

LoRA-B 입력의 topic·known·ask·previous·current·hold 는 LoRA-A 출력(행동, 사유, 값, 대상)과 직전 state 에서 표와 문장
틀로 만든다.
다음 질문 문장(next.text)은 문항 은행의 문장이라 호출하는 쪽이 준다(SQL.md 7.3). 판단은 하지 않고 표에서 문장을 찾아
끼울 뿐이다.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from model_io.core import labels_port
from model_io.core.jsonvalue import as_list, as_map, as_str
from model_io.core.state import as_slot_list, next_item_of, select_state

# 왜 Any: 정본을 글자 그대로 옮긴 labels_port 는 형 표기가 없다. 형이 있는 경계는 이 파일의 두 함수다
_labels: Any = labels_port


class ModelInputError(ValueError):
    """모델 입력의 글을 만들 수 없다.

    문항·칸·값이 데이터셋 정본의 표(모델 입출력 v2)에 없다. 호출한 쪽의 요청 문제다.
    """


# 왜 이 예외들: 정본을 옮긴 표·문장 틀은 표에 없는 문항·칸이나 모양이 틀린 값에서
# KeyError 등으로 멈춘다. 서버가 죽지 않게 요청 오류로 바꾼다
_TABLE_MISS = (KeyError, ValueError, TypeError, IndexError, AttributeError)
# 계약 ActionReason(9.4.0, 모델 입출력 v3)의 값
_UNCLEAR_TARGET = "UNCLEAR_TARGET"
_LIMIT_REACHED = "LIMIT_REACHED"
_ASK_BACK = ("ASK_MEANING", "ASK_HOW")
# 왜 이 셋: 설명 요청 REDIRECT 는 직전 화면의 되묻는 내용만 이어 받는다(fix3.md 1장(2), 계약 AskBackSource)
_CARRIED = ("ask", "previous", "current")


def compose_response_input(
    a_output: Mapping[str, object],
    asked_item: str,
    utterance: str,
    state: Mapping[str, object],
    next_text: str | None,
) -> dict[str, object]:
    """LoRA-B 입력(ResponseRequest 를 JSON 으로 푼 모양).

    a_output 은 검증을 마친 LoRA-A 출력, asked_item 은 A 입력의 question_id, state 는 A 입력의 state 다.
    다음 문항이 END 이면 next_text 는 None 이다.
    """
    try:
        b = cast("dict[str, object]", _labels.b_input(dict(a_output), asked_item, utterance, dict(state), next_text))
        if a_output.get("action") == "REASK" and a_output.get("reason") == _UNCLEAR_TARGET:
            # 왜 MISSING 의 틀: 대상이 모호해 지금 문항의 칸을 모두 다시 묻는 문장은 빠진 칸을 묻는 문장과 같다
            # (dataset1118 fixaug_rules.b_input, 실측 7,491행). 재료는 state 의 값이다
            rows: dict[object, object] = {}
            for key, raw in state.items():
                entry = as_map(raw)
                if entry is not None and entry.get("value") is not None:
                    rows[_labels.parse_key(key)] = entry["value"]
            targets = [t for t in (as_list(a_output.get("targets")) or []) if isinstance(t, str)]
            b["ask"] = _labels.ask_text("MISSING", targets, rows)
        return b
    except _TABLE_MISS as error:
        raise ModelInputError("응답 입력의 문항·칸·값이 모델 입출력 표에 없다") from error


def compose_start_input(next_text: str) -> dict[str, object]:
    """문진 시작(START) 입력: 환자 말 없이 인사와 첫 문항 질문을 만든다. LoRA-A 는 부르지 않는다."""
    try:
        return cast("dict[str, object]", _labels.start_b_input(next_text))
    except _TABLE_MISS as error:
        raise ModelInputError("시작 입력을 만들 수 없다") from error


def compose_response_from_request(request: Mapping[str, object]) -> dict[str, object]:
    """응답 생성 요청(`ResponseGenerationRequest` 를 JSON 으로 푼 모양)에서 LoRA-B 모델 입력을 만든다.

    저장된 칸들에서 LoRA-A 때와 같은 규칙으로 state 를 골라(`select_state`) 이전 값·되묻는 문장의 재료로 쓴다.
    START 는 환자 말 없이 다음 문항의 topic 과 질문 문장으로 만든다.
    """
    place = as_map(request.get("next")) or {}
    next_text = as_str(place.get("text"))
    if request.get("action") == "START":
        question = as_str(place.get("question_id")) or _labels.FIRST_ITEM
        try:
            topic = _labels.topic(question)
        except _TABLE_MISS as error:
            raise ModelInputError("다음 문항이 모델 입출력 v2 의 표에 없다") from error
        return {
            "action": "START",
            "topic": topic,
            "next": {"type": "NEXT", "question_id": question, "text": next_text},
        }
    asked = as_str(request.get("question_id")) or ""
    previous = as_str(request.get("previous_question_id"))
    if request.get("reason") == _LIMIT_REACHED:
        return _limit_reached_input(asked, as_str(request.get("user_utterance")) or "", place, next_text)
    screen = as_str(request.get("previous_screen_action"))
    state = select_state(as_slot_list(request.get("slots")), asked, previous, previous_screen_action=screen)
    a_output: dict[str, object] = {
        "action": request.get("action"),
        "values": request.get("values") or [],
        "next_item": next_item_of(place),
    }
    for name in ("reason", "targets", "note"):
        if request.get(name) is not None:
            a_output[name] = request[name]
    b = compose_response_input(a_output, asked, as_str(request.get("user_utterance")) or "", state, next_text)
    source = as_map(request.get("ask_back_source"))
    if source is not None and request.get("action") == "REDIRECT" and request.get("reason") in _ASK_BACK:
        # 직전 되묻기·확인의 B 입력을 같은 규칙으로 다시 만들어 ask(·previous·current)를 이어 받는다(fix3.md 1장(2))
        carried = compose_response_from_request(
            {**source, "runtime_contract_version": request.get("runtime_contract_version")}
        )
        if carried.get("ask"):
            b["ask"] = carried["ask"]
        if carried.get("previous") is not None and carried.get("current") is not None:
            b["previous"], b["current"] = carried["previous"], carried["current"]
    return b


def _limit_reached_input(
    asked: str, utterance: str, place: Mapping[str, object], next_text: str | None
) -> dict[str, object]:
    """되묻기 한도로 넘길 때의 LoRA-B 입력(SKIP/LIMIT_REACHED). A 출력이 없다(dataset1118 fixaug.py P22, 실측 827행).

    known 은 비고, hold 는 묻던 문항 이름이다(hold_text 는 그 문항의 칸을 받아도 문항 이름을 낸다), 다음 자리는 호출하는
    쪽이 정한 자리(묻던 문항의 다음, 이번 턴 저장 값 없이)다.
    """
    try:
        return {
            "action": "SKIP",
            "reason": _LIMIT_REACHED,
            "topic": _labels.topic(asked),
            "user_utterance": utterance,
            "known": "",
            "hold": _labels.hold_text([], asked),
            "next": {"type": "NEXT", "question_id": next_item_of(place), "text": next_text},
        }
    except _TABLE_MISS as error:
        raise ModelInputError("한도 문장 입력의 문항이 모델 입출력 표에 없다") from error
