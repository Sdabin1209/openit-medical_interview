"""잡: DETECT_FAILURES(쌓인 턴 기록에서 실패 사례를 규칙으로 찾는다), PURGE_EXPIRED(보존 기간이 지난 자료를 지운다).

`python -m survey_service.jobs <잡 이름> --requested-at <RFC 3339 시각>` 으로 한 번 실행한다(JobRunInput).
같은 입력은 같은 결과이고
여러 번 실행해도 안전하다(멱등, D39). 잡은 시계를 스스로 읽지 않고 요청한 시각을 쓴다. 영역은 실행 일정을 모른다(D131).
표준 출력에는 JobRunResult JSON 한 줄만 낸다. 종료 코드: 0 성공, 75 일시적 실패(DB 가 잠시 안 됨), 1 실패(D130).
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import OperationalError

from survey_service.components import failure_case
from survey_service.contract.models import JobExitCode, JobName, JobRunInput, JobRunResult
from survey_service.settings import limits_of, load_env, read_secret
from survey_service.store.engine import database_url, make_engine
from survey_service.store.repository import SqlStore
from survey_service.types import Store

EXIT_OK, EXIT_TRANSIENT, EXIT_FAILED = 0, 75, 1  # 왜 75: sysexits.h EX_TEMPFAIL, 계약 JobExitCode(D130)
# 왜 500: 한 번에 읽는 턴 기록의 수. 메모리와 트랜잭션 길이를 묶는 선택이며 측정하지 않았다
BATCH = 500
log = logging.getLogger("survey_service.jobs")


async def detect_failures(store: Store, now: datetime) -> int:
    """아직 보지 않은 턴 기록에서 실패 사례를 찾아 저장한다. 만든 사례 수를 돌려준다."""
    created = 0
    while True:
        async with store.transaction() as tx:
            turns = await tx.turns_without_cases(BATCH)
            if not turns:
                return created
            for case in failure_case.detect(turns, uuid4, now):
                created += int(await tx.create_case(case))
            await tx.mark_cases_checked(tuple((t.session_id, t.turn_id) for t in turns))


async def purge_expired(store: Store, now: datetime, *, retention_days: int, idle_seconds: int) -> int:
    """유휴로 만료된 세션을 EXPIRED 로 바꾸고, 보존 기간(180일)이 지난 발화 원문과 쓰지 않는 시작 코드를 지운다."""
    async with store.transaction() as tx:
        expired = await tx.mark_expired_sessions(now - timedelta(seconds=idle_seconds))
        purged = await tx.purge_expired(now, now - timedelta(days=retention_days))
    return expired + purged


async def run_job(job: JobName, requested_at: datetime, store: Store, *, retention_days: int, idle_seconds: int) -> int:
    """잡 하나를 실행하고 처리한 항목 수를 돌려준다."""
    if job is JobName.DETECT_FAILURES:
        return await detect_failures(store, requested_at)
    if job is JobName.PURGE_EXPIRED:
        return await purge_expired(store, requested_at, retention_days=retention_days, idle_seconds=idle_seconds)
    raise ValueError(f"이 영역의 잡이 아니다: {job.value}")


async def _execute(job: JobName, requested_at: datetime) -> tuple[JobRunResult, int]:
    started = datetime.now(UTC)
    env = load_env(os.environ)
    limits = limits_of(env)
    engine = make_engine(database_url(str(env.OPENIT_DATABASE_URL.root), read_secret("OPENIT_DATABASE_PASSWORD")))
    processed: int | None = None
    code = EXIT_OK
    try:
        processed = await run_job(
            job, requested_at, SqlStore(engine), retention_days=limits.retention_days, idle_seconds=limits.idle_seconds
        )
    except (OperationalError, ConnectionError, OSError):
        log.warning("%s: 일시적 실패, 다음 실행에서 다시 한다", job.value)
        code = EXIT_TRANSIENT
    except Exception:  # 왜: 어떤 실패든 결과 줄과 종료 코드 1 로 알린다. 예외 내용은 로그(표준 오류)에만 남긴다
        log.exception("%s: 실패", job.value)
        code = EXIT_FAILED
    finally:
        await engine.dispose()
    body: dict[str, object] = {
        "job": job.value,
        "exit_code": JobExitCode(code).value,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
    }
    if processed is not None:
        body["processed_count"] = processed
    return JobRunResult.model_validate(body), code


def main(argv: list[str] | None = None) -> int:
    """명령줄 진입점."""
    parser = argparse.ArgumentParser(prog="survey_service.jobs", description=__doc__)
    parser.add_argument("job", choices=[JobName.DETECT_FAILURES.value, JobName.PURGE_EXPIRED.value])
    parser.add_argument("--requested-at", required=True, help="스케줄러가 실행을 요청한 때(RFC 3339)")
    args = parser.parse_args(argv)
    request = JobRunInput.model_validate({"job": args.job, "requested_at": args.requested_at})
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    result, code = asyncio.run(_execute(request.job, request.requested_at.root))
    sys.stdout.write(result.model_dump_json(exclude_none=True) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
