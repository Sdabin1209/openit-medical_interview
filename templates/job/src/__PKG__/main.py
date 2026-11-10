"""조립과 진입점(ADR 0003). 잡 단계마다 한 번 실행하는 명령이다: `__PKG__ <잡 이름>`.

- 표준 출력에는 JobRunResult JSON 한 줄(JSON Lines)만 낸다. 로그는 표준 오류로 낸다(D130).
- 종료 코드: 0 성공, 75 일시적 실패(다음 실행에서 다시 한다, sysexits EX_TEMPFAIL), 1 실패(D130).
"""

import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

import typer
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from __PKG__.components.counter import count_items
from __PKG__.contract.models import JobExitCode, JobName, JobRunResult
from __PKG__.link.source import fetch_step_input

EXIT_OK = 0
EXIT_TRANSIENT = 75  # 왜 75: sysexits.h EX_TEMPFAIL, 계약 JobExitCode(D130)
EXIT_FAILED = 1

log = logging.getLogger("__PKG__")


class TransientJobError(Exception):
    """일시적 실패(이웃이 잠시 안 됨 등). 같은 입력으로 다음 실행에서 다시 하면 된다. 종료 코드 75."""


class Settings(BaseSettings):
    """환경 변수 설정(12-Factor 3). 변수 이름은 `OPENIT_` 접두어를 쓴다."""

    model_config = SettingsConfigDict(env_prefix="OPENIT_", extra="ignore")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="표준 오류로 내는 로그의 수준."
    )


JobFunction = Callable[[], int]  # 처리한 항목 수를 돌려준다


def purge_expired() -> int:
    """PURGE_EXPIRED 잡(템플릿 예시). 실제 영역은 자기 잡을 만들어 JOBS 와 jobs.json 에 더한다."""
    return count_items(fetch_step_input()).processed_count


# 왜 표: 잡 이름이 곧 실행할 함수다. jobs.json(JobsDeclaration)과 같은 이름 집합이어야 한다(tests/unit/test_jobs.py)
JOBS: dict[JobName, JobFunction] = {JobName.PURGE_EXPIRED: purge_expired}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def run_job(job: JobName) -> tuple[JobRunResult, int]:
    """잡 하나를 한 번 실행하고 결과와 종료 코드를 돌려준다. 예외는 종료 코드로 바꾼다."""
    started = _now()
    processed: int | None = None
    code = EXIT_OK
    try:
        processed = JOBS[job]()
    except TransientJobError:
        log.warning("%s: 일시적 실패, 다음 실행에서 다시 한다", job.value)
        code = EXIT_TRANSIENT
    except Exception:  # 왜: 어떤 실패든 결과 줄과 종료 코드 1 로 알린다. 예외 내용은 로그(표준 오류)에만 남긴다
        log.exception("%s: 실패", job.value)
        code = EXIT_FAILED
    body: dict[str, object] = {
        "job": job.value,
        "exit_code": JobExitCode(code).value,
        "started_at": started,
        "finished_at": _now(),
    }
    if processed is not None:
        body["processed_count"] = processed
    return JobRunResult.model_validate(body), code


app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(job: JobName = typer.Argument(..., help="실행할 잡 이름(계약 JobName).")) -> None:  # noqa: B008
    """잡 하나를 한 번 실행한다."""
    logging.basicConfig(level=Settings().log_level, stream=sys.stderr)
    result, code = run_job(job)
    typer.echo(result.model_dump_json(exclude_none=True))
    raise typer.Exit(code)
