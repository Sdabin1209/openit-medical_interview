"""tools/new-area 와 deploy 명령의 동작 시험."""

import filecmp
import shutil
import subprocess
from pathlib import Path

import pytest

BAKE = (
    '// BEGIN SERVICES\nvariable "SERVICES" {\n  default = []\n}\n// END SERVICES\n'
    '// BEGIN WEBS\nvariable "WEBS" {\n  default = []\n}\n// END WEBS\n'
)


def _sandbox(repo: Path, tmp: Path, name: str) -> Path:
    root = tmp / name
    (root / "templates").mkdir(parents=True)
    for kind in ("service", "web"):
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


@pytest.mark.parametrize("kind", ["service", "web"])
def test_new_area_is_deterministic(repo: Path, tmp_path: Path, kind: str) -> None:
    one, two = _sandbox(repo, tmp_path, "one"), _sandbox(repo, tmp_path, "two")
    folder = "services" if kind == "service" else "web"
    assert _new_area(repo, one, kind, "demo-area").returncode == 0
    assert _new_area(repo, two, kind, "demo-area").returncode == 0
    assert _same_tree(one / folder / "demo-area", two / folder / "demo-area")
    assert (one / "docker-bake.hcl").read_text() == (two / "docker-bake.hcl").read_text()
    assert '"demo-area"' in (one / "docker-bake.hcl").read_text()


def test_new_area_leaves_no_placeholders(repo: Path, tmp_path: Path) -> None:
    root = _sandbox(repo, tmp_path, "r")
    assert _new_area(repo, root, "service", "demo-area").returncode == 0
    for path in (root / "services" / "demo-area").rglob("*"):
        if path.is_file():
            assert "__AREA__" not in path.read_text() and "__PKG__" not in path.read_text(), path
    assert (root / "services/demo-area/src/demo_area/main.py").is_file()


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
    ignore = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "uv.lock"}
    made, kept = root / "services/_example", repo / "services/_example"
    for path in made.rglob("*"):
        if path.is_file() and not ignore & set(path.relative_to(made).parts):
            other = kept / path.relative_to(made)
            assert other.is_file() and other.read_bytes() == path.read_bytes(), path


def _deploy(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(repo / "deploy" / "deploy"), *args], capture_output=True, text=True, check=False)


def test_deploy_job_without_target_is_rc3(repo: Path) -> None:
    result = _deploy(repo, "job", "no-such-job")
    assert result.returncode == 3 and "대상 없음" in result.stderr


def test_deploy_e2e_without_suite_is_rc3(repo: Path) -> None:
    result = _deploy(repo, "e2e")
    assert result.returncode == 3 and "대상 없음" in result.stderr


def test_deploy_restore_requires_yes_and_valid_folder(repo: Path, tmp_path: Path) -> None:
    assert _deploy(repo, "restore", str(tmp_path)).returncode == 1  # 백업 폴더가 아님
    (tmp_path / "owners.json").write_text("{}", encoding="utf-8")
    assert _deploy(repo, "restore", str(tmp_path)).returncode == 2  # --yes 없음


def test_deploy_build_unknown_target_is_rc2(repo: Path) -> None:
    assert _deploy(repo, "build", "no-such-service").returncode == 2


def test_deploy_unknown_command_is_rc2(repo: Path) -> None:
    assert _deploy(repo, "nonsense").returncode == 2
