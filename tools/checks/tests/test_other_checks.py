"""docker 격리, 이미지 고정, bake 대상, 영역 경계 점검이 위반을 실제로 잡는지 본다."""

from pathlib import Path

from openit_checks import area_isolation, bake_targets, docker_isolation, dockerfile_lint, image_pins

from .conftest_helpers import write

D1 = "a" * 64
D2 = "b" * 64


# ---- docker 격리 ----
def test_docker_call_without_env_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "tool.py", 'import subprocess\nsubprocess.run(["docker", "ps"], check=False)\n')
    found = docker_isolation.run(tmp_path)
    assert len(found) == 1 and "env=" in found[0].message


def test_docker_call_with_env_is_ok(tmp_path: Path) -> None:
    write(tmp_path, "tool.py", 'import subprocess\nsubprocess.run(["docker", "ps"], env={}, check=False)\n')
    assert docker_isolation.run(tmp_path) == []


def test_docker_call_with_star_args_without_env_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "tool.py", 'import subprocess\nargs = []\nsubprocess.run(["docker", *args])\n')
    assert len(docker_isolation.run(tmp_path)) == 1


def test_user_docker_dir_string_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "tool.py", 'import os\nCONFIG = os.path.expanduser("~/.docker/config.json")\nOTHER = "~/.docker/config.json"\n')
    found = docker_isolation.run(tmp_path)
    assert len(found) == 2 and all(".docker" in v.message for v in found)


def test_prose_mention_is_not_violation(tmp_path: Path) -> None:
    write(tmp_path, "tool.py", '"""사용자 ~/.docker 를 쓰지 않는다."""\nprint("사용자 ~/.docker 를 읽지 않는다")\n')
    assert docker_isolation.run(tmp_path) == []


def test_shell_script_docker_call_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "run.sh", "#!/bin/sh\ndocker ps\n")
    found = docker_isolation.run(tmp_path)
    assert len(found) == 1 and "셸" in found[0].message


def test_shell_script_user_docker_dir_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "run.sh", "#!/bin/sh\nexport DOCKER_CONFIG=$HOME/.docker\n")
    assert len(docker_isolation.run(tmp_path)) == 1


def test_extensionless_python_script_is_checked(tmp_path: Path) -> None:
    write(tmp_path, "deploy", '#!/usr/bin/env python3\nimport subprocess\nsubprocess.run(["docker", "ps"])\n')
    assert len(docker_isolation.run(tmp_path)) == 1


HEAD = 'import { spawnSync } from "node:child_process";\n'


def test_js_docker_call_without_env_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "smoke.mjs", HEAD + 'spawnSync("docker", ["ps"], { encoding: "utf8" });\n')
    found = docker_isolation.run(tmp_path)
    assert len(found) == 1 and "env" in found[0].message


def test_js_docker_call_with_env_is_ok(tmp_path: Path) -> None:
    write(tmp_path, "smoke.mjs", HEAD + 'spawnSync("docker", ["ps"], { env, encoding: "utf8" });\n')
    assert docker_isolation.run(tmp_path) == []


def test_js_non_docker_spawn_is_ignored(tmp_path: Path) -> None:
    write(tmp_path, "a.mjs", 'import { spawnSync } from "node:child_process";\nspawnSync("git", ["status"]);\n')
    assert docker_isolation.run(tmp_path) == []


# ---- 이미지 고정 ----
def test_unpinned_from_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "services/a/Dockerfile", "FROM python:3.12-slim\n")
    found = image_pins.run(tmp_path)
    assert len(found) == 1 and "digest" in found[0].message


def test_arg_default_pinned_is_ok(tmp_path: Path) -> None:
    write(tmp_path, "services/a/Dockerfile", f"ARG P=python:3.12@sha256:{D1}\nFROM ${{P}} AS build\nFROM ${{P}}\nCOPY --from=build /a /a\n")
    assert image_pins.run(tmp_path) == []


def test_arg_without_default_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "services/a/Dockerfile", "ARG P\nFROM ${P}\n")
    assert len(image_pins.run(tmp_path)) == 1


def test_different_digests_for_same_image_are_violation(tmp_path: Path) -> None:
    write(tmp_path, "services/a/Dockerfile", f"FROM python:3.12@sha256:{D1}\n")
    write(tmp_path, "services/b/Dockerfile", f"FROM python:3.12@sha256:{D2}\n")
    found = image_pins.run(tmp_path)
    assert len(found) == 1 and "서로 다른" in found[0].message


def test_compose_unpinned_image_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "deploy/compose.yaml", "services:\n  a:\n    image: postgres:16\n")
    assert len(image_pins.run(tmp_path)) == 1


def test_compose_pinned_image_is_ok(tmp_path: Path) -> None:
    write(tmp_path, "deploy/compose.yaml", f"services:\n  a:\n    image: postgres:16@sha256:{D1}\n")
    assert image_pins.run(tmp_path) == []


