"""제3자 고지(THIRD_PARTY_NOTICES) 생성과 점검(ADR 0018).

허용형 라이선스(MIT·BSD·Apache-2.0·ISC 등)는 배포물에 저작권 표시와 라이선스 전문(Apache-2.0 은 NOTICE 도)을 함께 주라고 요구한다.
이 모듈은 잠금 파일에서 '실제 이미지에 들어가는 제품 의존'만 골라 고지 파일을 만들고, 이미지의 고지가 잠금 파일과 같은지 점검한다.

- 제품 의존의 기준은 licenses.py 와 같다(ADR 0017): Python 은 `uv sync --frozen --no-dev`(Dockerfile 이 하는 설치 그대로),
  npm 은 package-lock.json 의 dev·devOptional 표시가 없는 패키지(`npm ci --omit=dev`).
- 패키지 이름·버전·라이선스 식별자·저자·주소는 표준 메타데이터에서 읽는다(Python: pip-licenses, npm: package-lock.json).
  라이선스 전문과 NOTICE 는 설치된 패키지 폴더의 파일에서 읽는다(pip-licenses 는 파일을 하나만 주므로, ADR 0018).
- 같은 잠금 파일이면 같은 결과다: 정렬을 고정하고 시각·경로·환경 값을 넣지 않는다.
"""

from __future__ import annotations

import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from .common import Violation

CHECK = "notices"
NOTICES_FILE = "THIRD_PARTY_NOTICES"
# 왜 이 경로: FHS 의 문서 폴더(/usr/share/doc/<패키지>)가 배포물의 라이선스 문서를 두는 표준 위치다(Debian 정책도 같다)
DOC_PATH = "/usr/share/doc/openit/THIRD_PARTY_NOTICES"
# 왜 화면은 한 곳 더: 번들된 JavaScript 는 브라우저(받는 사람)에게 배포된다. 같은 서버에서 받아 볼 수 있어야 고지가 전달된다
WEB_PUBLIC_PATH = "/usr/share/nginx/html/THIRD_PARTY_NOTICES.txt"
IMAGE_PATHS: dict[str, tuple[str, ...]] = {"service": (DOC_PATH,), "web": (DOC_PATH, WEB_PUBLIC_PATH)}
KIND_FOLDERS = {"service": "services", "web": "web"}

# 라이선스·NOTICE 파일 이름(npm 의 license-checker 와 pip-licenses 가 쓰는 관례와 같은 계열)
LICENSE_NAME = re.compile(r"(?i)^(?:licen[sc]e|licen[sc]ing|copying|copyright|notice|unlicense)(?:[-._].*)?$")
# 저작권 표시 줄: 'Copyright' 뒤에 (c)·© 가 오거나 연도가 있는 줄.
# 라이선스 본문의 문장('copyright license to ...', 'Copyright [yyyy] [name ...]' 틀, 'copyright notice that ...')과 구분하려는 조건이다
COPYRIGHT_LINE = re.compile(r"(?i)^\W*(?:copyright\s*(?:\(c\)|©)|©|copyright\b.*\b(?:19|20)\d{2}\b)")
PROJECT_SOURCES = {"editable", "virtual", "directory", "path"}  # uv.lock 에서 우리 코드인 출처(제3자가 아니다)


OVERRIDES_PATH = Path(__file__).resolve().parents[2] / "notices-overrides.toml"


class NoticesError(RuntimeError):
    """고지를 만들지 못했다(라이선스 전문이 없는 패키지 등). 메시지에 어느 패키지인지 적는다."""


@dataclass(frozen=True)
class SourceFile:
    name: str
    text: str


@dataclass(frozen=True)
class Entry:
    name: str
    version: str
    license: str
    url: str
    authors: str
    licenses: tuple[SourceFile, ...]
    notices: tuple[SourceFile, ...]


