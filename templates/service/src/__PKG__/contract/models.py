# 이 파일은 openit-gen-contract 가 contracts/ 에서 생성했다. 손으로 고치지 않는다(ADR 0020).
# 다시 만들기: uv run --project tools/checks openit-gen-contract <영역 폴더>

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import AnyUrl, AwareDatetime, BaseModel, ConfigDict, Field, RootModel


class HealthCheckName(RootModel[str]):
    root: Annotated[str, Field(examples=['database'], max_length=63)]
    """
    점검 항목의 이름(예를 들어 database)
    """


class HealthStatus(StrEnum):
    """
    건강 점검 하나 또는 전체의 결과
    """

    pass_ = 'pass'
    warn = 'warn'
    fail = 'fail'


class HttpStatus(RootModel[int]):
    root: Annotated[int, Field(examples=[503], ge=400, le=599)]
    """
    오류 응답의 HTTP 상태 코드(클라이언트 오류 4xx, 서버 오류 5xx)
    """


class ImageRevision(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=['0123456789abcdef0123456789abcdef01234567'],
            max_length=64,
            pattern='^[0-9a-f]{40,64}$',
        ),
    ]
    """
    이미지를 만든 소스의 커밋 해시(소문자 16진수)
    """


class JsonPointer(RootModel[str]):
    root: Annotated[str, Field(examples=['/input/user_utterance'], max_length=8000)]
    """
    요청 본문 안에서 잘못된 값의 위치(JSON 포인터)
    """


class ProblemDetail(RootModel[str]):
    root: Annotated[
        str,
        Field(examples=['모델 출력이 합격 조건을 끝내 지키지 못했다'], max_length=4000),
    ]
    """
    이번 오류가 일어난 까닭의 사람용 설명. 환자 발화와 비밀 값은 넣지 않는다
    """


