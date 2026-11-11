"""responder: LoRA-B 가 낸 응답 문장을 검증한다. 환자에게 보일 글이므로 비었거나 길거나 JSON 으로 감싼 출력은 쓰지
않는다."""

from __future__ import annotations

import json
import unicodedata

from pydantic import ValidationError

from model_runtime.contract.models import ProblemReason, ResponseSentence
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


class SentenceStream:
    """스트림으로 보낼 조각을 이어 가며 문장의 합격 조건(계약 ResponseSentence)을 지킨다.

    조각은 바꾸지 않는다(계약 README 응답 문장 스트림 5항). 이으면 상한을 넘는 조각은 받지 않고 503 이다.
    """

    def __init__(self) -> None:
        self._text = ""

    def accept(self, fragment: str) -> str | None:
        """보낼 조각이면 그대로 돌려준다. 글자가 없는 조각은 보낼 것이 없다(ResponseDeltaText 는 1자 이상)."""
        if not fragment:
            return None
        try:
            ResponseSentence.model_validate(self._text + fragment)  # 왜 계약 값: 상한 344자의 정본은 계약이다
        except ValidationError as error:
            raise _stream_invalid("이으면 계약의 길이 상한(344자)을 넘는 조각이 왔다") from error
        self._text += fragment
        return fragment

    def finish(self) -> str:
        """끝났을 때의 문장. 비었으면 503 이다."""
        if not self._text:
            raise _stream_invalid("모델이 빈 문장을 냈다")
        return self._text


def _stream_invalid(detail: str) -> ServiceFault:
    return ServiceFault(
        503,
        "모델이 쓸 수 있는 응답 문장을 내지 못했다",
        detail,
        reason=ProblemReason.OUTPUT_INVALID,
        retry_after=5,
    )
