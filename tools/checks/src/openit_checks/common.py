"""점검 공통: 위반 모양과 리포 파일 열거."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Violation:
    check: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.check}] {self.where}: {self.message}"


def tracked_and_new_files(root: Path) -> list[Path]:
    """git 이 추적하거나 (제외 규칙에 안 걸린) 새 파일. git 리포가 아니면 폴더를 훑는다(시험 fixture)."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return [root / line for line in result.stdout.splitlines() if (root / line).is_file()]
    skip = {"node_modules", ".venv", ".git"}
    return [p for p in sorted(root.rglob("*")) if p.is_file() and not skip & set(p.relative_to(root).parts)]
