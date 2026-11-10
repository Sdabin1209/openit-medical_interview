"""라이선스 점검이 위반을 실제로 잡는지 본다."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from openit_checks import licenses
from openit_checks.cli import main

from .conftest_helpers import write


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT", "permissive"),
        ("MIT License", "permissive"),
        ("BSD-3-Clause", "permissive"),
        ("BSD License", "permissive"),
        ("Apache-2.0", "permissive"),
        ("Apache Software License", "permissive"),
        ("Apache-2.0 WITH LLVM-exception", "permissive"),
        ("ISC", "permissive"),
        ("MIT OR GPL-3.0-only", "permissive"),  # 이중 라이선스: 허용형을 고를 수 있다
        ("GPL-3.0-only", "copyleft"),
        ("GPL-2.0-or-later", "copyleft"),
        ("AGPL-3.0-only", "copyleft"),
        ("LGPL-3.0-or-later", "copyleft"),
        ("GNU Lesser General Public License v3 (LGPLv3)", "copyleft"),
        ("GNU General Public License v3 (GPLv3)", "copyleft"),
        ("MIT AND GPL-3.0-only", "copyleft"),  # AND 는 둘 다 지켜야 한다
        ("MIT License; GNU General Public License v3 (GPLv3)", "unknown"),  # 섞이면 사람이 판단
        ("UNKNOWN", "unknown"),
        ("Mozilla Public License 2.0 (MPL 2.0)", "unknown"),
        ("Proprietary", "unknown"),
    ],
)
def test_classify(text: str, expected: str) -> None:
    assert licenses.classify(text) == expected


def test_npm_lock_with_gpl_is_violation(tmp_path: Path) -> None:
    lock = {
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "root"},
            "node_modules/good": {"version": "1.0.0", "license": "MIT"},
            "node_modules/bad": {"version": "1.0.0", "license": "GPL-3.0"},
            "node_modules/a/node_modules/bad2": {"version": "1.0.0", "license": "AGPL-3.0-only"},
            "node_modules/nolicense": {"version": "1.0.0"},
        },
    }
    path = write(tmp_path, "package-lock.json", json.dumps(lock))
    violations = licenses.judge("npm", "x", licenses.npm_packages(path), {})
    names = {v.message.split(":")[0] for v in violations}
    assert names == {"npm bad", "npm bad2", "npm nolicense"}


def test_npm_lock_clean_is_ok(tmp_path: Path) -> None:
    lock = {"packages": {"": {}, "node_modules/a": {"license": "MIT"}, "node_modules/b": {"license": "(MIT OR Apache-2.0)"}}}
    path = write(tmp_path, "package-lock.json", json.dumps(lock))
    assert licenses.judge("npm", "x", licenses.npm_packages(path), {}) == []


def test_override_cannot_allow_copyleft(tmp_path: Path) -> None:
    path = write(tmp_path, "o.toml", '[[override]]\necosystem="npm"\nname="x"\nlicense="GPL-3.0"\nreason="r"\n')
    with pytest.raises(ValueError, match="복사 의무"):
        licenses.load_overrides(path)


def test_override_needs_reason(tmp_path: Path) -> None:
    path = write(tmp_path, "o.toml", '[[override]]\necosystem="npm"\nname="x"\nlicense="MPL-2.0"\nreason=""\n')
    with pytest.raises(ValueError, match="reason"):
        licenses.load_overrides(path)


def test_override_allows_reviewed_unknown() -> None:
    overrides = {("npm", "x"): "MPL-2.0"}
    assert licenses.judge("npm", "w", [("x", "MPL-2.0")], overrides) == []
    assert licenses.judge("npm", "w", [("x", "GPL-3.0")], overrides) != []  # 라이선스가 바뀌면 예외가 풀린다


def test_override_pattern_matches_platform_packages() -> None:
    overrides = {("npm", "lightningcss*"): "MPL-2.0"}
    pkgs = [("lightningcss", "MPL-2.0"), ("lightningcss-linux-x64-gnu", "MPL-2.0"), ("other", "MPL-2.0")]
    assert [v.message.split(":")[0] for v in licenses.judge("npm", "w", pkgs, overrides)] == ["npm other"]


def test_python_environment_with_gpl_package_is_caught(tmp_path: Path) -> None:
    """실제 pip-licenses 로 가짜 GPL 패키지가 든 가상환경을 읽는다."""
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    site = next((venv / "lib").glob("python*/site-packages"))
    for name, meta in (("fakegpl", "License-Expression: GPL-3.0-only"), ("fakemit", "License-Expression: MIT")):
        info = site / f"{name}-1.0.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(f"Metadata-Version: 2.4\nName: {name}\nVersion: 1.0\n{meta}\n", encoding="utf-8")
    packages = licenses.python_packages(venv / "bin" / "python")
    violations = licenses.judge("python", "fixture", packages, {})
    assert [v.message.split(":")[0] for v in violations] == ["python fakegpl"]


def test_run_fails_when_no_packages_found(tmp_path: Path) -> None:
    violations = licenses.run(tmp_path)
    assert len(violations) == 1
    assert "하나도 없다" in violations[0].message


def test_cli_rc_is_1_on_violation(tmp_path: Path) -> None:
    write(tmp_path, "package-lock.json", json.dumps({"packages": {"": {}, "node_modules/bad": {"license": "GPL-3.0"}}}))
    assert main(["licenses", "--root", str(tmp_path)]) == 1


def test_cli_rc_is_0_when_clean(tmp_path: Path) -> None:
    write(tmp_path, "package-lock.json", json.dumps({"packages": {"": {}, "node_modules/ok": {"license": "MIT"}}}))
    assert main(["licenses", "--root", str(tmp_path)]) == 0


# ---- 제품 의존과 개발 전용 의존(ADR 0017) ----
def test_product_gpl_fails_but_dev_tool_gpl_passes() -> None:
    packages = [("copyleft-lib", "GPL-3.0-only")]
    product_violations, product_notes = licenses.judge_scoped("python", "svc", packages, [], {})
    assert [v.message for v in product_violations] == ["python copyleft-lib: 복사 의무 라이선스 'GPL-3.0-only'"]
    assert product_notes == []
    dev_violations, dev_notes = licenses.judge_scoped("python", "svc", [], packages, {})
    assert dev_violations == []  # 실행만 하는 도구는 라이선스와 무관하게 통과
    assert len(dev_notes) == 1 and dev_notes[0].startswith("[보고]") and "개발 전용" in dev_notes[0]


def test_npm_dev_flag_splits_product_and_dev(tmp_path: Path) -> None:
    lock = {
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "root"},
            "node_modules/runtime": {"version": "1.0.0", "license": "MIT"},
            "node_modules/tool": {"version": "1.0.0", "license": "GPL-3.0", "dev": True},
            "node_modules/maybe": {"version": "1.0.0", "license": "AGPL-3.0-only", "devOptional": True},
        },
    }
    path = write(tmp_path, "package-lock.json", json.dumps(lock))
    assert [n for n, _ in licenses.npm_packages(path, dev=False)] == ["runtime"]
    assert sorted(n for n, _ in licenses.npm_packages(path, dev=True)) == ["maybe", "tool"]
    violations, notes = licenses.judge_scoped("npm", "x", licenses.npm_packages(path, dev=False), licenses.npm_packages(path, dev=True), {})
    assert violations == [] and len(notes) == 2


def test_own_packages_are_path_sources_from_the_lock(tmp_path: Path) -> None:
    """영역 자신과 libs/ 의 경로 의존은 우리 코드라 라이선스 점검 대상이 아니다(ADR 0020)."""
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "openit-area"\nsource = { editable = "." }\n\n'
        '[[package]]\nname = "openit-model-io"\nsource = { directory = "../../libs/model-io" }\n\n'
        '[[package]]\nname = "pydantic"\nsource = { registry = "https://pypi.org/simple" }\n',
        encoding="utf-8",
    )
    assert licenses.own_packages(tmp_path) == ["openit-area", "openit_area", "openit-model-io", "openit_model_io"]
