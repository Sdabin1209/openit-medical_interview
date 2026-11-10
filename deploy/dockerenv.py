"""docker 호출 환경 격리(ADR 0004, 워크스페이스 규칙 'docker 호출은 프로젝트 자체 설정만 쓴다').

- 사용자 전역 ~/.docker(설정, 자격 도우미)를 읽지도 고치지도 않는다.
  호출자가 DOCKER_CONFIG 를 주면 그대로 쓰고, 없으면 리포 안 git 제외 폴더(.docker-config)의 빈 설정({})을 쓴다.
- 엔진 선택은 Docker CLI 공식 우선순위(DOCKER_CONTEXT 가 DOCKER_HOST 보다 우선)를 지켜 DOCKER_HOST 로 넘긴다.
  1) DOCKER_CONTEXT 가 있으면 DOCKER_HOST 와 무관하게 그 context 를 해석하고 실패하면 멈춘다.
  2) 성공한 엔드포인트로 DOCKER_HOST 를 덮어쓰고 DOCKER_CONTEXT 를 지운다.
  3) DOCKER_CONTEXT 가 없고 DOCKER_HOST 가 있으면 그대로 둔다.
  4) 둘 다 없으면 현재 context 를 해석하고 실패하면 멈춘다. 해석 실패를 삼켜 기본 엔진으로 넘어가지 않는다.
표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ISOLATED_CONFIG_DIRNAME = ".docker-config"  # .gitignore 에 있다
Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class DockerEnvError(RuntimeError):
    """docker 환경을 정하지 못했다. 호출자는 멈춰야 한다."""


def config_dir(environ: Mapping[str, str], root: Path = REPO_ROOT) -> Path:
    given = environ.get("DOCKER_CONFIG")
    if given:
        return Path(given)
    path = root / ISOLATED_CONFIG_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    config = path / "config.json"
    if not config.exists():
        config.write_text("{}\n", encoding="utf-8")
    return path


def _resolve_endpoint(context: str, base_env: Mapping[str, str], runner: Runner) -> str:
    result = runner(
        ["docker", "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}"],
        env=dict(base_env), capture_output=True, text=True, check=False,
    )
    endpoint = result.stdout.strip()
    if result.returncode != 0 or not endpoint:
        raise DockerEnvError(f"docker context '{context}' 를 해석하지 못했다(rc={result.returncode})")
    return endpoint


def docker_env(
    environ: Mapping[str, str] | None = None, root: Path = REPO_ROOT, runner: Runner = subprocess.run
) -> dict[str, str]:
    """docker 를 부를 때 쓸 환경 변수 전체를 돌려준다. 실패하면 DockerEnvError."""
    source = dict(os.environ if environ is None else environ)
    cfg = config_dir(source, root)
    env = dict(source)
    env["DOCKER_CONFIG"] = str(cfg)
    # 해석용 환경: 설정 폴더만 정하고 엔진 선택 변수는 뺀다
    probe = {k: v for k, v in env.items() if k not in ("DOCKER_HOST", "DOCKER_CONTEXT")}
    context = source.get("DOCKER_CONTEXT")
    if context:  # 규칙 1, 2
        env["DOCKER_HOST"] = _resolve_endpoint(context, probe, runner)
        env.pop("DOCKER_CONTEXT", None)
    elif source.get("DOCKER_HOST"):  # 규칙 3
        pass
    else:  # 규칙 4
        shown = runner(["docker", "context", "show"], env=probe, capture_output=True, text=True, check=False)
        name = shown.stdout.strip()
        if shown.returncode != 0 or not name:
            raise DockerEnvError(f"현재 docker context 를 알 수 없다(rc={shown.returncode})")
        env["DOCKER_HOST"] = _resolve_endpoint(name, probe, runner)
    return env


def run_docker(
    args: Sequence[str], *, environ: Mapping[str, str] | None = None, **kwargs: object
) -> subprocess.CompletedProcess[str]:
    """격리된 환경으로 docker 를 실행한다. 모든 docker 호출은 이 함수를 지난다(점검: tools/checks)."""
    env = docker_env(environ)
    return subprocess.run(["docker", *args], env=env, text=True, **kwargs)  # type: ignore[call-overload]  # noqa: S603, S607