def _clean(text: str) -> str:
    """줄바꿈만 통일한다. 내용은 원문 그대로 둔다(끝의 빈 줄만 정리)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"


def _known(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.upper() in {"UNKNOWN", "NONE"} else text


def copyright_lines(entry: Entry) -> list[str]:
    seen: list[str] = []
    for source in (*entry.licenses, *entry.notices):
        for line in source.text.splitlines():
            stripped = line.strip()
            if COPYRIGHT_LINE.match(stripped) and stripped not in seen:
                seen.append(stripped)
    return seen


def collect_files(files: Iterable[tuple[str, Path]]) -> tuple[tuple[SourceFile, ...], tuple[SourceFile, ...]]:
    """(표시 이름, 경로) 목록에서 라이선스 전문과 NOTICE 를 가른다. 같은 내용의 중복은 한 번만 넣는다."""
    licenses: list[SourceFile] = []
    notices: list[SourceFile] = []
    seen: set[str] = set()
    for name, path in sorted(files, key=lambda item: item[0]):
        text = _clean(path.read_text(encoding="utf-8", errors="replace"))
        if text.strip() == "" or text in seen:
            continue
        seen.add(text)
        base = name.rsplit("/", 1)[-1].lower()
        (notices if base.startswith("notice") else licenses).append(SourceFile(name, text))
    return tuple(licenses), tuple(notices)


def load_text_overrides(path: Path) -> dict[tuple[str, str, str], str]:
    """(생태계, 이름, 라이선스 식별자) -> 대체 전문. reason 과 text 가 없는 항목은 거부한다."""
    if not path.is_file():
        return {}
    result: dict[tuple[str, str, str], str] = {}
    for item in tomllib.loads(path.read_text(encoding="utf-8")).get("text", []):
        if not item.get("reason") or not str(item.get("text", "")).strip():
            raise ValueError(f"대체 전문 {item.get('name')} 에 reason 또는 text 가 없다")
        result[(item["ecosystem"], item["name"], item["license"])] = _clean(item["text"])
    return result


def _with_override(
    ecosystem: str, name: str, license_id: str, licenses: tuple[SourceFile, ...], overrides: dict[tuple[str, str, str], str]
) -> tuple[SourceFile, ...]:
    if licenses or (ecosystem, name, license_id) not in overrides:
        return licenses
    return (SourceFile("notices-overrides.toml 의 대체 전문(패키지에 파일이 없다)", overrides[(ecosystem, name, license_id)]),)


def render(ecosystem: str, lock_name: str, entries: Iterable[Entry]) -> str:
    """고지 파일의 본문. 정렬은 (이름 소문자, 버전)으로 고정한다."""
    ordered = sorted(entries, key=lambda e: (e.name.lower(), e.version))
    rule = "=" * 80
    lines = [
        "THIRD_PARTY_NOTICES",
        "",
        f"이 이미지에 들어가는 제3자 소프트웨어({ecosystem} 제품 의존)의 이름, 버전, 라이선스, 저작권 표시, 라이선스 전문이다.",
        f"{lock_name} 에서 `openit-notices generate` 가 만든다. 직접 고치지 않는다.",
        "",
        f"패키지 {len(ordered)}개",
        *[f"- {e.name} {e.version} ({e.license})" for e in ordered],
    ]
    for entry in ordered:
        lines += ["", rule, f"{entry.name} {entry.version}", rule, f"라이선스: {entry.license}"]
        if entry.url:
            lines.append(f"주소: {entry.url}")
        marks = copyright_lines(entry)
        if marks:
            lines += ["저작권:", *[f"  {m}" for m in marks]]
        else:
            lines.append(f"저작권: 라이선스 파일에 연도가 있는 저작권 표시가 없다. 저자(패키지 메타데이터): {entry.authors or '없음'}")
        for source in entry.licenses:
            lines += ["", f"--- 라이선스 전문 ({source.name}) ---", source.text.rstrip("\n")]
        for source in entry.notices:
            lines += ["", f"--- NOTICE ({source.name}) ---", source.text.rstrip("\n")]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- Python


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _own_python_packages(lock: Path) -> set[str]:
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    own: set[str] = set()
    for package in data.get("package", []):
        if PROJECT_SOURCES & set(package.get("source", {})):
            own.add(_normalize(package["name"]))
    return own


def _dist_info(site: Path, name: str, version: str) -> Path | None:
    for candidate in sorted(site.glob("*.dist-info")):
        stem = candidate.name.removesuffix(".dist-info")
        dist_name, _, dist_version = stem.rpartition("-")
        if _normalize(dist_name) == _normalize(name) and dist_version == version:
            return candidate
    return None


def _python_files(dist: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    licenses_dir = dist / "licenses"  # PEP 639: 메타데이터의 License-File 이 가리키는 파일이 여기에 들어간다
    if licenses_dir.is_dir():
        found += [(path.relative_to(licenses_dir).as_posix(), path) for path in licenses_dir.rglob("*") if path.is_file()]
    found += [(path.name, path) for path in dist.iterdir() if path.is_file() and LICENSE_NAME.match(path.name)]  # 옛 방식(PEP 639 이전)
    return found


def _piplicenses(python: Path) -> list[dict[str, Any]]:
    command = [
        sys.executable, "-m", "piplicenses", "--python", str(python), "--format", "json",
        "--with-system", "--from", "mixed", "--with-authors", "--with-urls",
    ]  # fmt: skip
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise NoticesError(f"pip-licenses 실패(rc={result.returncode}): {result.stderr.strip()[-300:]}")
    return json.loads(result.stdout)


def python_entries(area: Path, overrides: dict[tuple[str, str, str], str]) -> list[Entry]:
    """uv.lock 대로 `--no-dev` 로 설치한 임시 환경(이미지와 같은 설치)에서 제품 의존의 고지 재료를 읽는다."""
    own = _own_python_packages(area / "uv.lock")
    with tempfile.TemporaryDirectory(prefix="openit-notices-") as tmp:
        env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(Path(tmp) / "venv")}
        sync = subprocess.run(
            ["uv", "sync", "--frozen", "--no-dev", "--no-install-project"], cwd=area, env=env, capture_output=True, text=True, check=False
        )
        if sync.returncode != 0:
            raise NoticesError(f"uv sync --frozen --no-dev 실패(rc={sync.returncode}): {sync.stderr.strip()[-300:]}")
        python = Path(tmp) / "venv" / "bin" / "python"
        sites = sorted((Path(tmp) / "venv" / "lib").glob("python*/site-packages"))
        if not sites:
            raise NoticesError("설치한 환경에서 site-packages 를 찾지 못했다")
        return python_entries_from(_piplicenses(python), sites[0], own, overrides)


def python_entries_from(
    rows: Iterable[dict[str, Any]], site: Path, own: set[str], overrides: dict[tuple[str, str, str], str]
) -> list[Entry]:
    """pip-licenses 가 읽은 행과 설치된 site-packages 에서 항목을 만든다. 우리 코드(own)는 뺀다."""
    entries: list[Entry] = []
    problems: list[str] = []
    for row in rows:
        name, version = str(row["Name"]), str(row["Version"])
        if _normalize(name) in own:
            continue
        dist = _dist_info(site, name, version)
        licenses, notices = collect_files(_python_files(dist)) if dist else ((), ())
        license_id = _known(row["License"]) or "UNKNOWN"
        licenses = _with_override("python", name, license_id, licenses, overrides)
        if not licenses:
            problems.append(f"python {name} {version}: 라이선스 전문 파일이 패키지에 없다")
            continue
        entries.append(Entry(name, version, license_id, _known(row.get("URL")), _known(row.get("Author")), licenses, notices))
    if problems:
        raise NoticesError("\n".join(problems))
    return entries


# ---------------------------------------------------------------- npm


def npm_product_paths(lock: Path) -> dict[str, dict[str, Any]]:
    """package-lock.json 에서 개발 전용이 아닌 패키지(경로 -> 정보)."""
    data = json.loads(lock.read_text(encoding="utf-8"))
    return {
        path: info
        for path, info in data.get("packages", {}).items()
        if path and not (info.get("dev") or info.get("devOptional")) and not info.get("link")
    }


def _field(value: object, key: str) -> str:
    """npm 메타데이터의 칸은 문자열이거나 {<key>: 문자열} 객체다(옛 형식)."""
    if isinstance(value, dict):
        return str(cast("dict[str, Any]", value).get(key, ""))
    return str(value or "")


def _npm_license(info: dict[str, Any]) -> str:
    return _known(_field(info.get("license"), "type")) or "UNKNOWN"


def npm_entries(area: Path, overrides: dict[tuple[str, str, str], str]) -> list[Entry]:
    """`npm ci --omit=dev` 로 설치한 임시 트리에서 제품 의존의 고지 재료를 읽는다."""
    product = npm_product_paths(area / "package-lock.json")
    with tempfile.TemporaryDirectory(prefix="openit-notices-") as tmp:
        work = Path(tmp)
        for name in ("package.json", "package-lock.json"):
            shutil.copy2(area / name, work / name)
        # 왜 --ignore-scripts: 설치 스크립트를 실행하지 않는다(고지에 필요한 것은 파일뿐이다)
        install = subprocess.run(
            ["npm", "ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=work, capture_output=True, text=True, check=False,
        )  # fmt: skip
        if install.returncode != 0:
            raise NoticesError(f"npm ci --omit=dev 실패(rc={install.returncode}): {install.stderr.strip()[-300:]}")
        return npm_entries_from(work, product, overrides)


def npm_entries_from(tree: Path, product: dict[str, dict[str, Any]], overrides: dict[tuple[str, str, str], str]) -> list[Entry]:
    """설치된 트리(tree/node_modules/...)에서 제품 의존(잠금 파일의 경로 -> 정보)의 항목을 만든다."""
    entries: dict[tuple[str, str], Entry] = {}
    problems: list[str] = []
    for path, info in sorted(product.items()):
        folder = tree / path
        name = path.rsplit("node_modules/", 1)[-1]
        version = str(info.get("version", ""))
        if not folder.is_dir():
            problems.append(f"npm {name} {version}: 설치된 폴더가 없다(플랫폼 전용 선택 의존이면 잠금 파일의 os·cpu 를 확인한다)")
            continue
        licenses, notices = collect_files((p.name, p) for p in folder.iterdir() if p.is_file() and LICENSE_NAME.match(p.name))
        license_id = _npm_license(info)
        licenses = _with_override("npm", name, license_id, licenses, overrides)
        if not licenses:
            problems.append(f"npm {name} {version}: 라이선스 전문 파일이 패키지에 없다")
            continue
        meta: dict[str, Any] = json.loads((folder / "package.json").read_text(encoding="utf-8"))
        url = _field(meta.get("repository"), "url")
        entries[(name, version)] = Entry(
            name, version, license_id, _known(url) or _known(meta.get("homepage")), _field(meta.get("author"), "name"), licenses, notices
        )
    if problems:
        raise NoticesError("\n".join(problems))
    return list(entries.values())


# ---------------------------------------------------------------- 영역 단위


def lock_of(area: Path) -> tuple[str, str] | None:
    """(생태계, 잠금 파일 이름). 잠금 파일이 없으면 None."""
    if (area / "uv.lock").is_file():
        return "python", "uv.lock"
    if (area / "package-lock.json").is_file():
        return "npm", "package-lock.json"
    return None


def generate(area: Path, overrides: dict[tuple[str, str, str], str] | None = None) -> str:
    found = lock_of(area)
    if found is None:
        raise NoticesError(f"{area.name}: 잠금 파일(uv.lock, package-lock.json)이 없다")
    ecosystem, lock_name = found
    texts = load_text_overrides(OVERRIDES_PATH) if overrides is None else overrides
    entries = python_entries(area, texts) if ecosystem == "python" else npm_entries(area, texts)
    if not entries:
        raise NoticesError(f"{area.name}: 제품 의존이 하나도 없다. 이미지가 의존 없이 서는지 확인한다")
    return render(ecosystem, lock_name, entries)


def area_folders(root: Path) -> list[tuple[str, Path]]:
    """(종류, 폴더). Dockerfile 이 있는 서비스·화면 영역."""
    found: list[tuple[str, Path]] = []
    for kind, folder in KIND_FOLDERS.items():
        base = root / folder
        if base.is_dir():
            found += [(kind, p) for p in sorted(base.iterdir()) if p.is_dir() and (p / "Dockerfile").is_file()]
    return found


def kind_of(root: Path, area: Path) -> str:
    for kind, folder in KIND_FOLDERS.items():
        if area.resolve().parent == (root / folder).resolve():
            return kind
    raise NoticesError(f"{area}: services/ 나 web/ 아래 영역이 아니다")


def _package_lines(text: str) -> set[str]:
    """머리말의 패키지 목록('- 이름 버전 (라이선스)' 줄들). 라이선스 전문 속의 목록 줄은 세지 않는다."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("패키지 ")), len(lines)) + 1
    found: list[str] = []
    for line in lines[start:]:
        if not line.startswith("- "):
            break
        found.append(line)
    return set(found)


