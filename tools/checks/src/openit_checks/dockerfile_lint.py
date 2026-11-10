"""Dockerfile 검사: Docker 표준 빌드 검사(`docker buildx bake --check`)를 deploy 명령으로 돌린다(ADR 0004).

hadolint 는 GPL-3.0 이라 쓰지 않는다. docker 호출은 deploy/deploy 가 격리 환경으로 한다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .common import Violation

CHECK = "dockerfile-lint"


def run(root: Path) -> list[Violation]:
    deploy = root / "deploy" / "deploy"
    result = subprocess.run([str(deploy), "build", "--check"], capture_output=True, text=True, check=False)
    if result.returncode == 3:
        return [Violation(CHECK, "services/ web/", "검사할 Dockerfile 이 없다(대상 없음)")]
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip().splitlines()[-6:]
        return [Violation(CHECK, "deploy build --check", f"rc={result.returncode}: " + " | ".join(tail))]
    return []
