"""시험용 PostgreSQL 16 컨테이너(`pytest -m postgres`). 컨테이너 이름에 openit-int-ss 를 넣고, 시험이 끝나면
자기가 만든 것만 ID 로 지운다.

docker 호출은 프로젝트 자체 설정만 쓴다: DOCKER_CONFIG 가 있으면 그대로, 없으면 빈 설정 폴더({})를 쓰고
사용자 ~/.docker 는 읽지 않는다.
"""

import json
import os
import secrets
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

# 왜 이 digest: deploy/compose.yaml 과 compose.dev.yaml 이 쓰는 이미지와 같다(이미지는 digest 로 고정한다, ADR 0006)
IMAGE = "postgres:16.10-bookworm@sha256:38471f330eb885e04de130b768d6db4e10469e2311879c7e5c699f6d2d8a1c74"


STARTUP_LIMIT_SECONDS = 60  # 측정하지 않았다. 이미지 기동에 넉넉한 상한(기존 값 유지)
READY_LINE = "database system is ready to accept connections"


def docker_env() -> dict[str, str]:
    env = {key: os.environ[key] for key in ("PATH", "DOCKER_HOST", "DOCKER_CONTEXT") if key in os.environ}
    config = os.environ.get("DOCKER_CONFIG")
    if not config:
        folder = Path(tempfile.mkdtemp(prefix="openit-int-ss-docker-", dir=os.environ.get("TMPDIR")))
        (folder / "config.json").write_text("{}\n", encoding="utf-8")
        config = str(folder)
    env["DOCKER_CONFIG"] = config
    return env


def docker(*args: str, check: bool = True, with_stderr: bool = False) -> str:
    result = subprocess.run(["docker", *args], env=docker_env(), capture_output=True, text=True, check=False)  # noqa: S603, S607
    if check and result.returncode != 0:
        raise RuntimeError(f"docker {args[0]} 실패 rc={result.returncode}: {result.stderr[-300:]}")
    return (result.stdout + result.stderr if with_stderr else result.stdout).strip()


class PostgresContainer:
    """임시 PostgreSQL. 호스트 포트는 Docker 가 배정한다(고정 포트 없음)."""

    def __init__(self) -> None:
        self.password = secrets.token_hex(12)
        name = f"openit-int-ss-test-pg-{uuid.uuid4().hex[:8]}"
        self.cid = docker(
            "run", "-d", "--name", name, "-e", f"POSTGRES_PASSWORD={self.password}", "-p", "127.0.0.1::5432",
            "--tmpfs", "/var/lib/postgresql/data", IMAGE,
        )  # fmt: skip
        mapping = docker("port", self.cid, "5432/tcp").splitlines()[0]
        self.port = int(mapping.rsplit(":", 1)[1])
        # 왜 로그의 준비 문구를 두 번 센다: 초기화 중 임시 서버가 먼저 준비되고 재시작한다(공식 이미지 동작, testcontainers 도 같은 방식).
        # 기동 대기는 상한 안에서 상태를 보는 것이고 시험 판정의 시간이 아니다
        deadline = time.monotonic() + STARTUP_LIMIT_SECONDS
        while docker("logs", self.cid, check=False, with_stderr=True).count(READY_LINE) < 2:
            if time.monotonic() > deadline:
                logs = docker("logs", "--tail", "30", self.cid, check=False, with_stderr=True)
                raise RuntimeError(f"PostgreSQL 이 준비되지 않았다: {logs}")
            time.sleep(0.5)

    def url(self, database: str) -> str:
        return f"postgresql+asyncpg://postgres:{self.password}@127.0.0.1:{self.port}/{database}"

    def stop(self) -> None:
        # 진단 수단을 지우지 않는다: 실패가 있었다면 호출한 쪽이 먼저 로그를 남긴다(conftest)
        docker("rm", "-f", self.cid, check=False)


_ = json
