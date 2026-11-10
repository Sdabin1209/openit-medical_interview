"""이미지 스모크(ADR 0004). `tools/smoke <영역>` 이 부른다.

docker 호출은 호출자가 준비한 격리 환경(DOCKER_CONFIG, DOCKER_HOST)만 쓴다.
호스트 포트는 Docker 가 배정한다(고정 포트 없음).
"""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.smoke


def _docker_env() -> dict[str, str]:
    if not os.environ.get("DOCKER_CONFIG"):
        pytest.fail("DOCKER_CONFIG 가 없다. tools/smoke 로 실행해 격리 설정을 받는다(사용자 ~/.docker 를 쓰지 않는다)")
    keep = ("PATH", "DOCKER_CONFIG", "DOCKER_HOST")
    return {key: os.environ[key] for key in keep if key in os.environ}


def _docker(*args: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["docker", *args], env=_docker_env(), capture_output=True, text=True, check=False  # noqa: S607
    )
    if result.returncode != 0:
        pytest.fail(f"docker {args[0]} 실패 rc={result.returncode}: {result.stderr[-500:]}")
    return result.stdout.strip()


@pytest.fixture(scope="module")
def container() -> Iterator[str]:
    image = os.environ.get("OPENIT_SMOKE_IMAGE")
    if not image:
        pytest.fail("OPENIT_SMOKE_IMAGE 가 없다. tools/smoke 로 실행한다")
    name = f"openit-__PKG__-smoke-{uuid.uuid4().hex[:8]}"
    cid = _docker(
        "run", "-d", "--name", name, "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "-p", "127.0.0.1::8080", image,
    )
    try:
        yield cid
    finally:
        # 진단 수단을 지우지 않는다: 실패했으면 로그를 먼저 남긴다
        subprocess.run(["docker", "logs", "--tail", "50", cid], env=_docker_env(), check=False)  # noqa: S603, S607
        subprocess.run(["docker", "rm", "-f", cid], env=_docker_env(), check=False, capture_output=True)  # noqa: S603, S607


def _url(cid: str, path: str) -> str:
    mapping = _docker("port", cid, "8080/tcp").splitlines()[0]
    return f"http://{mapping}{path}"


def _get(cid: str, path: str) -> tuple[int, object]:
    deadline = time.monotonic() + 30
    while True:
        try:
            with urllib.request.urlopen(_url(cid, path), timeout=3) as response:  # noqa: S310
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)


def test_healthz(container: str) -> None:
    assert _get(container, "/healthz") == (200, {"status": "ok"})


def test_readyz(container: str) -> None:
    assert _get(container, "/readyz") == (200, {"status": "ready", "failed": []})


def test_runs_as_non_root(container: str) -> None:
    assert _docker("exec", container, "id", "-u") != "0"


def test_root_filesystem_is_read_only(container: str) -> None:
    mode = _docker("inspect", "-f", "{{.HostConfig.ReadonlyRootfs}}", container)
    assert mode == "true"
