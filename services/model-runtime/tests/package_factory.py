"""시험용 모델 패키지를 메모리 레지스트리에 만든다. 계약을 어기는 변형(손상)도 만든다."""

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from model_runtime.components.package_publish import AdapterFiles, BuiltPackage, build_package, pack_adapter_folder
from model_runtime.types import PackageNotFoundError, RawManifest
from support import BASE_MODEL, adapter_folder

REPO = "openit/model-package"
SERVING = {"max_new_tokens": 1208, "temperature": 0.0, "constrained_decoding": False}
EVALUATION: dict[str, Any] = {
    "dataset_version_id": "3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90",
    "created_at": "2026-11-10T09:30:00+00:00",
    "metrics": [{"name": "semantic_violation_rate", "value": 0.0, "unit": "ratio", "sample_count": 4}],
}


@dataclass
class MemorySource:
    """PackageSource 의 메모리 구현. 시험이 manifests·blobs 를 바꿔 손상을 흉내 낸다."""

    manifests: dict[str, bytes] = field(default_factory=lambda: dict[str, bytes]())
    blobs: dict[str, bytes] = field(default_factory=lambda: dict[str, bytes]())
    downloads: list[str] = field(default_factory=lambda: list[str]())

    async def fetch_manifest(self, digest: str) -> RawManifest:
        if digest not in self.manifests:
            raise PackageNotFoundError
        return RawManifest(digest, self.manifests[digest])

    async def list_manifests(self) -> list[RawManifest]:
        return [RawManifest(digest, content) for digest, content in self.manifests.items()]

    async def download_blob(self, digest: str, destination: Path) -> None:
        self.downloads.append(digest)
        if digest not in self.blobs:
            raise PackageNotFoundError
        destination.write_bytes(self.blobs[digest])


def sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def publish_memory(
    source: MemorySource,
    work: Path,
    *,
    version: str = "0.1.0",
    mutate_config: Callable[[dict[str, Any]], None] | None = None,
    mutate_manifest: Callable[[dict[str, Any]], None] | None = None,
    prompts: tuple[str, str] = ("프롬프트 A", "프롬프트 B"),
    seed: str = "x",
    created_at: str = "2026-11-10T09:31:00+00:00",
    base_model: str = BASE_MODEL,
) -> str:
    """패키지를 만들어 source 에 넣고 매니페스트 digest 를 돌려준다. mutate_* 는 계약을 어기는 변형을 넣는다."""
    folders = {
        "LORA_A": adapter_folder(work, f"a-{uuid.uuid4().hex[:6]}", f"a{seed}".encode()),
        "LORA_B": adapter_folder(work, f"b-{uuid.uuid4().hex[:6]}", f"b{seed}".encode()),
    }
    files: dict[str, AdapterFiles] = {}
    for (role, folder), text in zip(folders.items(), prompts, strict=True):
        archive = work / f"{role}-{seed}.tar"
        pack_adapter_folder(folder, archive)
        prompt = work / f"{role}-{seed}.txt"
        prompt.write_text(text, encoding="utf-8")
        files[role] = AdapterFiles(archive, prompt, SERVING)
    package = build_package(
        adapters=files,
        base_model=base_model,
        runtime_contract_version=1,
        model_io_version="model-io-v2",
        model_runtime_version=version,
        dataset_version_id=EVALUATION["dataset_version_id"],
        training_run_ids=[str(uuid.uuid4()), str(uuid.uuid4())],
        evaluation=EVALUATION,
        created_at=created_at,
        workdir=work / f"pkg-{seed}",
    )
    config = json.loads(package.config.path.read_bytes())
    manifest = json.loads(package.manifest)
    config_bytes = package.config.path.read_bytes()
    if mutate_config:
        mutate_config(config)
        config_bytes = json.dumps(config, ensure_ascii=False).encode()
        manifest["config"] = {**manifest["config"], "digest": sha(config_bytes), "size": len(config_bytes)}
    if mutate_manifest:
        mutate_manifest(manifest)
    manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode()
    digest = sha(manifest_bytes)
    source.manifests[digest] = manifest_bytes
    source.blobs[manifest["config"]["digest"]] = config_bytes
    for layer in package.layers:
        source.blobs[layer.digest] = layer.path.read_bytes()
    return digest


def built(tmp: Path, seed: str = "") -> BuiltPackage:
    adapters: dict[str, AdapterFiles] = {}
    for role in ("LORA_A", "LORA_B"):
        archive = tmp / f"{role}.tar"
        pack_adapter_folder(adapter_folder(tmp, role, (role + seed).encode()), archive)
        prompt = tmp / f"{role}.txt"
        prompt.write_text(role, encoding="utf-8")
        adapters[role] = AdapterFiles(archive, prompt, SERVING)
    return build_package(
        adapters=adapters,
        base_model="Qwen/Qwen3-8B",
        runtime_contract_version=1,
        model_io_version="model-io-v2",
        model_runtime_version="0.1.0",
        dataset_version_id=EVALUATION["dataset_version_id"],
        training_run_ids=[],
        evaluation=EVALUATION,
        created_at="2026-11-10T09:00:00+00:00",
        workdir=tmp / "pkg",
    )
