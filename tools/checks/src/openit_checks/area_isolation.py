"""영역 경계 점검(ADR 0002): 영역은 다른 영역의 코드를 가져오지 않는다.

영역 안의 import-linter 는 자기 패키지 안만 본다. 이 점검은 리포 전체에서 한 영역의 파이썬 소스가
다른 영역의 최상위 패키지를 import 하는지 본다(영역 패키지는 서로 설치되지 않아 import-linter 로는 못 본다).
"""

from __future__ import annotations

import ast
from pathlib import Path

from .common import Violation

CHECK = "area-isolation"


def _packages(area: Path) -> set[str]:
    src = area / "src"
    return {p.name for p in src.iterdir() if p.is_dir() and (p / "__init__.py").is_file()} if src.is_dir() else set()


def run(root: Path) -> list[Violation]:
    areas = [p for folder in ("services", "jobs") if (root / folder).is_dir() for p in sorted((root / folder).iterdir()) if p.is_dir()]
    owner = {pkg: area for area in areas for pkg in _packages(area)}
    violations: list[Violation] = []
    for area in areas:
        mine = _packages(area)
        for path in sorted((area / "src").rglob("*.py")) + sorted((area / "tests").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    top = name.split(".")[0]
                    if top in owner and top not in mine:
                        where = f"{path.relative_to(root)}:{node.lineno}"
                        violations.append(Violation(CHECK, where, f"다른 영역({owner[top].name})의 패키지 '{top}' 를 import 한다"))
    return violations
