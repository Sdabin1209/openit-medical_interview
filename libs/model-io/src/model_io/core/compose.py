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

# 왜 Any: 정본을 글자 그대로 옮긴 labels_port 는 형 표기가 없다. 형이 있는 경계는 이 파일의 두 함수다
_labels: Any = labels_port


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
    return cast("dict[str, object]", _labels.b_input(dict(a_output), asked_item, utterance, dict(state), next_text))


def compose_start_input(next_text: str) -> dict[str, object]:
    """문진 시작(START) 입력: 환자 말 없이 인사와 첫 문항 질문을 만든다. LoRA-A 는 부르지 않는다."""
    return cast("dict[str, object]", _labels.start_b_input(next_text))