def dockerfile_violations(dockerfile: Path, kind: str, where: str) -> list[Violation]:
    """마지막 단계(runtime)가 고지 파일을 이미지 안 정해진 경로로 복사하는지 본다."""
    text = dockerfile.read_text(encoding="utf-8")
    last_stage = re.split(r"(?mi)^FROM\b", text)[-1]
    copies = {
        match.group(1)
        for match in re.finditer(rf"(?mi)^\s*COPY\s+(?:--\S+\s+)*{NOTICES_FILE}\s+(\S+)\s*$", last_stage)
    }
    return [
        Violation(CHECK, where, f"Dockerfile 의 마지막 단계에 `COPY {NOTICES_FILE} {path}` 가 없다")
        for path in IMAGE_PATHS[kind]
        if path not in copies
    ]


def dockerignore_violations(area: Path, where: str) -> list[Violation]:
    ignore = area / ".dockerignore"
    if not ignore.is_file():
        return []
    for raw in ignore.read_text(encoding="utf-8").splitlines():
        pattern = raw.strip().lstrip("/")
        if pattern and not pattern.startswith(("#", "!")) and fnmatch.fnmatchcase(NOTICES_FILE, pattern.rstrip("/")):
            return [Violation(CHECK, where, f".dockerignore 의 '{raw.strip()}' 가 {NOTICES_FILE} 를 빌드 컨텍스트에서 뺀다")]
    return []