class ProblemFieldError(BaseModel):
    """
    요청의 칸 하나가 계약을 어긴 내용. 위치와 까닭
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    detail: ProblemDetail
    """
    그 칸이 어긋난 까닭
    """
    pointer: JsonPointer
    """
    잘못된 값이 있는 요청 본문 안의 위치
    """


class ProblemFieldErrors(RootModel[list[ProblemFieldError]]):
    """
    한 요청에서 어긋난 칸들의 목록
    """

    root: Annotated[list[ProblemFieldError], Field(max_length=100)]
    """
    한 요청에서 어긋난 칸들의 목록
    """


class ProblemInstance(RootModel[str]):
    root: Annotated[str, Field(examples=['/v1/extractions'], max_length=8000)]
    """
    이번 오류 발생 하나를 가리키는 URI 참조(보통 요청 경로)
    """


class ProblemReason(StrEnum):
    """
    오류의 세부 사유. 상태 코드로 나뉘지 않는 경우를 클라이언트가 가르는 값. 각 값에 그 값을 내는 작업을 적었다
    """

    OUTPUT_INVALID = 'OUTPUT_INVALID'
    TURN_IN_PROGRESS = 'TURN_IN_PROGRESS'
    START_CODE_INVALID = 'START_CODE_INVALID'
    START_CODE_EXPIRED = 'START_CODE_EXPIRED'
    START_CODE_USED = 'START_CODE_USED'
    SESSION_NOT_ACTIVE = 'SESSION_NOT_ACTIVE'
    MODEL_NOT_LOADED = 'MODEL_NOT_LOADED'
    QUESTION_BANK_VERSION_MISMATCH = 'QUESTION_BANK_VERSION_MISMATCH'
    DEADLINE_EXCEEDED = 'DEADLINE_EXCEEDED'
    CASE_VERSION_MISMATCH = 'CASE_VERSION_MISMATCH'
    PACKAGE_INVALID = 'PACKAGE_INVALID'
    ROLLBACK_TARGET_INVALID = 'ROLLBACK_TARGET_INVALID'
    RISK_DETECTION_DISABLED = 'RISK_DETECTION_DISABLED'


class ProblemTitle(RootModel[str]):
    root: Annotated[
        str, Field(examples=['모델 출력이 합격 조건을 지키지 못했다'], max_length=200)
    ]
    """
    오류 종류의 짧은 사람용 이름. 같은 종류면 항상 같다
    """


class ProblemType(RootModel[AnyUrl]):
    root: Annotated[AnyUrl, Field(examples=['https://openit/problems/OUTPUT_INVALID'])]
    """
    오류의 종류를 가리키는 절대 URI(scheme 이 있는 URI). 기본은 about:blank 다. 이 계약의 서버는 사유가 있으면 https://openit/problems/<ProblemReason 값> 을 쓴다
    """


class PrometheusExposition(RootModel[str]):
    root: Annotated[
        str,
        Field(
            examples=[
                '# TYPE turn_duration_seconds histogram\nturn_duration_seconds_count 1\n'
            ],
            max_length=8388608,
        ),
    ]
    """
    Prometheus 텍스트 노출 형식의 지표 본문. 8 MiB 는 바이트 상한이라 HTTP 본문 계층(Content-Length)에서 강제하고 maxLength 는 글자 수의 상한이며 둘은 따로다. 서비스는 RequiredPrometheusMetric 에 적힌 지표(turn_duration_seconds, model_call_duration_seconds)를 해당 서비스에서 반드시 낸다
    """


class RetryAfterSeconds(RootModel[int]):
    root: Annotated[int, Field(examples=[5], ge=0, le=120)]
    """
    클라이언트가 같은 요청을 다시 보내기 전에 기다릴 초
    """


class ServiceName(StrEnum):
    """
    계약에 나오는 상시 서비스(컨테이너 이미지가 하나인 단위)의 이름. 상시 서버가 없는 학습 파이프라인(model-lab)과 도구(deploy)는 서비스가 아니다
    """

    survey_service = 'survey-service'
    model_runtime = 'model-runtime'
    platform = 'platform'
    kiosk_frontend = 'kiosk-frontend'
    admin_console = 'admin-console'


class Timestamp(RootModel[AwareDatetime]):
    root: Annotated[AwareDatetime, Field(examples=['2026-11-10T09:30:00+09:00'])]
    """
    일이 일어난 때. UTC 오프셋을 포함한 RFC 3339 날짜-시각
    """


class HealthCheck(BaseModel):
    """
    건강 점검 항목 하나의 결과
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    name: HealthCheckName
    """
    점검한 의존 또는 기능의 이름
    """
    observed_at: Timestamp | None = None
    """
    이 항목을 마지막으로 점검한 때
    """
    status: HealthStatus
    """
    이 항목의 점검 결과
    """


class HealthChecks(RootModel[list[HealthCheck]]):
    """
    건강 점검 항목들
    """

    root: Annotated[list[HealthCheck], Field(max_length=100)]
    """
    건강 점검 항목들
    """


class HealthReport(BaseModel):
    """
    서비스의 건강 점검 응답 본문(application/json). /healthz 와 /readyz 가 낸다. 모양은 만료된 초안을 참고한 자체 모양이다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    checks: HealthChecks | None = None
    """
    의존별 점검 결과(/readyz 에서만)
    """
    revision: ImageRevision | None = None
    """
    실행 중인 이미지의 소스 커밋
    """
    service: ServiceName
    """
    응답한 서비스
    """
    status: HealthStatus
    """
    전체 결과. /healthz 는 프로세스 생존만, /readyz 는 의존 준비까지 본다
    """


class ProblemDetails(BaseModel):
    """
    모든 오류 응답의 본문(application/problem+json). 4xx 와 5xx 모두 이 모양이다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    detail: ProblemDetail | None = None
    """
    이번 오류의 설명
    """
    errors: ProblemFieldErrors | None = None
    """
    요청 본문에서 어긋난 칸들(검증 실패일 때만)
    """
    instance: ProblemInstance | None = None
    """
    이번 오류 발생을 가리키는 URI 참조
    """
    reason: ProblemReason | None = None
    """
    상태 코드만으로 가를 수 없는 세부 사유
    """
    status: HttpStatus
    """
    응답의 HTTP 상태 코드
    """
    title: ProblemTitle
    """
    오류 종류의 짧은 이름
    """
    type: ProblemType
    """
    오류 종류를 가리키는 URI 참조
    """
