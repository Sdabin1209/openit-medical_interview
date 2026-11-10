"""샌드박스 사본과 설치 입력 시험(docker 없음): 제품 구성을 바꾸지 않고, 시험 입력만 사본에 쓴다."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from openit_e2e import sandbox as sandbox_module
from openit_e2e.contract import Contract
from openit_e2e.sandbox import Sandbox

REPO = Path(__file__).resolve().parents[3]
CONTRACT = Contract(REPO / "contracts")


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Sandbox:
    monkeypatch.setattr(sandbox_module, "WORK_ROOT", tmp_path / "work")
    box = Sandbox("gpu-12g", "Qwen/Qwen3-1.7B", ["--gpu-memory-utilization", "0.7"])
    box.prepare()
    return box


def test_project_name_marks_the_sandbox() -> None:
    assert Sandbox("gpu-12g", "m", []).project.startswith("openit-e2e-")


def test_deployable_folders_skip_template_areas() -> None:
    names = {sandbox_module.image_name(folder) for folder in sandbox_module.deployable_folders(REPO)}
    assert {"openit/survey-service", "openit/model-runtime", "openit/web-admin-console", "openit/web-kiosk-frontend"} <= names
    assert not any("example" in name for name in names)


def test_copy_has_product_compose_unchanged_and_no_install_state(box: Sandbox) -> None:
    assert (box.deploy_dir / "compose.yaml").read_bytes() == (REPO / "deploy" / "compose.yaml").read_bytes()  # 제품 compose 는 그대로다
    assert (box.deploy_dir / "env.example").read_bytes() == (REPO / "deploy" / "env.example").read_bytes()
    for state in ("secrets", "pki", "generated", "images.lock", "e2e", ".venv"):
        assert not (box.deploy_dir / state).exists(), state  # 이 설치의 상태와 이 도구 자신은 복사하지 않는다
    assert (box.root / "services" / "survey-service" / "Dockerfile").is_file()
    assert not (box.root / "services" / "_example").exists()
    assert not (box.root / "services" / "survey-service" / "src").exists()  # Dockerfile 만 둔다(빌드는 하지 않는다)


def test_install_inputs(box: Sandbox) -> None:
    env = dict(line.split("=", 1) for line in (box.deploy_dir / ".env").read_text(encoding="utf-8").splitlines())
    assert env["OPENIT_PROJECT_NAME"] == box.project
    assert env["OPENIT_INFERENCE_ENGINE_LOCAL"] == "false"
    assert env["OPENIT_MODEL_PROFILE"] == "gpu-12g" and env["OPENIT_BASE_MODEL"] == "Qwen/Qwen3-1.7B"
    assert Path(env["OPENIT_DEVICE_CA_CERTIFICATE_FILE"]).is_file() and Path(env["OPENIT_DEVICE_ALLOWLIST_FILE"]).is_file()
    assert box.install_value("OPENIT_MODEL_REGISTRY_REPOSITORY") == "openit/model-package"  # env.example 의 기본값
    assert box.install_value("OPENIT_MODEL_PROFILE") == "gpu-12g"  # .env 가 덮는다


def test_machine_callers_table_and_device_allowlist_satisfy_the_contract(box: Sandbox) -> None:
    table = json.loads((box.deploy_dir / "machine-callers.json").read_text(encoding="utf-8"))
    assert CONTRACT.schema_errors(CONTRACT.named("MachineTokenTable"), table) == []
    assert {(entry["client"], tuple(entry["roles"])) for entry in table["tokens"]} == {
        ("survey-service", ("inference-caller",)),
        ("hospital", ("result-reader",)),
    }
    allowlist = json.loads((box.state / "device-allowlist.json").read_text(encoding="utf-8"))
    assert CONTRACT.schema_errors(CONTRACT.named("DeviceAllowlist"), allowlist) == []
    assert allowlist["devices"][0]["device_id"] == sandbox_module.DEVICE_ID
    assert box.device is not None and allowlist["devices"][0]["serial_number"] == box.device.serial_hex


def test_overlay_extends_the_product_engine_definition(box: Sandbox) -> None:
    product = yaml.safe_load((REPO / "deploy" / "compose.yaml").read_text(encoding="utf-8"))["services"]["inference-engine"]
    overlay = yaml.safe_load((box.deploy_dir / "compose.e2e.yaml").read_text(encoding="utf-8"))
    engine = overlay["services"]["inference-engine"]
    assert engine["command"] == [*product["command"], "--gpu-memory-utilization", "0.7"]  # 제품 정의의 인자 뒤에 더한다
    assert engine["environment"] == {"HF_HUB_OFFLINE": "1"}
    assert any(volume.endswith(f":{sandbox_module.ADAPTERS_IN_CONTAINER}:ro") for volume in engine["volumes"])
    publisher = overlay["services"]["e2e-publisher"]
    assert publisher["profiles"] == ["e2e"] and publisher["entrypoint"] == ["/app/.venv/bin/package-publish"]
    assert publisher["read_only"] is True and publisher["cap_drop"] == ["ALL"]
    assert overlay["volumes"] == {sandbox_module.HF_VOLUME: {"external": True}}


def test_compose_args_name_the_project_and_every_profile(box: Sandbox) -> None:
    args = box.compose_args()
    assert args[args.index("--project-name") + 1] == box.project
    profiles = [args[index + 1] for index, value in enumerate(args) if value == "--profile"]
    assert {"local-registry", "inference-engine", "e2e", "tools"} == set(profiles)  # down -v 가 프로필 서비스까지 지운다


def test_environment_is_an_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENIT_SECRET_LIKE", "x")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = sandbox_module.restricted_env()
    assert "OPENIT_SECRET_LIKE" not in env and env["PATH"] == "/usr/bin"