def verify_area(root: Path, kind: str, area: Path) -> list[Violation]:
    """고지 파일이 있고, 잠금 파일에서 다시 만든 것과 같고, Dockerfile 이 이미지에 넣는지 본다."""
    where = str(area.relative_to(root)) if area.is_relative_to(root) else str(area)
    violations = dockerfile_violations(area / "Dockerfile", kind, f"{where}/Dockerfile") + dockerignore_violations(area, where)
    if lock_of(area) is None:
        return [*violations, Violation(CHECK, where, "잠금 파일(uv.lock, package-lock.json)이 없어 고지를 만들 수 없다")]
    committed = area / NOTICES_FILE
    if not committed.is_file():
        return [*violations, Violation(CHECK, where, f"{NOTICES_FILE} 가 없다. `openit-notices generate {where}` 로 만든다")]
    try:
        expected = generate(area)
    except NoticesError as error:
        return [*violations, *[Violation(CHECK, where, line) for line in str(error).splitlines()]]
    actual = committed.read_text(encoding="utf-8")
    if actual != expected:
        added = sorted(_package_lines(expected) - _package_lines(actual))
        removed = sorted(_package_lines(actual) - _package_lines(expected))
        detail = "패키지 목록은 같고 본문이 다르다"
        if added or removed:
            detail = f"잠금 파일에만 있음 {len(added)}개, 고지에만 있음 {len(removed)}개"
        fix = f"`openit-notices generate {where}` 로 다시 만든다"
        violations.append(Violation(CHECK, where, f"{NOTICES_FILE} 가 잠금 파일과 어긋난다({detail}). {fix}"))
    return violations


