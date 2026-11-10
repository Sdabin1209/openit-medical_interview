"""bake 대상 점검(ADR 0004): docker-bake.hcl 의 SERVICES·WEBS 목록이 services/·web/ 폴더와 같다.

왜: HCL 에는 폴더 glob 이 없어 목록을 직접 둔다. 폴더와 어긋나면 빌드에서 영역이 조용히 빠지므로 여기서 잡는다.
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import Violation

CHECK = "bake-targets"


def _listed(text: str, var: str) -> set[str] | None:
    block = re.search(rf"// BEGIN {var}\n(.*?)// END {var}\n", text, re.S)
    if not block:
        return None
    default = re.search(r"default\s*=\s*\[(.*?)\]", block.group(1), re.S)
    return set(re.findall(r'"([^"]+)"', default.group(1))) if default else set()


def _folders(root: Path, folder: str) -> set[str]:
    base = root / folder
    if not base.is_dir():
        return set()
    return {p.name for p in base.iterdir() if p.is_dir() and (p / "Dockerfile").is_file()}


def run(root: Path) -> list[Violation]:
    bake = root / "docker-bake.hcl"
    if not bake.is_file():
        return [Violation(CHECK, "docker-bake.hcl", "파일이 없다")]
    text = bake.read_text(encoding="utf-8")
    violations: list[Violation] = []
    for var, folder in (("SERVICES", "services"), ("WEBS", "web")):
        listed = _listed(text, var)
        if listed is None:
            violations.append(Violation(CHECK, "docker-bake.hcl", f"'// BEGIN {var}' 표시가 없다"))
            continue
        actual = _folders(root, folder)
        for name in sorted(actual - listed):
            violations.append(Violation(CHECK, "docker-bake.hcl", f"{folder}/{name} 가 {var} 목록에 없다"))
        for name in sorted(listed - actual):
            violations.append(Violation(CHECK, "docker-bake.hcl", f"{var} 의 '{name}' 에 해당하는 {folder}/{name}/Dockerfile 이 없다"))
    return violations
