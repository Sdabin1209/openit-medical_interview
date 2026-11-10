# license_expression 은 타입 정보가 없는 라이브러리라 그 경계에서만 pyright 의 Unknown 보고를 끈다
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""라이선스 점검(ADR 0017이 ADR 0007을 고친 규칙): 우리 결과물에 의무가 생기지 않게 한다.

- 제품 의존(이미지·배포물에 들어가는 운영 의존)은 허용형(MIT·Apache·BSD 등)만 쓴다. GPL·AGPL·LGPL 이 있으면 실패한다.
  목록에 없거나 알 수 없는 라이선스도 실패한다(놓치는 것보다 낫다). 예외는 license-overrides.toml 에 이유와 함께 적는다.
- 개발 전용 의존(실행만 하고 배포물에 들어가지 않는 도구)은 라이선스와 무관하게 허용한다. 실패시키지 않고 '[보고]' 줄로 알린다.
- 어느 쪽인지는 잠금 파일의 표준 구분으로 정한다: Python 은 uv 의 `--no-dev` 설치에 들어가는 패키지가 제품, 나머지(dev 그룹)는 개발이다.
  npm 은 package-lock.json 의 `dev`(`devOptional` 포함) 표시가 개발이다.
  `tools/` 아래 프로젝트와 PEP 723 스크립트(deploy/deploy)는 배포물이 아니므로 모두 도구다.
- Python: 프로젝트의 uv.lock 대로 설치한 환경을 pip-licenses(MIT)로 읽는다. npm: package-lock.json 의 `license` 칸을 읽는다.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from license_expression import AND, OR, ExpressionError, LicenseSymbol, get_spdx_licensing

from .common import Violation, tracked_and_new_files

CHECK = "licenses"
# 복사 의무(copyleft) 계열. 도구에도 쓰지 않는다(ADR 0001).
COPYLEFT = re.compile(r"(?i)(?:^|[^a-z])(?:a|l)?gpl|gnu\s+(?:general|lesser|affero|library)|affero|\bsspl\b|\bcpal\b|\beupl\b")
# 허용형. 값마다 근거: OSI 승인 허용형 라이선스이며 결과물 배포에 복사 의무가 없다.
PERMISSIVE = re.compile(
    r"(?i)^(?:mit(?:-0|-cmu)?(?: license)?|0bsd|isc(?: license.*)?|zlib|unlicense|cc0-1\.0|blueoak-1\.0\.0|python-2\.0|"
    r"psf-2\.0|python software foundation license|bsd(?:-\d-clause(?:-clear)?)?(?: license)?|apache(?:-2\.0| software license|"
    r" license.*| 2\.0)(?: with .*)?|the unlicense.*|public domain)$"
)


def classify_token(token: str) -> str:
    """'permissive' | 'copyleft' | 'unknown'"""
    text = token.strip().strip("()")
    if not text or text.upper() in {"UNKNOWN", "NONE"}:
        return "unknown"
    if COPYLEFT.search(text):
        return "copyleft"
    if PERMISSIVE.match(text):
        return "permissive"
    return "unknown"


def classify(expression: str) -> str:
    """라이선스 표현식(SPDX 또는 pip-licenses 의 ';' 나열)을 평가한다.

    OR(이중 라이선스)는 하나라도 허용형이면 허용(선택 가능). AND 는 모두 허용형이어야 한다.
    ';' 로 나열된 분류자(classifier)는 선택 가능한 목록으로 보되, 복사 의무와 허용형이 섞이면 사람이 판단하도록 unknown 으로 둔다.
    """
    parts = [p for p in re.split(r"\s*;\s*", expression.strip()) if p]
    if len(parts) > 1:
        kinds = {classify(p) for p in parts}
        if kinds == {"permissive"}:
            return "permissive"
        return "copyleft" if kinds == {"copyleft"} else "unknown"
    try:
        tree: Any = get_spdx_licensing().parse(expression, validate=False)
    except (ExpressionError, ValueError):
        tree = None
    if tree is None:
        return classify_token(expression)
    return _evaluate(tree)


