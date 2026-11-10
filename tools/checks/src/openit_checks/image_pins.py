"""이미지 고정 점검(ADR 0004, 0006): 기반 이미지는 digest 로 고정하고, 같은 이미지는 모든 곳에서 같은 digest 를 쓴다."""

from __future__ import annotations

import re
from pathlib import Path

from .common import Violation, tracked_and_new_files

CHECK = "image-pins"
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
ARG = re.compile(r"^\s*ARG\s+(\w+)=(\S+)")
FROM = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", re.I)
COPY_FROM = re.compile(r"--from=(\S+)")
COMPOSE_IMAGE = re.compile(r"^\s+image:\s*(\S+)")


def _repo(reference: str) -> str:
    return reference.split("@", 1)[0].rsplit(":", 1)[0]


def dockerfile_images(path: Path, display: str) -> tuple[list[tuple[str, str]], list[Violation]]:
    """(위치, 이미지 참조) 목록과 위반. ARG 기본값으로 풀어서 본다."""
    args: dict[str, str] = {}
    stages: set[str] = set()
    refs: list[tuple[str, str]] = []
    violations: list[Violation] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if match := ARG.match(line):
            args[match.group(1)] = match.group(2)
        candidates: list[str] = []
        if match := FROM.match(line):
            candidates.append(match.group(1))
            if match.group(2):
                stages.add(match.group(2))
        candidates += COPY_FROM.findall(line)
        for ref in candidates:
            resolved = re.sub(r"\$\{(\w+)\}", lambda m: args.get(m.group(1), m.group(0)), ref)
            if resolved in stages or resolved == "scratch" or resolved.isdigit():
                continue
            where = f"{display}:{number}"
            if "$" in resolved:
                violations.append(Violation(CHECK, where, f"이미지 참조 '{ref}' 를 ARG 기본값으로 풀 수 없다"))
            elif not DIGEST.search(resolved):
                violations.append(Violation(CHECK, where, f"이미지 '{resolved}' 가 digest 로 고정되지 않았다"))
            else:
                refs.append((where, resolved))
    return refs, violations


def run(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    all_refs: list[tuple[str, str]] = []
    for path in tracked_and_new_files(root):
        rel = str(path.relative_to(root))
        if (path.name == "Dockerfile" and not rel.startswith("templates/")) or (rel.startswith("templates/") and path.name == "Dockerfile"):
            refs, found = dockerfile_images(path, rel)
            all_refs += refs
            violations += found
        elif path.name in {"compose.yaml", "compose.yml"}:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if match := COMPOSE_IMAGE.match(line):
                    ref = match.group(1)
                    if not DIGEST.search(ref):
                        violations.append(Violation(CHECK, f"{rel}:{number}", f"이미지 '{ref}' 가 digest 로 고정되지 않았다"))
                    else:
                        all_refs.append((f"{rel}:{number}", ref))
    by_repo: dict[str, dict[str, str]] = {}
    for where, ref in all_refs:
        by_repo.setdefault(_repo(ref), {}).setdefault(ref, where)
    for repo, variants in by_repo.items():
        if len(variants) > 1:
            detail = "; ".join(f"{where} -> {ref.split('@')[-1][:19]}" for ref, where in variants.items())
            violations.append(Violation(CHECK, repo, f"같은 이미지가 서로 다른 고정값으로 쓰인다: {detail}"))
    return violations
