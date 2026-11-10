"""package_publish(패키지 만들기): 계약 매니페스트, 같은 입력이면 같은 바이트, 어댑터 폴더 묶기."""

import json
import tarfile
from pathlib import Path

import pytest

from model_runtime.components.package_publish import AdapterFiles, BuiltPackage, build_package, pack_adapter_folder
from package_factory import EVALUATION, SERVING
from support import adapter_folder


def files(tmp: Path) -> dict[str, AdapterFiles]:
    result: dict[str, AdapterFiles] = {}
    for role in ("LORA_A", "LORA_B"):
        folder = adapter_folder(tmp, role)
        archive = tmp / f"{role}.tar"
        pack_adapter_folder(folder, archive)
        prompt = tmp / f"{role}.txt"
        prompt.write_text(f"{role} 프롬프트", encoding="utf-8")
        result[role] = AdapterFiles(archive, prompt, SERVING)
    return result


def build(tmp: Path, adapters: dict[str, AdapterFiles], created: str = "2026-11-10T09:00:00+00:00") -> BuiltPackage:
    return build_package(
        adapters=adapters,
        base_model="Qwen/Qwen3-8B",
        runtime_contract_version=1,
        model_io_version="model-io-v2",
        model_runtime_version="0.1.0",
        dataset_version_id=EVALUATION["dataset_version_id"],
        training_run_ids=["3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90", "4f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90"],
        evaluation=EVALUATION,
        created_at=created,
        workdir=tmp / "out",
    )


def test_manifest_is_the_contract_oci_manifest(tmp_path: Path) -> None:
    package = build(tmp_path, files(tmp_path))
    manifest = json.loads(package.manifest)
    assert manifest["artifactType"] == "application/vnd.openit.model.package.v1" and manifest["schemaVersion"] == 2
    assert [layer["mediaType"] for layer in manifest["layers"]] == [
        "application/vnd.openit.model.adapter.weights.v1",
        "application/vnd.openit.model.adapter.system-prompt.v1",
    ] * 2
    assert manifest["config"]["mediaType"] == "application/vnd.openit.model.package.config.v1+json"
    assert package.digest.startswith("sha256:") and len(package.digest) == 71


def test_same_input_gives_same_bytes_and_time_is_an_input(tmp_path: Path) -> None:
    adapters = files(tmp_path)
    first = build(tmp_path / "one", adapters)
    again = build(tmp_path / "two", adapters)
    other = build(tmp_path / "three", adapters, created="2026-11-11T09:00:00+00:00")
    assert first.digest == again.digest and first.digest != other.digest


def test_packed_folder_is_reproducible_and_relative(tmp_path: Path) -> None:
    folder = adapter_folder(tmp_path, "adapter")
    (folder / "sub").mkdir()
    (folder / "sub" / "extra.json").write_text("{}", encoding="utf-8")
    pack_adapter_folder(folder, tmp_path / "1.tar")
    pack_adapter_folder(folder, tmp_path / "2.tar")
    assert (tmp_path / "1.tar").read_bytes() == (tmp_path / "2.tar").read_bytes()
    with tarfile.open(tmp_path / "1.tar") as tar:
        assert tar.getnames() == ["adapter_config.json", "adapter_model.safetensors", "sub/extra.json"]
        assert {(m.mtime, m.uid, m.gid) for m in tar.getmembers()} == {(0, 0, 0)}


def test_folder_without_adapter_config_is_refused(tmp_path: Path) -> None:
    (tmp_path / "x").mkdir()
    with pytest.raises(ValueError, match=r"adapter_config\.json"):
        pack_adapter_folder(tmp_path / "x", tmp_path / "x.tar")


def test_symlink_is_refused(tmp_path: Path) -> None:
    folder = adapter_folder(tmp_path, "adapter")
    (folder / "link").symlink_to(folder / "adapter_config.json")
    with pytest.raises(ValueError, match="링크"):
        pack_adapter_folder(folder, tmp_path / "a.tar")


def test_contract_violation_is_refused_before_publishing(tmp_path: Path) -> None:
    adapters = files(tmp_path)
    with pytest.raises(ValueError, match=r"model_io_version|Input should be"):
        build_package(
            adapters=adapters,
            base_model="Qwen/Qwen3-8B",
            runtime_contract_version=1,
            model_io_version="model-io-v9",
            model_runtime_version="0.1.0",
            dataset_version_id=EVALUATION["dataset_version_id"],
            training_run_ids=[],
            evaluation=EVALUATION,
            created_at="2026-11-10T09:00:00+00:00",
            workdir=tmp_path / "bad",
        )
