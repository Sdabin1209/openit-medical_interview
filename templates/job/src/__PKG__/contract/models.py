# 이 파일은 openit-gen-contract 가 contracts/ 에서 생성했다. 손으로 고치지 않는다(ADR 0020).
# 다시 만들기: uv run --project tools/checks openit-gen-contract <영역 폴더>

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel


class BackupSnapshotId(RootModel[str]):
    root: Annotated[
        str, Field(examples=['79766175'], max_length=64, pattern='^[0-9a-f]{8,64}$')
    ]
    """
    백업 스냅샷 하나의 식별자(restic 스냅샷 ID 의 16진수 표기)
    """


class JobExitCode(IntEnum):
    """
    잡이 끝나며 내는 종료 코드
    """

    integer_0 = 0
    integer_75 = 75
    integer_1 = 1


class JobName(StrEnum):
    """
    deploy 의 스케줄러가 한 번 실행하는 잡의 이름
    """

    IMPORT_DATASET = 'IMPORT_DATASET'
    PREPARE = 'PREPARE'
    TRAIN = 'TRAIN'
    EVALUATE = 'EVALUATE'
    PUBLISH = 'PUBLISH'
    DETECT_FAILURES = 'DETECT_FAILURES'
    PURGE_EXPIRED = 'PURGE_EXPIRED'
    BACKUP = 'BACKUP'
    RESTORE = 'RESTORE'
    OFFSITE_SYNC = 'OFFSITE_SYNC'
    RESTORE_TEST = 'RESTORE_TEST'


class JobTimeoutSeconds(RootModel[int]):
    root: Annotated[int, Field(examples=[600], ge=1, le=259200)]
    """
    잡 한 번이 끝나야 하는 시간 상한(초). deploy 가 이 값보다 큰 가장 작은 300초 배수를 주기로 정한다
    """


class ProcessedCount(RootModel[int]):
    root: Annotated[int, Field(examples=[3], ge=0, le=2147483647)]
    """
    잡이 처리한 항목의 수
    """


class Timestamp(RootModel[AwareDatetime]):
    root: Annotated[AwareDatetime, Field(examples=['2026-11-10T09:30:00+09:00'])]
    """
    일이 일어난 때. UTC 오프셋을 포함한 RFC 3339 날짜-시각
    """


class JobDeclaration(BaseModel):
    """
    영역이 선언하는 잡 하나(이름과 시간 상한)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    job: JobName
    """
    잡 이름
    """
    timeout_seconds: JobTimeoutSeconds
    """
    이 잡의 시간 상한
    """


class JobRunResult(BaseModel):
    """
    잡 한 번의 실행 결과(표준 출력에 JSON 한 줄로 낸다)
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    exit_code: JobExitCode
    """
    종료 코드
    """
    finished_at: Timestamp
    """
    끝난 때
    """
    job: JobName
    """
    실행한 잡
    """
    processed_count: ProcessedCount | None = None
    """
    처리한 항목 수
    """
    snapshot_id: BackupSnapshotId | None = None
    """
    BACKUP 이 만든 스냅샷
    """
    started_at: Timestamp
    """
    시작한 때
    """


class JobsDeclaration(BaseModel):
    """
    이미지가 가진 잡들의 선언. 영역은 실행 일정을 모른다
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    jobs: Annotated[list[JobDeclaration], Field(max_length=11)]
    """
    잡들
    """
