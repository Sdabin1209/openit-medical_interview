"""이미지 선언(jobs.json, exposure.json, inputs.json): 계약 스키마로 검증되고 서로·코드와 어긋나지 않는다(ADR 0016).

라벨 io.openit.jobs·exposure·inputs 의 원본은 이 파일들이다. Dockerfile 은 값을 복사하지 않고 빌드 인자로 받는다.
"""

import json
import re
from pathlib import Path
from typing import Any

import yaml

from survey_service.contract.models import (
    ContainerInputs,
    Exposure,
    ExposureAudience,
    JobName,
    JobsDeclaration,
    SurveyServiceEnv,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT.parents[1] / "contracts"
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")


def load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def schemas() -> dict[str, Any]:
    return yaml.safe_load((CONTRACTS / "components.yaml").read_text(encoding="utf-8"))["components"]["schemas"]


def test_the_three_files_are_valid_contract_values() -> None:
    JobsDeclaration.model_validate(load("jobs.json"))
    Exposure.model_validate(load("exposure.json"))
    ContainerInputs.model_validate(load("inputs.json"))


def test_dockerfile_takes_the_declarations_as_build_arguments_and_does_not_copy_them() -> None:
    for name, label in (("JOBS", "jobs"), ("EXPOSURE", "exposure"), ("INPUTS", "inputs")):
        assert re.search(rf"^ARG {name}$", DOCKERFILE, re.M)
        assert f'io.openit.{label}="${{{name}}}"' in DOCKERFILE
    assert '"run_as_uid"' not in DOCKERFILE and '"routes"' not in DOCKERFILE and '"timeout_seconds"' not in DOCKERFILE


def test_env_declaration_is_the_env_schema() -> None:
    """이름, 필수 여부, 종류(비밀 파일, 설정 파일, 값)가 Env 스키마의 칸과 같다."""
    declared = {item["name"]: item for item in load("inputs.json")["env"]}
    spec = schemas()["SurveyServiceEnv"]
    kinds = {"SecretFilePath": "SECRET_FILE", "ConfigFilePath": "FILE_PATH"}
    expected = {
        name: {
            "name": name,
            "kind": kinds.get(prop["$ref"].rsplit("/", 1)[1], "VALUE"),
            "required": name in SurveyServiceEnv.model_fields and SurveyServiceEnv.model_fields[name].is_required(),
        }
        for name, prop in spec["properties"].items()
    }
    assert declared == expected
    assert set(declared) == set(SurveyServiceEnv.model_fields)
    assert all(item["kind"] == "SECRET_FILE" for name, item in declared.items() if name.endswith("_SECRET_FILE"))


def test_processes_are_the_image_entry_and_the_job_commands() -> None:
    declared = load("inputs.json")
    jobs = {item["job"] for item in load("jobs.json")["jobs"]}
    by_job = {p.get("job"): p["argv"] for p in declared["processes"]}
    assert jobs == {JobName.DETECT_FAILURES.value, JobName.PURGE_EXPIRED.value} == {j for j in by_job if j}
    assert all(argv[0].startswith("/") for argv in by_job.values())
    # 서비스 진입점은 Dockerfile 의 CMD 와 같다
    cmd = re.search(r"^CMD (\[.*\])$", DOCKERFILE, re.M)
    assert cmd and json.loads(cmd.group(1)) == by_job[None]
    # 잡은 `python -m survey_service.jobs <잡>` 이고 deploy 가 `--requested-at <시각>` 을 덧붙인다(ADR 0010)
    for job in jobs:
        assert by_job[job] == ["/app/.venv/bin/python", "-m", "survey_service.jobs", job]
    assert declared["run_as_uid"] == 10001 and "USER 10001:10001" in DOCKERFILE
    assert declared["writable_paths"] == [] and declared["capabilities"] == [] and declared["sysctls"] == []


def operations() -> list[tuple[str, str, list[dict[str, list[str]]]]]:
    document = yaml.safe_load((CONTRACTS / "openapi" / "survey-service.yaml").read_text(encoding="utf-8"))
    found: list[tuple[str, str, list[dict[str, list[str]]]]] = []
    for path, item in document["paths"].items():
        for method in ("get", "post", "put", "delete"):
            if method in item:
                found.append((path, method.upper(), item[method].get("security", [])))
    return found


SCHEME = {
    ExposureAudience.HUMAN_OIDC: "oidc",
    ExposureAudience.DEVICE_MTLS: "device_mtls",
    ExposureAudience.EXTERNAL_MACHINE_TOKEN: "machine_token",
    ExposureAudience.MACHINE_TOKEN: "machine_token",
}


def allows(security: list[dict[str, list[str]]], audience: ExposureAudience) -> bool:
    """작업의 security 요구가 이 대상을 허용하는지. platform 의 라우트 생성 규칙(area_mtls 가 함께 있으면 같은 서버 안의 호출)과 같다."""
    for alternative in security:
        if SCHEME[audience] not in alternative:
            continue
        in_area = "area_mtls" in alternative
        if (audience is ExposureAudience.MACHINE_TOKEN) == in_area:
            return True
    return False


def under(prefix: str, path: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def test_every_route_opens_an_operation_and_every_operation_is_reachable_by_its_audiences() -> None:
    """platform 은 노출 선언과 작업 security 의 곱 로 라우트를 만들고 허용 작업이 하나도 없는 접두어가 있으면 시작하지 않는다."""
    exposure = Exposure.model_validate(load("exposure.json"))
    ops = [op for op in operations() if op[0] not in ("/healthz", "/readyz", "/metrics")]
    for route in exposure.routes:
        methods = {m.value for m in route.methods}
        matched = [op for op in ops if under(route.path_prefix.root, op[0]) and op[1] in methods]
        assert any(allows(op[2], route.audience) for op in matched), (route.path_prefix.root, route.audience.value)
    reachable = {
        (op[0], op[1], audience)
        for op in ops
        for audience in SCHEME
        for route in exposure.routes
        if route.audience is audience
        and under(route.path_prefix.root, op[0])
        and op[1] in {m.value for m in route.methods}
        and allows(op[2], audience)
    }
    for path, method, security in ops:
        for audience in SCHEME:
            if allows(security, audience):
                assert (path, method, audience) in reachable, (method, path, audience.value)


def test_egress_names_the_neighbors_the_service_calls() -> None:
    """model-runtime(추출·응답), platform(발급자: JWKS·토큰 엔드포인트). 웹 푸시 서비스는 설치처 값이라 deploy 가 더한다(ADR 0016)."""
    assert Exposure.model_validate(load("exposure.json")).model_dump(mode="json")["egress"] == [
        "model-runtime",
        "platform",
    ]
