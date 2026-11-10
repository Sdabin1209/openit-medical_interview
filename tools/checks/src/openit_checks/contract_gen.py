"""계약에서 Pydantic v2 모델을 만든다(ADR 0020). 같은 계약이면 같은 생성물이다.

입력: 영역(서비스·잡·라이브러리) 폴더의 `pyproject.toml` 의 `[tool.openit.contract]`.
    openapi = ["platform"]    # contracts/openapi/<이름>.yaml 의 작업이 쓰는 스키마를 모두 가져온다(선택)
    schemas = ["JobRunResult"]  # components.yaml 에서 이름으로 더 가져올 스키마(선택. openapi 가 없는 영역은 이것만 쓴다)
출력: src/<패키지>/contract/models.py. 이 파일은 손으로 고치지 않는다.

왜 이름 목록인가: 영역은 자기가 쓰는 계약만 안다(구조 규칙 4). components.yaml 전체를 모든 영역에 넣지 않는다.
왜 x- 확장을 지우나: x-enum-descriptions 등은 계약 린트용 주석이고 생성기는 이를 다른 뜻(목록)으로 읽어 실패한다.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from .common import Violation

CHECK = "contract-drift"
MODELS_FILE = "models.py"
HEADER = (
    "# 이 파일은 openit-gen-contract 가 contracts/ 에서 생성했다. 손으로 고치지 않는다(ADR 0020).\n"
    "# 다시 만들기: uv run --project tools/checks openit-gen-contract <영역 폴더>"
)
# 왜 이 옵션들: pydantic v2 모델, 제약(maxLength 등)은 Field 의 인자로, 시각은 시간대 있는 값(RFC 3339), 열거는 문자열 열거
GENERATOR_ARGS = [
    "--input-file-type", "openapi",
    "--openapi-scopes", "schemas",
    "--output-model-type", "pydantic_v2.BaseModel",
    "--target-python-version", "3.12",
    "--use-annotated", "--field-constraints", "--use-standard-collections", "--use-union-operator",
    "--use-schema-description", "--use-field-description", "--use-subclass-enum",
    "--output-datetime-class", "AwareDatetime",
    "--disable-timestamp", "--formatters", "builtin",
]  # fmt: skip
# 왜 10종: OpenAPI 3.1.0 4.8.7 Components Object 가 정한 종류 전부. 스키마가 아닌 종류(securitySchemes 등)도 참조를 따라가야 한다
REF = re.compile(
    r"^(?P<file>[^#]*)#/components/"
    r"(?P<kind>schemas|responses|parameters|examples|requestBodies|headers|securitySchemes|links|callbacks|pathItems)/(?P<name>[^/]+)$"
)


class ContractGenError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    openapi: tuple[str, ...]
    schemas: tuple[str, ...]


def read_config(folder: Path) -> Config | None:
    pyproject = folder / "pyproject.toml"
    if not pyproject.is_file():
        return None
    table = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("tool", {}).get("openit", {}).get("contract")
    if table is None:
        return None
    unknown = set(table) - {"openapi", "schemas"}
    if unknown:
        raise ContractGenError(f"{pyproject}: [tool.openit.contract] 에 알 수 없는 칸 {sorted(unknown)}")
    config = Config(tuple(table.get("openapi", [])), tuple(table.get("schemas", [])))
    return config


def package_dir(folder: Path) -> Path:
    packages = sorted(p for p in (folder / "src").iterdir() if p.is_dir() and (p / "__init__.py").is_file())
    if len(packages) != 1:
        raise ContractGenError(f"{folder}: src/ 아래 패키지가 하나여야 한다(찾은 수 {len(packages)})")
    return packages[0]


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractGenError(f"계약 파일이 없다: {path}")
    return cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))


def _refs(node: Any) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in cast("dict[str, Any]", node).items():
            if key == "$ref" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_refs(value))
    elif isinstance(node, list):
        for item in cast("list[Any]", node):
            found.extend(_refs(item))
    return found


def _strip_extensions(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip_extensions(v) for k, v in cast("dict[str, Any]", node).items() if not str(k).startswith("x-")}
    if isinstance(node, list):
        return [_strip_extensions(v) for v in cast("list[Any]", node)]
    return node


def collect_schema_names(contracts: Path, config: Config) -> list[str]:
    """openapi 의 작업이 닿는 스키마와 이름으로 준 스키마, 그리고 그것들이 참조하는 스키마 전부(정렬)."""
    components = _load(contracts / "components.yaml")["components"]
    pending: list[tuple[str, str]] = [("schemas", name) for name in config.schemas]
    for name in config.openapi:
        spec = _load(contracts / "openapi" / f"{name}.yaml")
        for ref in _refs(spec):
            match = REF.match(ref)
            if match is None:
                raise ContractGenError(f"openapi/{name}.yaml: 해석할 수 없는 $ref '{ref}'")
            if match["file"] not in ("", "../components.yaml"):
                raise ContractGenError(f"openapi/{name}.yaml: 계약 밖 파일을 참조한다 '{ref}'")
            pending.append((match["kind"], match["name"]))
    schemas: set[str] = set()
    seen: set[tuple[str, str]] = set()
    while pending:
        kind, name = pending.pop()
        if (kind, name) in seen:
            continue
        seen.add((kind, name))
        definition = components.get(kind, {}).get(name)
        if definition is None:
            raise ContractGenError(f"components.yaml 에 {kind}/{name} 이 없다")
        if kind == "schemas":
            schemas.add(name)
        for ref in _refs(definition):
            match = REF.match(ref)
            if match is None or match["file"] != "":
                raise ContractGenError(f"components.yaml {kind}/{name}: 해석할 수 없는 $ref '{ref}'")
            pending.append((match["kind"], match["name"]))
    return sorted(schemas)


def build_document(contracts: Path, config: Config) -> dict[str, Any]:
    components = _load(contracts / "components.yaml")["components"]["schemas"]
    names = collect_schema_names(contracts, config)
    return {
        "openapi": "3.1.0",
        "info": {"title": "openit contract subset", "version": "0"},
        "paths": {},
        "components": {"schemas": {n: _strip_extensions(components[n]) for n in names}},
    }


def generate_models(contracts: Path, config: Config) -> str:
    if not config.openapi and not config.schemas:
        return f'{HEADER}\n\n"""계약에서 쓰는 스키마가 아직 없다. pyproject.toml 의 [tool.openit.contract] schemas 에 이름을 쓴다."""\n'
    document = build_document(contracts, config)
    with tempfile.TemporaryDirectory(prefix="openit-gen-contract-") as tmp:
        source, target = Path(tmp) / "contract.yaml", Path(tmp) / MODELS_FILE
        source.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=True), encoding="utf-8")
        command = [
            sys.executable, "-m", "datamodel_code_generator", "--input", str(source), "--output", str(target),
            "--custom-file-header", HEADER, *GENERATOR_ARGS,
        ]  # fmt: skip
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not target.is_file():
            raise ContractGenError(f"datamodel-codegen 실패(rc={result.returncode}): {result.stderr.strip()[-500:]}")
        return target.read_text(encoding="utf-8")


def target_path(folder: Path) -> Path:
    return package_dir(folder) / "contract" / MODELS_FILE


def contract_folders(root: Path) -> list[Path]:
    """계약 설정이 있는 파이썬 영역(서비스, 잡, 라이브러리와 그 템플릿) 폴더."""
    found: list[Path] = []
    for group in ("services", "jobs", "libs", "templates"):
        base = root / group
        if base.is_dir():
            found += [p for p in sorted(base.iterdir()) if p.is_dir() and read_config(p) is not None]
    return found


def run(root: Path) -> list[Violation]:
    """생성물이 계약에서 다시 만든 결과와 같은지 본다. 파이썬 영역은 생성기로, 화면 영역은 openapi-typescript --check 로 본다."""
    return [*python_drift(root), *_web_drift(root)]


def python_drift(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    contracts = root / "contracts"
    for folder in contract_folders(root):
        where = str(folder.relative_to(root))
        try:
            config = read_config(folder)
            if config is None:  # contract_folders 가 설정 있는 폴더만 주므로 여기 오지 않는다
                continue
            expected = generate_models(contracts, config)
            path = target_path(folder)
        except ContractGenError as error:
            violations.append(Violation(CHECK, where, str(error)))
            continue
        if not path.is_file():
            violations.append(Violation(CHECK, where, f"{path.relative_to(root)} 가 없다. openit-gen-contract 로 만든다"))
        elif path.read_text(encoding="utf-8") != expected:
            message = f"{path.relative_to(root)} 가 계약에서 다시 만든 결과와 다르다. openit-gen-contract 로 다시 만든다"
            violations.append(Violation(CHECK, where, message))
    return violations


def _web_drift(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    base = root / "web"
    for folder in sorted(p for p in base.iterdir() if p.is_dir() and (p / "package.json").is_file()) if base.is_dir() else []:
        where = str(folder.relative_to(root))
        if not (folder / "node_modules" / ".bin" / "openapi-typescript").is_file():
            violations.append(Violation(CHECK, where, "openapi-typescript 가 설치되어 있지 않다(npm ci 를 먼저 한다)"))
            continue
        result = subprocess.run(["npm", "run", "--silent", "check:contract"], cwd=folder, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[-300:]
            message = f"src/contract 가 계약에서 다시 만든 결과와 다르다. npm run generate:contract 로 다시 만든다: {detail}"
            violations.append(Violation(CHECK, where, message))
    return violations


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="openit-gen-contract", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folders", nargs="*", type=Path, help="영역 폴더(없으면 계약 설정이 있는 모든 영역)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args(argv)
    folders = [f.resolve() for f in args.folders] or contract_folders(args.root)
    for folder in folders:
        config = read_config(folder)
        if config is None:
            print(f"오류: {folder} 에 [tool.openit.contract] 가 없다", file=sys.stderr)
            return 2
        try:
            text = generate_models(args.root / "contracts", config)
            path = target_path(folder)
        except ContractGenError as error:
            print(f"오류: {error}", file=sys.stderr)
            return 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"만들었다: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
