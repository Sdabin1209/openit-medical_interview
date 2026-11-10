"""이미지가 영역 밖에서 주입받는 것과 영역 밖에 내보내는 것의 선언(계약 ContainerInputs, Exposure, D134).

원본은 영역 폴더의 inputs.json 과 exposure.json 이다. Dockerfile 은 `ARG INPUTS`, `ARG EXPOSURE` 로 받아 라벨로 달고(deploy build 가
파일을 한 줄 JSON 으로 넘긴다) 원본 내용을 글자 그대로 복사하지 않는다. 이 영역에는 잡이 없어 JOBS 가 없다.
"""

import json
import re
from pathlib import Path

import pytest
import yaml

from model_runtime.contract.models import ContainerInputs, Exposure, ModelRuntimeEnv

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT.parents[1] / "contracts"
DOCKERFILE = "\n".join(  # 주석은 뺀다(주석이 이유를 설명하며 같은 낱말을 쓴다)
    line for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")
)
DECLARED = json.loads((ROOT / "inputs.json").read_text(encoding="utf-8"))
EXPOSURE = json.loads((ROOT / "exposure.json").read_text(encoding="utf-8"))
SCHEME_OF = {
    "HUMAN_OIDC": "oidc",
    "MACHINE_TOKEN": "machine_token",
}  # 계약 securitySchemes 이름(platform gateway.py 의 SCHEME_OF 와 같다)
HEALTH = {"/healthz", "/readyz", "/metrics"}


def operations() -> list[tuple[str, str, list[dict[str, list[str]]]]]:
    spec = yaml.safe_load((CONTRACTS / "openapi" / "model-runtime.yaml").read_text(encoding="utf-8"))
    return [
        (path, method.upper(), item.get("security", []))
        for path, methods in spec["paths"].items()
        for method, item in methods.items()
        if isinstance(item, dict) and path not in HEALTH
    ]


def under(prefix: str, path: str) -> bool:
    base = prefix.rstrip("/")
    return path == base or path.startswith(base + "/")


def test_declarations_are_valid_contract_values() -> None:
    ContainerInputs.model_validate(DECLARED)
    Exposure.model_validate(EXPOSURE)


def test_labels_are_build_arguments_not_copies() -> None:
    assert re.search(r"^ARG INPUTS$", DOCKERFILE, re.M) and re.search(r"^ARG EXPOSURE$", DOCKERFILE, re.M)
    assert 'io.openit.inputs="${INPUTS}"' in DOCKERFILE and 'io.openit.exposure="${EXPOSURE}"' in DOCKERFILE
    assert "io.openit.jobs" not in DOCKERFILE and "ARG JOBS" not in DOCKERFILE  # 잡이 없다
    assert not (ROOT / "jobs.json").exists()
    assert '"run_as_uid"' not in DOCKERFILE  # 원본 파일의 내용을 Dockerfile 에 복사하지 않는다


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


def test_healthcheck_is_the_listen_port_over_plain_http() -> None:
    """서비스는 TLS 를 끝내지 않는다(계약 9.0.0). 건강 확인은 OPENIT_LISTEN_PORT 의 /healthz 하나다."""
    check = re.search(r"^HEALTHCHECK .*\n\s*CMD .*$", DOCKERFILE, re.M)
    assert check and "OPENIT_LISTEN_PORT" in check.group(0) and "/healthz" in check.group(0)
    assert "https" not in check.group(0) and "18081" not in DOCKERFILE and not re.search(r"^EXPOSE\b", DOCKERFILE, re.M)


def test_the_adapter_folder_is_under_the_declared_writable_path() -> None:
    """엔진 컨테이너가 같은 경로로 읽기 전용 마운트하는 폴더가 이 영역이 쓰는 경로다(ADR 0006, 계약 ModelRuntimeEnv 설명)."""
    paths = {item["path"]: item["persistent"] for item in DECLARED["writable_paths"]}
    assert paths == {"/var/lib/openit/model-runtime": True}
    assert "/var/lib/openit/model-runtime" in DOCKERFILE


@pytest.mark.parametrize(("path", "method", "security"), operations())
def test_every_operation_is_exposed_to_exactly_the_audiences_its_security_allows(
    path: str, method: str, security: list[dict[str, list[str]]]
) -> None:
    """작업 security 와 노출 선언이 맞는다(platform 은 노출 선언 x 작업 security 로 라우트를 만든다)."""
    opened = {
        route["audience"]
        for route in EXPOSURE["routes"]
        if under(route["path_prefix"], path) and method in route["methods"]
    }
    allowed = {
        audience for audience, scheme in SCHEME_OF.items() if any(scheme in alternative for alternative in security)
    }
    assert opened == allowed, f"{method} {path}: 노출 {sorted(opened)} 허용 {sorted(allowed)}"


def test_every_route_opens_at_least_one_operation() -> None:
    """허용 작업이 없는 접두어는 platform 이 시작하지 않는다."""
    for route in EXPOSURE["routes"]:
        scheme = SCHEME_OF[route["audience"]]
        assert any(
            under(route["path_prefix"], path) and method in route["methods"] and any(scheme in alt for alt in security)
            for path, method, security in operations()
        ), route


def test_egress_is_the_token_issuer_only_and_the_registry_is_not_a_service_name() -> None:
    assert EXPOSURE["egress"] == ["platform"]