# ---- bake 대상 ----
BAKE = (
    '// BEGIN SERVICES\nvariable "SERVICES" {\n  default = [%s]\n}\n// END SERVICES\n'
    '// BEGIN JOB_AREAS\nvariable "JOB_AREAS" {\n  default = [%s]\n}\n// END JOB_AREAS\n'
    '// BEGIN WEBS\nvariable "WEBS" {\n  default = [%s]\n}\n// END WEBS\n'
)


def test_bake_matches_folders(tmp_path: Path) -> None:
    write(tmp_path, "docker-bake.hcl", BAKE % ('"a"', "", ""))
    write(tmp_path, "services/a/Dockerfile", "FROM scratch\n")
    assert bake_targets.run(tmp_path) == []


def test_bake_missing_service_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "docker-bake.hcl", BAKE % ("", "", ""))
    write(tmp_path, "services/a/Dockerfile", "FROM scratch\n")
    assert len(bake_targets.run(tmp_path)) == 1


def test_bake_stale_entry_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "docker-bake.hcl", BAKE % ('"gone"', "", ""))
    assert len(bake_targets.run(tmp_path)) == 1


def test_bake_job_areas_match_jobs_folders(tmp_path: Path) -> None:
    write(tmp_path, "docker-bake.hcl", BAKE % ("", '"j"', ""))
    write(tmp_path, "jobs/j/Dockerfile", "FROM scratch\n")
    assert bake_targets.run(tmp_path) == []
    write(tmp_path, "jobs/k/Dockerfile", "FROM scratch\n")
    assert len(bake_targets.run(tmp_path)) == 1


# ---- 영역 경계 ----
def _area(root: Path, name: str, body: str) -> None:
    write(root, f"services/{name}/src/{name}/__init__.py", "")
    write(root, f"services/{name}/src/{name}/main.py", body)


def test_importing_other_area_is_violation(tmp_path: Path) -> None:
    _area(tmp_path, "alpha", "import beta\n")
    _area(tmp_path, "beta", "")
    found = area_isolation.run(tmp_path)
    assert len(found) == 1 and "beta" in found[0].message


def test_from_import_of_other_area_is_violation(tmp_path: Path) -> None:
    _area(tmp_path, "alpha", "from beta.main import x\n")
    _area(tmp_path, "beta", "x = 1\n")
    assert len(area_isolation.run(tmp_path)) == 1


def test_own_package_import_is_ok(tmp_path: Path) -> None:
    _area(tmp_path, "alpha", "from alpha import main\n")
    _area(tmp_path, "beta", "")
    assert area_isolation.run(tmp_path) == []


# ---- Dockerfile 검사: 빌드 검사 래퍼 + hadolint ----
GOOD_DOCKERFILE = "FROM python:3.12-slim-bookworm\nUSER 10001\nCMD [\"python\", \"--version\"]\n"
HADOLINT_CONFIG = "failure-threshold: info\nignored: []\n"


def _lint_tree(tmp_path: Path, deploy_script: str, dockerfile: str = GOOD_DOCKERFILE) -> None:
    write(tmp_path, "deploy/deploy", deploy_script, mode=0o755)
    write(tmp_path, ".hadolint.yaml", HADOLINT_CONFIG)
    write(tmp_path, "services/a/Dockerfile", dockerfile)


def test_dockerfile_lint_reports_failure(tmp_path: Path) -> None:
    _lint_tree(tmp_path, "#!/bin/sh\necho 'bad' >&2\nexit 1\n")
    found = dockerfile_lint.run(tmp_path)
    assert len(found) == 1 and "rc=1" in found[0].message


def test_dockerfile_lint_no_target_is_violation(tmp_path: Path) -> None:
    write(tmp_path, "deploy/deploy", "#!/bin/sh\nexit 3\n", mode=0o755)
    write(tmp_path, ".hadolint.yaml", HADOLINT_CONFIG)
    assert len(dockerfile_lint.run(tmp_path)) == 2  # hadolint 대상 없음 + 빌드 검사 대상 없음


def test_dockerfile_lint_passes_on_rc0(tmp_path: Path) -> None:
    _lint_tree(tmp_path, "#!/bin/sh\nexit 0\n")
    assert dockerfile_lint.run(tmp_path) == []


def test_hadolint_catches_unpinned_latest_tag(tmp_path: Path) -> None:
    _lint_tree(tmp_path, "#!/bin/sh\nexit 0\n", "FROM python:latest\nUSER 10001\n")
    found = dockerfile_lint.run(tmp_path)
    assert found and any("DL3007" in v.message for v in found)


def test_hadolint_runs_shellcheck_on_run_lines(tmp_path: Path) -> None:
    _lint_tree(tmp_path, "#!/bin/sh\nexit 0\n", "FROM python:3.12-slim-bookworm\nRUN cd /tmp && ls $HOME/*.txt | wc -l\nUSER 10001\n")
    found = dockerfile_lint.run(tmp_path)
    assert found and any("SC" in v.message for v in found)


def test_hadolint_requires_config(tmp_path: Path) -> None:
    write(tmp_path, "deploy/deploy", "#!/bin/sh\nexit 0\n", mode=0o755)
    write(tmp_path, "services/a/Dockerfile", GOOD_DOCKERFILE)
    assert any(".hadolint.yaml" in v.where for v in dockerfile_lint.run(tmp_path))
