"""잡 명령줄: 결과 JSON 한 줄과 종료 코드 0·75·1(D130). 실제 PostgreSQL 이 필요한 시험은 `-m postgres`."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from tests.support.harness import build_harness
from tests.support.postgres import PostgresContainer
from tests.unit.test_settings_health import REQUIRED

from survey_service.contract.models import JobRunResult

REQUESTED = "2026-11-10T09:00:00+00:00"


def _run(args: list[str], env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ["PATH"], **REQUIRED, **env_extra}
    return subprocess.run(  # noqa: S603  (우리 모듈을 같은 파이썬으로 실행한다)
        [sys.executable, "-m", "survey_service.jobs", *args], env=env, capture_output=True, text=True, check=False
    )


def test_unknown_job_and_missing_time_are_usage_errors() -> None:
    assert _run(["TRAIN", "--requested-at", REQUESTED], {}).returncode == 2
    assert _run(["PURGE_EXPIRED"], {}).returncode == 2


def test_unreachable_database_is_transient_75(tmp_path: Path) -> None:
    password = tmp_path / "pw"
    password.write_text("x", encoding="utf-8")
    env = {
        "OPENIT_DATABASE_URL": "postgresql://survey@127.0.0.1:1/survey",
        "OPENIT_DATABASE_PASSWORD_FILE": str(password),
    }
    done = _run(["PURGE_EXPIRED", "--requested-at", REQUESTED], env)
    lines = done.stdout.strip().splitlines()
    assert done.returncode == 75 and len(lines) == 1  # 표준 출력에는 결과 한 줄뿐이다
    assert JobRunResult.model_validate_json(lines[0]).exit_code.value == 75


def test_missing_secret_is_failure_1(tmp_path: Path) -> None:
    done = _run(
        ["DETECT_FAILURES", "--requested-at", REQUESTED], {"OPENIT_DATABASE_PASSWORD_FILE": str(tmp_path / "nope")}
    )
    assert done.returncode != 0 and "SECRET" not in done.stdout


@pytest.mark.postgres
@pytest.mark.anyio
@pytest.mark.parametrize("job", ["DETECT_FAILURES", "PURGE_EXPIRED"])
async def test_jobs_run_against_postgres(postgres_server: PostgresContainer, tmp_path: Path, job: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    name = f"jobs_{job.lower()}"
    admin = create_async_engine(postgres_server.url("postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{name}"'))
    await admin.dispose()
    harness = await build_harness(postgres_server.url(name))
    await harness.engine.dispose()
    password = tmp_path / "pw"
    password.write_text(postgres_server.password, encoding="utf-8")
    env = {
        "OPENIT_DATABASE_URL": f"postgresql://postgres@127.0.0.1:{postgres_server.port}/{name}",
        "OPENIT_DATABASE_PASSWORD_FILE": str(password),
    }
    for _ in range(2):  # 여러 번 실행해도 안전하다(멱등)
        done = _run([job, "--requested-at", REQUESTED], env)
        assert done.returncode == 0, done.stderr[-300:]
        result = JobRunResult.model_validate(json.loads(done.stdout.strip()))
        assert result.job.value == job and result.processed_count is not None and result.processed_count.root == 0
