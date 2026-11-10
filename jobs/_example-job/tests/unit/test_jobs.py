"""잡 명령: 표준 출력은 JobRunResult 한 줄, 종료 코드는 0·75·1(D130)이고, jobs.json 은 JobsDeclaration 이다."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from example_job.contract.models import JobName, JobRunResult, JobsDeclaration
from example_job.main import JOBS, TransientJobError, app

ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def test_success_prints_one_json_line_and_exits_0() -> None:
    result = runner.invoke(app, ["PURGE_EXPIRED"])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert len(lines) == 1
    parsed = JobRunResult.model_validate_json(lines[0])
    assert parsed.job == JobName.PURGE_EXPIRED
    assert json.loads(lines[0])["exit_code"] == 0
    assert json.loads(lines[0])["processed_count"] == 3


def test_transient_failure_exits_75(monkeypatch: pytest.MonkeyPatch) -> None:
    def down() -> int:
        raise TransientJobError

    monkeypatch.setitem(JOBS, JobName.PURGE_EXPIRED, down)
    result = runner.invoke(app, ["PURGE_EXPIRED"])
    assert result.exit_code == 75
    assert json.loads(result.stdout.splitlines()[0])["exit_code"] == 75


def test_other_failure_exits_1_without_leaking_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> int:
        raise RuntimeError("postgresql://user:SECRET@host/db")

    monkeypatch.setitem(JOBS, JobName.PURGE_EXPIRED, boom)
    result = runner.invoke(app, ["PURGE_EXPIRED"])
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    assert json.loads(result.stdout.splitlines()[0])["exit_code"] == 1


def test_unknown_job_name_is_usage_error() -> None:
    assert runner.invoke(app, ["NO_SUCH_JOB"]).exit_code == 2


def test_jobs_json_is_a_valid_declaration_and_matches_registry() -> None:
    declaration = JobsDeclaration.model_validate_json((ROOT / "jobs.json").read_text(encoding="utf-8"))
    assert {item.job for item in declaration.jobs} == set(JOBS)
