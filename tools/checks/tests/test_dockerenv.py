"""deploy/dockerenv.py 가 Docker CLI 공식 우선순위를 지키는지 본다(fake docker 로)."""

import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


class FakeDocker:
    """docker context show/inspect 를 흉내 낸다. 호출 기록과 호출 때 받은 환경을 남긴다."""

    def __init__(self, contexts: dict[str, str], current: str = "default", fail_show: bool = False) -> None:
        self.contexts = contexts
        self.current = current
        self.fail_show = fail_show
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> "subprocess.CompletedProcess[str]":
        self.calls.append((argv, dict(kwargs["env"])))
        if argv[:3] == ["docker", "context", "show"]:
            if self.fail_show:
                return subprocess.CompletedProcess(argv, 1, "", "err")
            return subprocess.CompletedProcess(argv, 0, self.current + "\n", "")
        if argv[:3] == ["docker", "context", "inspect"]:
            host = self.contexts.get(argv[3])
            if host is None:
                return subprocess.CompletedProcess(argv, 1, "", "no such context")
            return subprocess.CompletedProcess(argv, 0, host + "\n", "")
        raise AssertionError(argv)


def test_default_config_is_repo_local_empty_json(dockerenv: ModuleType, tmp_path: Path) -> None:
    env = dockerenv.docker_env({"HOME": "/home/x"}, tmp_path, FakeDocker({"default": "unix:///a.sock"}))
    assert env["DOCKER_CONFIG"] == str(tmp_path / ".docker-config")
    assert (tmp_path / ".docker-config" / "config.json").read_text().strip() == "{}"
    assert "/home/x/.docker" not in env["DOCKER_CONFIG"]


def test_given_docker_config_is_used_as_is(dockerenv: ModuleType, tmp_path: Path) -> None:
    env = dockerenv.docker_env({"DOCKER_CONFIG": "/given"}, tmp_path, FakeDocker({"default": "unix:///a.sock"}))
    assert env["DOCKER_CONFIG"] == "/given"
    assert not (tmp_path / ".docker-config").exists()


def test_rule1_context_wins_over_host(dockerenv: ModuleType, tmp_path: Path) -> None:
    fake = FakeDocker({"remote": "ssh://box"})
    env = dockerenv.docker_env({"DOCKER_CONTEXT": "remote", "DOCKER_HOST": "unix:///other"}, tmp_path, fake)
    assert env["DOCKER_HOST"] == "ssh://box"  # 규칙 2: 엔드포인트로 덮어쓴다
    assert "DOCKER_CONTEXT" not in env
    # 해석할 때 DOCKER_HOST 와 DOCKER_CONTEXT 는 환경에서 뺀다
    assert all("DOCKER_HOST" not in e and "DOCKER_CONTEXT" not in e for _, e in fake.calls)


def test_rule1_unresolvable_context_stops(dockerenv: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(dockerenv.DockerEnvError):
        dockerenv.docker_env({"DOCKER_CONTEXT": "nope", "DOCKER_HOST": "unix:///other"}, tmp_path, FakeDocker({}))


def test_rule3_host_without_context_is_kept(dockerenv: ModuleType, tmp_path: Path) -> None:
    fake = FakeDocker({})
    env = dockerenv.docker_env({"DOCKER_HOST": "tcp://h:1"}, tmp_path, fake)
    assert env["DOCKER_HOST"] == "tcp://h:1"
    assert fake.calls == []


def test_rule4_current_context_is_resolved(dockerenv: ModuleType, tmp_path: Path) -> None:
    env = dockerenv.docker_env({}, tmp_path, FakeDocker({"mine": "unix:///m.sock"}, current="mine"))
    assert env["DOCKER_HOST"] == "unix:///m.sock"


def test_rule4_failure_stops_instead_of_default_engine(dockerenv: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(dockerenv.DockerEnvError):
        dockerenv.docker_env({}, tmp_path, FakeDocker({}, fail_show=True))
    with pytest.raises(dockerenv.DockerEnvError):
        dockerenv.docker_env({}, tmp_path, FakeDocker({}, current="ghost"))
