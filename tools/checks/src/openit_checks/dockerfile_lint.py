"""Dockerfile 검사(ADR 0016): Docker 표준 빌드 검사(`docker buildx bake --check`)와 hadolint(ShellCheck 포함)를 모두 돌린다.

- 빌드 검사: deploy 명령이 격리된 docker 환경으로 돌린다(ADR 0004, 0009).
- hadolint: Dockerfile 작성 규칙과 RUN 줄의 셸 명령(ShellCheck)을 본다. 개발·점검에서 실행만 하는 도구이며 이미지에 들어가지 않는다(ADR 0017).
  모든 Dockerfile(templates/, services/, web/, deploy/)이 대상이다. 규칙 설정은 리포 루트의 `.hadolint.yaml`이다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .common import Violation, tracked_and_new_files

CHECK = "dockerfile-lint"


def dockerfiles(root: Path) -> list[Path]:
    return sorted(p for p in tracked_and_new_files(root) if p.name == "Dockerfile")


def hadolint(root: Path) -> list[Violation]:
    files = dockerfiles(root)
    if not files:
        return [Violation(CHECK, "hadolint", "검사할 Dockerfile 이 없다(대상 없음)")]
    config = root / ".hadolint.yaml"
    if not config.is_file():
        return [Violation(CHECK, ".hadolint.yaml", "hadolint 설정 파일이 없다")]
    binary = Path(sys.executable).parent / "hadolint"  # 왜: 이 환경(uv.lock)이 설치한 공식 바이너리만 쓴다
    if not binary.is_file():
        return [Violation(CHECK, "hadolint", "hadolint 가 설치되지 않았다(cd tools/checks && uv sync)")]
    violations: list[Violation] = []
    for path in files:
        result = subprocess.run(  # noqa: S603
            [str(binary), "--config", str(config), "--no-color", str(path)], capture_output=True, text=True, check=False, cwd=root
        )
        if result.returncode != 0:
            for line in (result.stdout + result.stderr).strip().splitlines():
                violations.append(Violation(CHECK, str(path.relative_to(root)), f"hadolint: {line}"))
    return violations


def run(root: Path) -> list[Violation]:
    violations = hadolint(root)
    deploy = root / "deploy" / "deploy"
    result = subprocess.run([str(deploy), "build", "--check"], capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode == 3:
        return [*violations, Violation(CHECK, "services/ web/", "검사할 Dockerfile 이 없다(대상 없음)")]
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip().splitlines()[-6:]
        violations.append(Violation(CHECK, "deploy build --check", f"rc={result.returncode}: " + " | ".join(tail)))
    return violations
