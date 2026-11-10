"""libs/ 의 공유 라이브러리를 경로 의존으로 쓰는 영역이면, 그 라이브러리가 설치되어 import 되는지 본다(ADR 0020).

경로 의존이 없는 영역에서는 이 시험이 대상 없이 지나간다(파라미터 0개).
"""

import importlib
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _lib_packages() -> list[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    sources = project.get("tool", {}).get("uv", {}).get("sources", {})
    packages: list[str] = []
    for source in sources.values():
        if "path" not in source:
            continue
        lib = tomllib.loads((ROOT / source["path"] / "pyproject.toml").read_text(encoding="utf-8"))
        packages += [Path(p).name for p in lib["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]]
    return packages


@pytest.mark.parametrize("package", _lib_packages())
def test_path_dependency_is_importable(package: str) -> None:
    assert importlib.import_module(package).__name__ == package
