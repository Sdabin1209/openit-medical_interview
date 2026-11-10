"""responder: LoRA-B 가 낸 응답 문장을 검증한다. 환자에게 보일 글이므로 비었거나 길거나 JSON 으로 감싼 출력은 쓰지
않는다."""

from __future__ import annotations

import json
import unicodedata

from pydantic import ValidationError

from model_runtime.contract.models import ResponseSentence
from model_runtime.types import ServiceFault


def validate_sentence(raw: str) -> str:
    """모델이 낸 글자를 응답 문장으로 낸다. 어긋나면 503(값을 지어내지 않는다, D74)."""
    text = raw.strip()
    try:
        sentence = ResponseSentence.model_validate(
            text
        )  # 왜 계약 값: 길이 제약(1~344자)의 정본은 계약 ResponseSentence 다
    except ValidationError as error:
        raise _unusable("모델이 낸 문장이 계약의 길이 제약(1자 이상 344자 이하)을 지키지 않았다") from error
    if any(unicodedata.category(char) == "Cc" and char not in "\n\t" for char in text):
        raise _unusable("모델이 낸 문장에 제어 문자가 있다")
    try:
        wrapped = isinstance(json.loads(text), dict | list)
    except ValueError:
        wrapped = False
    if wrapped:
        raise _unusable("모델이 응답 문장을 JSON 으로 감싸 냈다")
    return sentence.root


def _unusable(detail: str) -> ServiceFault:
    return ServiceFault(503, "모델이 쓸 수 있는 응답 문장을 내지 못했다", detail, retry_after=5)