def _evaluate(node: Any) -> str:
    if isinstance(node, OR):
        kinds = [_evaluate(a) for a in node.args]
        if "permissive" in kinds:
            return "permissive"
        return "copyleft" if all(k == "copyleft" for k in kinds) else "unknown"
    if isinstance(node, AND):
        kinds = [_evaluate(a) for a in node.args]
        if "copyleft" in kinds:
            return "copyleft"
        return "permissive" if all(k == "permissive" for k in kinds) else "unknown"
    text = str(node.key if isinstance(node, LicenseSymbol) else node)  # pyright: ignore[reportUnknownMemberType]
    wrapped = getattr(node, "wrapped", None)
    if wrapped is not None and getattr(wrapped, "exception_symbol", None) is not None:
        text = str(getattr(wrapped, "license_symbol", node).key)  # 'X WITH 예외' 는 X 로 판정
    return classify_token(text)


def load_overrides(path: Path) -> dict[tuple[str, str], str]:
    if not path.is_file():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    result: dict[tuple[str, str], str] = {}
    for item in data.get("override", []):
        if not item.get("reason"):
            raise ValueError(f"예외 {item.get('name')} 에 reason 이 없다")
        if classify(item["license"]) == "copyleft":
            raise ValueError(f"예외 {item['name']}: 복사 의무 라이선스는 예외로 허용하지 않는다")
        result[(item["ecosystem"], item["name"])] = item["license"]
    return result


def judge(
    ecosystem: str, where: str, packages: Iterable[tuple[str, str]], overrides: dict[tuple[str, str], str]
) -> list[Violation]:
    violations: list[Violation] = []
    for name, license_text in packages:
        reviewed = (
            eco == ecosystem and fnmatch.fnmatchcase(name, pattern) and lic == license_text
            for (eco, pattern), lic in overrides.items()
        )
        if any(reviewed):
            continue
        kind = classify(license_text)
        if kind == "copyleft":
            violations.append(Violation(CHECK, where, f"{ecosystem} {name}: 복사 의무 라이선스 '{license_text}'"))
        elif kind == "unknown":
            violations.append(
                Violation(CHECK, where, f"{ecosystem} {name}: 허용 목록에 없거나 알 수 없는 라이선스 '{license_text}'")
            )
    return violations


def judge_scoped(
    ecosystem: str,
    where: str,
    product: Iterable[tuple[str, str]],
    dev: Iterable[tuple[str, str]],
    overrides: dict[tuple[str, str], str],
) -> tuple[list[Violation], list[str]]:
    """제품 의존은 위반으로, 개발 의존은 보고 줄로 판정한다(ADR 0017)."""
    violations = judge(ecosystem, where, product, overrides)
    notes = [f"[보고] {v.where} (개발 전용, 실패 아님) {v.message}" for v in judge(ecosystem, where, dev, overrides)]
    return violations, notes


def python_packages(python: Path, exclude: Iterable[str] = ()) -> list[tuple[str, str]]:
    """pip-licenses 로 그 파이썬 환경에 설치된 패키지의 (이름, 라이선스) 를 읽는다."""
    command = [
        sys.executable, "-m", "piplicenses", "--python", str(python), "--format", "json",
        "--with-system", "--from", "mixed",
    ]
    for name in exclude:
        command += ["--ignore-packages", name]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"pip-licenses 실패(rc={result.returncode}): {result.stderr.strip()[-300:]}")
    return [(row["Name"], row["License"]) for row in json.loads(result.stdout)]


def npm_packages(lock: Path, dev: bool | None = None) -> list[tuple[str, str]]:
    """dev=None 이면 전부, True 면 개발 전용(lock 의 dev·devOptional 표시), False 면 제품 의존만."""
    data = json.loads(lock.read_text(encoding="utf-8"))
    packages: list[tuple[str, str]] = []
    for path, info in data.get("packages", {}).items():
        if not path:  # 루트 프로젝트 자신
            continue
        is_dev = bool(info.get("dev") or info.get("devOptional"))
        if dev is not None and is_dev != dev:
            continue
        name = path.rsplit("node_modules/", 1)[-1]
        license_field = info.get("license")
        if isinstance(license_field, dict):  # 옛 형식 {type: ...}
            license_field = license_field.get("type")  # pyright: ignore[reportUnknownMemberType]
        packages.append((name, str(license_field) if license_field else "UNKNOWN"))
    return packages


