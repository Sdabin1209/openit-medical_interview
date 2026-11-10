"""docker 설정 격리 점검(ADR 0004): 모든 docker 호출은 격리된 환경으로 나간다.

- Python: argv 가 "docker" 로 시작하는 subprocess 호출은 `env=` 를 반드시 준다(없으면 사용자 ~/.docker 를 쓴다).
- 사용자 전역 설정(~/.docker) 을 가리키는 코드·설정이 없다.
- 셸 스크립트에는 docker 호출이 없다(호출은 deploy/deploy 를 지난다).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .common import Violation, tracked_and_new_files

CHECK = "docker-isolation"
SUBPROCESS_FUNCS = {"run", "call", "check_call", "check_output", "Popen"}
# 문자열 값이 사용자 설정 폴더로 시작하는 경우만 본다(설명 글 속의 언급은 위반이 아니다)
USER_DOCKER_DIR = re.compile(r"^(?:~|\$HOME|\$\{HOME\}|/home/[^/\s]+|/root)/\.docker(?:/|$)")
SHELL_USER_DOCKER_DIR = re.compile(r"(?:~|\$HOME|\$\{HOME\})/\.docker\b")
CODE_SUFFIXES = {".py", ".sh", ".yaml", ".yml", ".hcl", ".toml", ".mjs", ".ts", ".js"}
SELF_DIR = ("tools", "checks")  # 이 점검의 정의·시험은 금지 패턴을 문자열로 담는다


def _starts_with_docker(node: ast.expr) -> bool:
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        first = node.elts[0]
        return isinstance(first, ast.Constant) and first.value == "docker"
    return False


def _is_subprocess_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in SUBPROCESS_FUNCS:
        return isinstance(func.value, ast.Name) and func.value.id == "subprocess"
    return False


def check_python(path: Path, display: str) -> list[Violation]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as error:
        return [Violation(CHECK, display, f"파싱 실패: {error}")]
    found: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and USER_DOCKER_DIR.match(node.value):
            found.append(Violation(CHECK, f"{display}:{node.lineno}", "사용자 전역 .docker 폴더를 가리킨다"))
        is_docker_call = isinstance(node, ast.Call) and _is_subprocess_call(node) and node.args and _starts_with_docker(node.args[0])
        if is_docker_call and isinstance(node, ast.Call) and not any(k.arg == "env" for k in node.keywords):
            found.append(Violation(CHECK, f"{display}:{node.lineno}", "docker 호출에 env= 가 없다(격리 환경을 넘기지 않음)"))
    return found


def run(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in tracked_and_new_files(root):
        rel = path.relative_to(root)
        if rel.parts[: len(SELF_DIR)] == SELF_DIR:
            continue
        display = str(rel)
        is_shell = path.suffix == ".sh"
        is_python = path.suffix == ".py" or (path.suffix == "" and _has_python_shebang(path))
        if is_python:
            violations += check_python(path, display)
        if path.suffix in CODE_SUFFIXES or path.suffix == "" or path.name == "Dockerfile":
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if not is_python and not line.lstrip().startswith("#") and SHELL_USER_DOCKER_DIR.search(line):
                    violations.append(Violation(CHECK, f"{display}:{number}", "사용자 전역 ~/.docker 를 가리킨다"))
                if is_shell and re.match(r"\s*(?:sudo\s+)?docker\s", line):
                    violations.append(Violation(CHECK, f"{display}:{number}", "셸 스크립트의 docker 호출(deploy/deploy 를 쓴다)"))
    return violations


def _has_python_shebang(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            first = handle.readline(200)
    except OSError:
        return False
    return first.startswith(b"#!") and (b"python" in first or b"uv run" in first)
