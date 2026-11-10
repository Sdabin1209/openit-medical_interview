"""start_code: 일회용 시작 코드 발급(6자리 숫자)과 사용 판정.

입력은 발급 요청과 시계, 출력은 코드 기록과 판정이다. 저장·시도 한도 집계는 모른다(store 와 링크가 한다).
"""

import secrets
from datetime import datetime, timedelta
from uuid import UUID

from survey_service.types import StartCodeRecord, StartCodeVerdict

CODE_DIGITS = 6  # 왜: 계약 StartCodeValue(6자리 숫자, UD-04, RFC 4226 의 6자리 HOTP 와 같은 자릿수)


def new_code() -> str:
    """6자리 숫자 코드. 왜 secrets: 추측할 수 있는 난수(random)로 코드를 만들면 남의 코드를 맞힐 수 있다."""
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def issue(
    *,
    code: str,
    subject_ref: str,
    questionnaire_id: str | None,
    issued_by: str,
    now: datetime,
    ttl_seconds: int,
) -> StartCodeRecord:
    """발급 기록을 만든다. 유효 시간은 설정(SURVEY_START_CODE_TTL_SECONDS)에서 온다."""
    return StartCodeRecord(
        code=code,
        subject_ref=subject_ref,
        questionnaire_id=questionnaire_id,
        issued_by=issued_by,
        issued_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )


def evaluate(record: StartCodeRecord | None, device_id: str, now: datetime) -> StartCodeVerdict:
    """이 기기가 지금 이 코드로 시작할 수 있는지.

    같은 기기가 같은 코드로 다시 시작하면(응답을 못 받고 재전송) 만료 뒤에도 REPLAY 다(계약 startSession).
    """
    if record is None:
        return StartCodeVerdict.INVALID
    if record.used_by_device is not None:
        return StartCodeVerdict.REPLAY if record.used_by_device == device_id else StartCodeVerdict.USED
    if now >= record.expires_at:
        return StartCodeVerdict.EXPIRED
    return StartCodeVerdict.OK


def use(record: StartCodeRecord, device_id: str, session_id: UUID) -> StartCodeRecord:
    """코드를 썼다고 표시한 새 기록(한 번 쓰면 폐기)."""
    return record.model_copy(update={"used_by_device": device_id, "used_session_id": session_id})
