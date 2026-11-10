"""환경 입력과 비밀·한도: 설정은 환경 변수, 비밀은 파일에서만 읽는다(ADR 0004, 0005).

환경 입력의 모양은 계약 SurveyServiceEnv 가 정한다(받아들이는 조건은 전부 스키마에 둔다). 앱 조립(main)과
잡(jobs)이 함께 쓴다.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from survey_service.contract.models import ServiceName, SurveyServiceEnv
from survey_service.types import Limits

SERVICE = ServiceName.survey_service
# 왜 이 값들: 한도는 계약이 값을 const 로 못박은 것(ReaskLimit 2, KioskIdleResetSeconds 60, SurveyTurnLimitSeconds 50,
# ExtractClientLimitSeconds 21, RespondClientLimitSeconds 26, AlertStreamHeartbeatSeconds 15,
# RawUtteranceRetentionDays 180)을 따른다.
# 계약과 어긋나지 않는지는 tests/unit/test_limits.py 가 계약 파일과 견준다
CONTRACT_LIMITS = {
    "reask_limit": 2,
    "idle_seconds": 60,
    "turn_seconds": 50,
    "extract_seconds": 21,
    "respond_seconds": 26,
    "heartbeat_seconds": 15,
    "retention_days": 180,
}
DEFAULT_START_CODE_TTL = 300  # 계약 StartCodeTtlSeconds 의 default
# 왜 10회·300초: NIST SP 800-63B 5.2.2 는 실패 시도에 한도를 두라고만 정하고 값은 정하지 않는다. 6자리
# 코드(100만 가지)를
# 기기당 5분에 10번으로 묶으면 코드 유효 시간(최대 600초) 안에 맞힐 확률이 10^-5 수준이다(ADR 0002, 측정하지 않은 선택)
START_FAILURE_LIMIT = 10
START_FAILURE_WINDOW_SECONDS = 300
RETRY_AFTER_SECONDS = 5  # 계약 RetryAfterSeconds 의 예시 값. 측정으로 정한 값이 아니다


class SecretError(RuntimeError):
    """비밀을 읽지 못했다. 메시지에는 비밀 이름만 넣고 값과 경로는 넣지 않는다."""


def read_secret(name: str, environ: Mapping[str, str] | None = None) -> str:
    """환경 변수 `<name>_FILE` 이 가리키는 파일에서 비밀을 읽는다(D84).

    왜 파일만: 환경 변수는 프로세스 목록·`docker inspect`·자식 프로세스로 새 나간다.
    """
    env = os.environ if environ is None else environ
    path = env.get(f"{name}_FILE")
    if not path:
        raise SecretError(f"비밀 {name} 을 읽을 수 없다: {name}_FILE 이 설정되지 않았다")
    try:
        value = Path(path).read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as error:
        raise SecretError(f"비밀 {name} 을 읽을 수 없다: 파일을 열지 못했다") from error
    if not value:
        raise SecretError(f"비밀 {name} 을 읽을 수 없다: 파일이 비어 있다")
    return value


def load_env(environ: Mapping[str, str]) -> SurveyServiceEnv:
    """환경 변수에서 계약 SurveyServiceEnv 를 읽어 검증한다(모르는 변수는 건너뛴다. 모양이 틀리면 ValidationError)."""
    fields = set(SurveyServiceEnv.model_fields)
    return SurveyServiceEnv.model_validate({key: value for key, value in environ.items() if key in fields})


def limits_of(env: SurveyServiceEnv) -> Limits:
    """환경 입력과 계약 한도로 영역 한도를 만든다."""
    ttl = (
        env.SURVEY_START_CODE_TTL_SECONDS.root
        if env.SURVEY_START_CODE_TTL_SECONDS is not None
        else DEFAULT_START_CODE_TTL
    )
    return Limits(
        start_code_ttl_seconds=ttl,
        start_failure_limit=START_FAILURE_LIMIT,
        start_failure_window_seconds=START_FAILURE_WINDOW_SECONDS,
        retry_after_seconds=RETRY_AFTER_SECONDS,
        **CONTRACT_LIMITS,
    )
