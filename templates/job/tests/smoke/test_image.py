"""잡 이미지 스모크(ADR 0004, 0020). `tools/smoke job <영역>` 이 부른다.

docker 호출은 호출자가 준비한 격리 환경(DOCKER_CONFIG, DOCKER_HOST)만 쓴다. 잡은 서버가 아니라 한 번 실행하고 끝난다.
"""

import json
import os
import subprocess
import uuid
from pathlib import Path

import pytest

from __PKG__.contract.models import JobRunResult, JobsDeclaration

pytestmark = pytest.mark.smoke
ROOT = Path(__file__).resolve().parents[2]


def _docker_env() -> dict[str, str]:
    if not os.environ.get("DOCKER_CONFIG"):
        pytest.fail("DOCKER_CONFIG 가 없다. tools/smoke 로 실행해 격리 설정을 받는다(사용자 ~/.docker 를 쓰지 않는다)")
    keep = ("PATH", "DOCKER_CONFIG", "DOCKER_HOST")
    return {key: os.environ[key] for key in keep if key in os.environ}


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["docker", *args], env=_docker_env(), capture_output=True, text=True, check=False  # noqa: S607
    )


def _image() -> str:
    image = os.environ.get("OPENIT_SMOKE_IMAGE")
    if not image:
        pytest.fail("OPENIT_SMOKE_IMAGE 가 없다. tools/smoke 로 실행한다")
    return image


def test_declared_job_runs_once_and_reports_one_json_line() -> None:
    declaration = JobsDeclaration.model_validate_json((ROOT / "jobs.json").read_text(encoding="utf-8"))
    name = f"openit-__PKG__-smoke-{uuid.uuid4().hex[:8]}"
    for declared in declaration.jobs:
        result = _docker(
            "run", "--rm", "--name", name, "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", _image(), declared.job.value,
        )  # fmt: skip
        assert result.returncode == 0, result.stderr[-500:]
        lines = result.stdout.splitlines()
        assert len(lines) == 1
        assert JobRunResult.model_validate_json(lines[0]).job == declared.job


def test_runs_as_non_root() -> None:
    user = _docker("inspect", "-f", "{{.Config.User}}", _image()).stdout.strip()
    assert user not in ("", "0", "root", "0:0")


def test_jobs_label_is_the_declaration() -> None:
    label = _docker("inspect", "-f", '{{index .Config.Labels "io.openit.jobs"}}', _image()).stdout.strip()
    declared = json.loads((ROOT / "jobs.json").read_text(encoding="utf-8"))
    assert json.loads(label) == declared
