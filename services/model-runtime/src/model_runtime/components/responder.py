"""responder: LoRA-B 가 낸 응답 문장의 받아들이는 조건은 계약 ResponseSentence 가 정한다(D117). 이 컴포넌트는 그
모델로 가리고 어긋나면 503 으로 바꾼다."""

from __future__ import annotations

import unicodedata

from pydantic import ValidationError

from model_runtime.contract.models import ProblemReason, ResponseSentence
from model_runtime.types import ServiceFault


def validate_sentence(raw: str) -> str:
    """모델이 낸 글자를 응답 문장으로 낸다. 어긋나면 503(값을 지어내지 않는다, D74).

    받아들이는 조건(길이, 앞뒤 공백, 제어 문자, `{`·`[` 로 시작)은 생성된 계약 모델 ResponseSentence 만 가린다(D117).
    """
    # 왜 바깥 공백을 걷나: 스트림 작업이 문장 앞뒤의 공백을 보내지 않는 것(계약 README 응답 문장 스트림 5항)과 같은
    # 정리를 해야 두 작업이 같은 출력에 같은 문장을 낸다. 걷어 내는 것은 공백뿐이고 제어 문자는 걷지 않는다
    try:
        return ResponseSentence.model_validate(_trim_outer_space(raw)).root
    except ValidationError as error:
        raise _unusable("모델이 낸 문장이 계약의 응답 문장 조건을 지키지 않았다") from error


def _is_forbidden_control(char: str) -> bool:
    return unicodedata.category(char) == "Cc" and char not in "\n\t"


def _is_space(char: str) -> bool:
    # 왜 제어 문자를 뺀다: \x1c 같은 제어 문자는 공백으로도 판정되지만 계약은 제어 문자를 받지 않는다. 걷어 내면 거부할
    # 출력을 받아들이게 된다
    return char.isspace() and not _is_forbidden_control(char)


def _trim_outer_space(raw: str) -> str:
    start, end = 0, len(raw)
    while start < end and _is_space(raw[start]):
        start += 1
    while end > start and _is_space(raw[end - 1]):
        end -= 1
    return raw[start:end]


def _unusable(detail: str) -> ServiceFault:
    return ServiceFault(503, "모델이 쓸 수 있는 응답 문장을 내지 못했다", detail, retry_after=5)


class SentenceStream:
    """스트림으로 보낼 조각을 이어 가며 문장의 합격 조건(계약 ResponseSentence)을 지킨다(README 5항).

    조각은 바꾸지 않되 문장 앞의 공백은 보내지 않고, 끝의 공백은 뒤에 글자가 올 때까지 쥔다(끝나면
    버린다). 조건을 어기는 조각은 받지 않고 503 이다.
    """

    def __init__(self) -> None:
        self._text = ""  # 보낸 글자
        self._held = ""  # 뒤에 글자가 오면 함께 보낼 공백

    def accept(self, fragment: str) -> str | None:
        """보낼 글자가 있으면 돌려준다. 공백만이면 쥐고 None 이다."""
        out = ""
        held = self._held
        for char in fragment:
            if _is_forbidden_control(char):
                raise _stream_invalid("제어 문자가 왔다")
            if char.isspace():
                if self._text or out:  # 문장 앞의 공백은 버린다
                    held += char
                continue
            out += held + char
            held = ""
        if out:
            try:
                # 왜 계약 모델: 길이(344자)와 `{`·`[` 시작의 정본은 계약 ResponseSentence 다(D117)
                ResponseSentence.model_validate(self._text + out)
            except ValidationError as error:
                raise _stream_invalid(
                    "이으면 계약의 응답 문장 조건(길이 344자, 첫 글자)을 어기는 조각이 왔다"
                ) from error
            self._text += out
        self._held = held  # 조각을 거절하면 예외로 끝나므로 쥔 공백은 성공했을 때만 바꾼다
        return out or None

    def finish(self) -> str:
        """끝났을 때의 문장(쥔 끝 공백은 버린다). 비었으면 503 이다."""
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
