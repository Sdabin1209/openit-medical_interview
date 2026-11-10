"""tools/new-area 와 deploy 명령의 동작 시험."""

import filecmp
import shutil
import subprocess
from pathlib import Path

import pytest

BAKE = (
    '// BEGIN SERVICES\nvariable "SERVICES" {\n  default = []\n}\n// END SERVICES\n'
    '// BEGIN JOB_AREAS\nvariable "JOB_AREAS" {\n  default = []\n}\n// END JOB_AREAS\n'
    '// BEGIN WEBS\nvariable "WEBS" {\n  default = []\n}\n// END WEBS\n'
)


def _sandbox(repo: Path, tmp: Path, name: str) -> Path:
    root = tmp / name
    (root / "templates").mkdir(parents=True)
    for kind in ("service", "job", "lib", "web"):
        if (repo / "templates" / kind).is_dir():
            skip = shutil.ignore_patterns("node_modules", ".venv", "dist")
            shutil.copytree(repo / "templates" / kind, root / "templates" / kind, ignore=skip)
    (root / "docker-bake.hcl").write_text(BAKE, encoding="utf-8")
    return root


def _new_area(repo: Path, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(repo / "tools" / "new-area"), *args, "--no-lock", "--root", str(root)], capture_output=True, text=True, check=False
    )


def _same_tree(a: Path, b: Path) -> bool:
    cmp = filecmp.dircmp(a, b)
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return False
    return all(_same_tree(a / d, b / d) for d in cmp.common_dirs)


FOLDERS = {"service": "services", "job": "jobs", "lib": "libs", "web": "web"}


@pytest.mark.parametrize("kind", ["service", "job", "lib", "web"])
def test_new_area_is_deterministic(repo: Path, tmp_path: Path, kind: str) -> None:
    one, two = _sandbox(repo, tmp_path, "one"), _sandbox(repo, tmp_path, "two")
    folder = FOLDERS[kind]
    assert _new_area(repo, one, kind, "demo-area").returncode == 0
    assert _new_area(repo, two, kind, "demo-area").returncode == 0
    assert _same_tree(one / folder / "demo-area", two / folder / "demo-area")
    assert (one / "docker-bake.hcl").read_text() == (two / "docker-bake.hcl").read_text()
    # 왜: lib 는 이미지가 없어 bake 목록에 들어가지 않는다
    assert ('"demo-area"' in (one / "docker-bake.hcl").read_text()) == (kind != "lib")


def test_new_area_job_goes_to_job_areas_list(repo: Path, tmp_path: Path) -> None:
    root = _sandbox(repo, tmp_path, "r")
    assert _new_area(repo, root, "job", "demo-job").returncode == 0
    bake = (root / "docker-bake.hcl").read_text()
    assert 'variable "JOB_AREAS" {\n  default = ["demo-job"]' in bake
    assert 'variable "SERVICES" {\n  default = []' in bake


def test_new_area_lib_and_openapi_options_are_checked(repo: Path, tmp_path: Path) -> None:
    root = _sandbox(repo, tmp_path, "r")
    assert _new_area(repo, root, "lib", "demo-lib", "--lib", "x").returncode == 2  # lib 에는 --lib 가 없다
    assert _new_area(repo, root, "job", "demo-job", "--openapi", "platform").returncode == 2  # job 에는 --openapi 가 없다
    assert _new_area(repo, root, "service", "demo", "--lib", "no-such-lib").returncode == 2  # 없는 라이브러리


@pytest.mark.parametrize("kind", ["service", "job", "lib", "web"])
def test_new_area_leaves_no_placeholders(repo: Path, tmp_path: Path, kind: str) -> None:
    root = _sandbox(repo, tmp_path, "r")
    assert _new_area(repo, root, kind, "demo-area").returncode == 0
    for path in (root / FOLDERS[kind] / "demo-area").rglob("*"):
        if path.is_file():
            text = path.read_text()
            assert "__AREA__" not in text and "__PKG__" not in text and "__SERVICE_NAME__" not in text, path
    if kind != "web":
        assert (root / FOLDERS[kind] / "demo-area/src/demo_area/__init__.py").is_file()


def test_new_area_refuses_existing_and_bad_names(repo: Path, tmp_path: Path) -> None:
    root = _sandbox(repo, tmp_path, "r")
    assert _new_area(repo, root, "service", "demo").returncode == 0
    assert _new_area(repo, root, "service", "demo").returncode == 1
    assert _new_area(repo, root, "service", "Bad_Name").returncode == 2


def test_new_area_adds_names_sorted_without_duplicates(repo: Path, tmp_path: Path) -> None:
    root = _sandbox(repo, tmp_path, "r")
    for name in ("zeta", "alpha"):
        assert _new_area(repo, root, "service", name).returncode == 0
    assert 'default = ["alpha", "zeta"]' in (root / "docker-bake.hcl").read_text()


