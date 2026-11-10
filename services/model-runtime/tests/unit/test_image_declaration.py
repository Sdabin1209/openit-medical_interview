"""이미지가 영역 밖에서 주입받는 것의 선언(계약 ContainerInputs, D134).

inputs.json 과 Dockerfile 라벨과 계약이 같은 말을 한다.
"""

import json
import re
from pathlib import Path

from model_runtime.contract.models import ContainerInputs, ModelRuntimeEnv

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
DECLARED = json.loads((ROOT / "inputs.json").read_text(encoding="utf-8"))


def test_declaration_is_a_valid_container_inputs() -> None:
    ContainerInputs.model_validate(DECLARED)


def test_label_is_the_declaration() -> None:
    match = re.search(r"io\.openit\.inputs='(.*)'", DOCKERFILE)
    assert match and json.loads(match.group(1)) == DECLARED


def test_env_declaration_matches_the_contract_env_inputs() -> None:
    declared = {item["name"]: item["required"] for item in DECLARED["env"]}
    contract = {name: field.is_required() for name, field in ModelRuntimeEnv.model_fields.items()}
    assert declared == contract


def test_secret_inputs_are_files_and_the_entry_point_is_declared_as_cmd() -> None:
    kinds = {item["name"]: item["kind"] for item in DECLARED["env"]}
    assert kinds["OPENIT_TLS_PRIVATE_KEY_FILE"] == kinds["OPENIT_REGISTRY_CREDENTIALS_FILE"] == "SECRET_FILE"
    assert all(kind != "VALUE" for name, kind in kinds.items() if name.endswith("_FILE"))
    cmd = re.search(r"^CMD (\[.*\])$", DOCKERFILE, re.M)
    assert cmd and json.loads(cmd.group(1)) == DECLARED["processes"][0]["argv"]
    assert DECLARED["run_as_uid"] == 10001 and "USER 10001:10001" in DOCKERFILE