def run(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for kind, area in area_folders(root):
        violations += verify_area(root, kind, area)
    for kind in KIND_FOLDERS:  # 템플릿에서 나온 영역이 처음부터 고지를 이미지에 넣게 한다
        dockerfile = root / "templates" / kind / "Dockerfile"
        if dockerfile.is_file():
            violations += dockerfile_violations(dockerfile, kind, f"templates/{kind}/Dockerfile")
    return violations


# ---------------------------------------------------------------- 이미지


def _load_dockerenv(root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("openit_dockerenv", root / "deploy" / "dockerenv.py")
    if spec is None or spec.loader is None:
        raise NoticesError("deploy/dockerenv.py 를 읽지 못했다")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_from_image(root: Path, image: str, paths: Iterable[str], into: Path) -> dict[str, Path]:
    """이미지를 실행하지 않고(docker create + cp) 파일을 꺼낸다. docker 환경은 deploy/dockerenv.py 의 격리 설정이다."""
    dockerenv = _load_dockerenv(root)
    container = f"openit-notices-{uuid.uuid4().hex[:12]}"
    created = dockerenv.run_docker(["create", "--name", container, image], capture_output=True)
    if created.returncode != 0:
        raise NoticesError(f"docker create {image} 실패: {created.stderr.strip()[-300:]}")
    try:
        out: dict[str, Path] = {}
        for index, path in enumerate(paths):
            target = into / str(index)
            copied = dockerenv.run_docker(["cp", f"{container}:{path}", str(target)], capture_output=True)
            if copied.returncode != 0:
                raise NoticesError(f"이미지 {image} 에 {path} 가 없다")
            out[path] = target
        return out
    finally:
        dockerenv.run_docker(["rm", "-f", container], capture_output=True)


def verify_image(root: Path, area: Path, image: str) -> list[Violation]:
    """이미지 안의 고지가 영역의 고지(잠금 파일에서 만든 것)와 바이트까지 같은지 본다."""
    kind = kind_of(root, area)
    where = f"{area.relative_to(root)} ({image})"
    violations = verify_area(root, kind, area)
    if violations:
        return violations
    expected = (area / NOTICES_FILE).read_bytes()
    with tempfile.TemporaryDirectory(prefix="openit-notices-") as tmp:
        try:
            files = extract_from_image(root, image, IMAGE_PATHS[kind], Path(tmp))
        except NoticesError as error:
            return [Violation(CHECK, where, str(error))]
        for path, local in files.items():
            if local.read_bytes() != expected:
                digest = hashlib.sha256(local.read_bytes()).hexdigest()[:12]
                violations.append(Violation(CHECK, where, f"이미지의 {path} 가 잠금 파일에서 만든 고지와 다르다(sha256 {digest}...)"))
    return violations