def test_example_service_matches_template(repo: Path, tmp_path: Path) -> None:
    """services/_example 은 템플릿에서 나온 그대로다(uv.lock 과 생성 환경 제외). 템플릿이 바뀌면 다시 만든다."""
    root = _sandbox(repo, tmp_path, "r")
    assert _new_area(repo, root, "service", "_example").returncode == 0
    ignore = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".import_linter_cache", "uv.lock"}
    made, kept = root / "services/_example", repo / "services/_example"
    for path in made.rglob("*"):
        if path.is_file() and not ignore & set(path.relative_to(made).parts):
            other = kept / path.relative_to(made)
            if path.name == "pyproject.toml":
                # 왜: _example 은 `--lib model-io` 로 만든다. uv add 가 더한 경로 의존(의존 한 줄과 sources 표)을 빼고 견준다
                text = other.read_text(encoding="utf-8").replace('  "openit-model-io",\n', "")
                text = text.replace('\n[tool.uv.sources]\nopenit-model-io = { path = "../../libs/model-io" }\n', "")
                assert text == path.read_text(encoding="utf-8"), path
                continue
            assert other.is_file() and other.read_bytes() == path.read_bytes(), path


def test_example_job_matches_template(repo: Path, tmp_path: Path) -> None:
    """jobs/_example-job 은 템플릿에서 나온 그대로다(uv.lock 과 생성 환경 제외)."""
    root = _sandbox(repo, tmp_path, "r")
    assert _new_area(repo, root, "job", "_example-job").returncode == 0
    ignore = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".import_linter_cache", "uv.lock"}
    made, kept = root / "jobs/_example-job", repo / "jobs/_example-job"
    for path in made.rglob("*"):
        if path.is_file() and not ignore & set(path.relative_to(made).parts):
            other = kept / path.relative_to(made)
            assert other.is_file() and other.read_bytes() == path.read_bytes(), path


def test_example_web_matches_template(repo: Path, tmp_path: Path) -> None:
    """web/_example 은 템플릿에서 나온 그대로다(package-lock.json 과 설치·빌드 산출물 제외)."""
    root = _sandbox(repo, tmp_path, "r")
    assert _new_area(repo, root, "web", "_example").returncode == 0
    ignore = {"node_modules", "dist", "test-results", "playwright-report", "package-lock.json"}
    made, kept = root / "web/_example", repo / "web/_example"
    for path in made.rglob("*"):
        if path.is_file() and not ignore & set(path.relative_to(made).parts):
            other = kept / path.relative_to(made)
            assert other.is_file() and other.read_bytes() == path.read_bytes(), path


def _deploy(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(repo / "deploy" / "deploy"), *args], capture_output=True, text=True, check=False)


def test_deploy_job_without_target_is_rc3(repo: Path) -> None:
    result = _deploy(repo, "job", "no-such-job")
    assert result.returncode == 3 and "대상 없음" in result.stderr


def test_deploy_e2e_usage_errors_are_rc2_before_anything_starts(repo: Path) -> None:
    """E2E 는 ADR 0025 로 구현되었다. 실제로 돌리지 않고(몇십 분, docker·GPU) 인자 오류가 아무것도 시작하기 전에 rc=2 로 끝나는 것만 본다."""
    assert _deploy(repo, "e2e").returncode == 2  # --mode 가 필요하다
    assert _deploy(repo, "e2e", "--mode", "full").returncode == 2  # pipeline 또는 product
    product = _deploy(repo, "e2e", "--mode", "product")  # 어댑터와 프로파일이 필요하다(도구가 거절한다)
    assert product.returncode == 2 and "--adapters-a" in product.stderr


def test_deploy_restore_requires_yes_before_touching_anything(repo: Path) -> None:
    """복구는 덮어쓴다: --yes 가 없으면 저장소에 닿기 전에 rc=2 이고 잡 결과도 내지 않는다(사용법 오류, ADR 0027)."""
    result = _deploy(repo, "restore", "latest")
    assert result.returncode == 2 and "--yes" in result.stderr and result.stdout.strip() == ""


def test_deploy_backup_commands_exist_and_take_their_options(repo: Path) -> None:
    for words, option in ((["backup"], None), (["offsite-sync"], None), (["restore-test"], "--offsite"), (["restore"], "--offsite")):
        result = _deploy(repo, *words, "--help")
        assert result.returncode == 0 and (option is None or option in result.stdout), words


def test_deploy_build_unknown_target_is_rc2(repo: Path) -> None:
    assert _deploy(repo, "build", "no-such-service").returncode == 2


def test_deploy_unknown_command_is_rc2(repo: Path) -> None:
    assert _deploy(repo, "nonsense").returncode == 2