def _python_projects(root: Path) -> list[Path]:
    return sorted(p.parent for p in tracked_and_new_files(root) if p.name == "uv.lock")


def _project_name(folder: Path) -> str:
    return tomllib.loads((folder / "pyproject.toml").read_text(encoding="utf-8"))["project"]["name"]


def _sync_and_read(folder: Path, groups: list[str], exclude: str) -> tuple[list[tuple[str, str]] | None, str]:
    sync = subprocess.run(["uv", "sync", "--frozen", *groups], cwd=folder, capture_output=True, text=True, check=False)
    if sync.returncode != 0:
        return None, f"uv sync --frozen {' '.join(groups)} 실패: {sync.stderr.strip()[-200:]}"
    return python_packages(folder / ".venv" / "bin" / "python", exclude=[exclude]), ""


def run(root: Path) -> list[Violation]:
    overrides = load_overrides(Path(__file__).resolve().parents[2] / "license-overrides.toml")
    violations: list[Violation] = []
    seen = 0
    for folder in _python_projects(root):
        where = str(folder.relative_to(root))
        is_tool = folder.relative_to(root).parts[0] == "tools"  # 왜: tools/ 는 점검·보조 도구라 배포물에 들어가지 않는다
        name = _project_name(folder)
        product, error = _sync_and_read(folder, ["--no-dev"], name)
        if product is None:
            violations.append(Violation(CHECK, where, error))
            continue
        full, error = _sync_and_read(folder, ["--all-groups"], name)  # 마지막에 개발 환경으로 되돌려 둔다
        if full is None:
            violations.append(Violation(CHECK, where, error))
            continue
        seen += len(full)
        product_names = {n for n, _ in product}
        product_rows = [] if is_tool else product
        dev_rows = [row for row in full if is_tool or row[0] not in product_names]
        found, notes = judge_scoped("python", where, product_rows, dev_rows, overrides)
        violations += found
        _announce(notes)
    for script_lock in sorted(p for p in tracked_and_new_files(root) if p.suffix == ".lock" and _is_pep723_script(p.with_suffix(""))):
        # PEP 723 스크립트(deploy/deploy)의 잠금 파일: uv 가 만든 스크립트 환경을 읽는다. 배포 도구라 개발 전용으로 본다
        script = script_lock.with_suffix("")
        found_python = subprocess.run(["uv", "python", "find", "--script", str(script)], capture_output=True, text=True, check=False)
        if found_python.returncode != 0:
            violations.append(Violation(CHECK, str(script.relative_to(root)), "스크립트 환경을 찾지 못했다"))
            continue
        packages = python_packages(Path(found_python.stdout.strip()))
        seen += len(packages)
        found, notes = judge_scoped("python", str(script.relative_to(root)), [], packages, overrides)
        violations += found
        _announce(notes)
    for lock in sorted(p for p in tracked_and_new_files(root) if p.name == "package-lock.json"):
        where = str(lock.relative_to(root))
        everything = npm_packages(lock)
        seen += len(everything)
        found, notes = judge_scoped("npm", where, npm_packages(lock, dev=False), npm_packages(lock, dev=True), overrides)
        violations += found
        _announce(notes)
    if seen == 0:
        violations.append(Violation(CHECK, str(root), "읽은 패키지가 하나도 없다. 잠금 파일이 없으면 점검이 비어 성공하므로 실패로 본다"))
    return violations


def _is_pep723_script(path: Path) -> bool:
    """`# /// script` 블록(PEP 723)이 있는 파일만 uv 스크립트다. 같은 이름의 .lock(예: tools/web-e2e.lock)은 다른 용도일 수 있다."""
    return path.is_file() and "# /// script" in path.read_text(encoding="utf-8", errors="ignore")


def _announce(notes: list[str]) -> None:
    for note in notes:
        print(note, file=sys.stderr)
