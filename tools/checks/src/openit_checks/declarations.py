"""영역의 선언 파일 점검: jobs.json·exposure.json·inputs.json 이 계약 스키마(JobsDeclaration, Exposure, ContainerInputs)를 지키는지 본다.

왜: 이 파일들이 이미지 라벨 io.openit.jobs·io.openit.exposure·io.openit.inputs 의 원본이고(`deploy build` 가 한 줄 JSON 으로 라벨에 넣는다)
받는 쪽(platform 의 입구 생성기, deploy 의 잡 실행)은 값을 다시 검증하지 않고 계약 모양을 믿는다(R7). 낸 쪽인 영역 리포에서 한 번 검증한다.
검증기는 JSON Schema 2020-12 의 format 단언을 켠다(계약 README: 검증기는 format 단언을 켠다).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .common import Violation

CHECK = "declarations"
SCHEMA_OF = {"jobs.json": "JobsDeclaration", "exposure.json": "Exposure", "inputs.json": "ContainerInputs"}
AREA_FOLDERS = ("services", "jobs", "web")


def _validator(components: dict[str, Any], schema_name: str) -> Draft202012Validator:
    document = {"$schema": "https://json-schema.org/draft/2020-12/schema", "components": components, "$ref": f"#/components/schemas/{schema_name}"}
    return Draft202012Validator(document, format_checker=Draft202012Validator.FORMAT_CHECKER)


def run(root: Path) -> list[Violation]:
    contract = root / "contracts" / "components.yaml"
    if not contract.is_file():
        return []
    components = yaml.safe_load(contract.read_text(encoding="utf-8"))["components"]
    violations: list[Violation] = []
    for folder in AREA_FOLDERS:
        base = root / folder
        for area in sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []:
            for filename, schema in SCHEMA_OF.items():
                path = area / filename
                if not path.is_file():
                    continue
                where = str(path.relative_to(root))
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    violations.append(Violation(CHECK, where, f"JSON 이 아니다: {error}"))
                    continue
                for error in sorted(_validator(components, schema).iter_errors(value), key=lambda e: list(map(str, e.absolute_path))):
                    location = "/".join(map(str, error.absolute_path)) or "(최상위)"
                    violations.append(Violation(CHECK, where, f"{schema} 위반 {location}: {error.message[:200]}"))
    return violations
