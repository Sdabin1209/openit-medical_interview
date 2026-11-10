"""package_publish(도구)의 패키지 만들기: 어댑터 폴더와 시스템 프롬프트와 평가 보고서를 계약 ModelPackageOciManifest 로
묶는다.

model-lab 이 생기기 전까지 모델 패키지를 만드는 유일한 길이다. 평가(추론)와 레지스트리에 올리는 일은 이 파일 밖이다
(`publish.py` 가 엮고 `link/publish_registry.py` 가 올린다). 같은 입력이면 같은 바이트가 나온다(시각은 입력이다).
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from model_runtime.contract.models import ModelPackageManifest, ModelPackageOciManifest

CONFIG_MEDIA_TYPE = "application/vnd.openit.model.package.config.v1+json"
WEIGHTS_MEDIA_TYPE = "application/vnd.openit.model.adapter.weights.v1"
PROMPT_MEDIA_TYPE = "application/vnd.openit.model.adapter.system-prompt.v1"
ARTIFACT_TYPE = "application/vnd.openit.model.package.v1"
_ROLE_ORDER = ("LORA_A", "LORA_B")  # 왜: 계약 AdapterRole 의 순서. 매니페스트 layers 순서가 입력에 흔들리지 않게 한다
_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class AdapterFiles:
    """어댑터 하나의 파일: 어댑터 폴더를 묶은 tar, 시스템 프롬프트, 서빙 설정(계약 ServingConfig 모양)."""

    weights_tar: Path
    system_prompt: Path
    serving_config: Mapping[str, Any]


@dataclass(frozen=True)
class PackageFile:
    """레지스트리에 올릴 파일 하나와 그 OCI descriptor."""

    path: Path
    media_type: str
    digest: str
    size: int

    def descriptor(self) -> dict[str, Any]:
        """OCI descriptor(미디어 유형, digest, 크기). 칸 이름은 OCI 표준 그대로다."""
        return {"mediaType": self.media_type, "digest": self.digest, "size": self.size}


@dataclass(frozen=True)
class BuiltPackage:
    """게시할 패키지: 파일들, 매니페스트 바이트, 패키지의 식별자(매니페스트의 digest)."""

    config: PackageFile
    layers: Sequence[PackageFile]
    manifest: bytes
    digest: str


def file_digest(path: Path) -> tuple[str, int]:
    """파일의 OCI digest(`sha256:<소문자 16진수 64자>`)와 크기."""
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            hasher.update(chunk)
            size += len(chunk)
    return f"sha256:{hasher.hexdigest()}", size


def pack_adapter_folder(folder: Path, archive: Path) -> None:
    """어댑터 폴더(PEFT 출력)를 같은 입력이면 같은 바이트의 tar 로 묶는다(이름순, 시각·소유자 0, 일반 파일만).

    왜 이 형식: 계약의 가중치 layer 는 파일 하나다. vLLM 이 읽는 어댑터는 폴더(adapter_config.json 과 가중치)라 폴더를
    하나로 묶는다.
    package_loader 가 같은 형식을 `data` 필터로 안전하게 푼다.
    """
    files = sorted(path for path in folder.rglob("*") if path.is_file())
    if not any(path.name == "adapter_config.json" and path.parent == folder for path in files):
        raise ValueError(f"{folder} 에 adapter_config.json 이 없다. 어댑터 폴더가 아니다")
    with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as tar:
        for path in files:
            if path.is_symlink():
                raise ValueError(f"{path} 는 링크다. 어댑터 폴더에는 일반 파일만 둔다")
            info = tar.gettarinfo(str(path), arcname=path.relative_to(folder).as_posix())
            info.mtime, info.uid, info.gid, info.uname, info.gname, info.mode = 0, 0, 0, "", "", 0o644
            with path.open("rb") as handle:
                tar.addfile(info, handle)


def _canonical(body: Mapping[str, Any]) -> bytes:
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_package(
    *,
    adapters: Mapping[str, AdapterFiles],
    base_model: str,
    runtime_contract_version: int,
    model_io_version: str,
    model_runtime_version: str,
    dataset_version_id: str,
    training_run_ids: Sequence[str],
    evaluation: Mapping[str, Any],
    created_at: str,
    workdir: Path,
) -> BuiltPackage:
    """패키지 파일(config 와 layer 넷)과 OCI 매니페스트를 만들고 계약 검증을 거친다. 어긋나면 ValueError(pydantic)."""
    workdir.mkdir(parents=True, exist_ok=True)
    layers: list[PackageFile] = []
    entries: list[dict[str, Any]] = []
    for role in _ROLE_ORDER:
        files = adapters[role]
        weights = PackageFile(files.weights_tar, WEIGHTS_MEDIA_TYPE, *file_digest(files.weights_tar))
        prompt = PackageFile(files.system_prompt, PROMPT_MEDIA_TYPE, *file_digest(files.system_prompt))
        layers += [weights, prompt]
        entries.append(
            {
                "role": role,
                "weights": weights.descriptor(),
                "system_prompt": prompt.descriptor(),
                "serving_config": dict(files.serving_config),
            }
        )
    config_body: dict[str, Any] = {
        "base_model": base_model,
        "runtime_contract_version": runtime_contract_version,
        "model_io_version": model_io_version,
        "model_runtime_version": model_runtime_version,
        "adapters": entries,
        "lineage": {
            "dataset_version_id": dataset_version_id,
            "base_model": base_model,
            "training_run_ids": list(training_run_ids),
        },
        "evaluation": dict(evaluation),
        "created_at": created_at,
    }
    config_bytes = _canonical(config_body)
    ModelPackageManifest.model_validate_json(config_bytes, strict=True)
    config_path = workdir / "config.json"
    config_path.write_bytes(config_bytes)
    config = PackageFile(config_path, CONFIG_MEDIA_TYPE, *file_digest(config_path))
    manifest_body = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "artifactType": ARTIFACT_TYPE,
        "config": config.descriptor(),
        "layers": [layer.descriptor() for layer in layers],
    }
    manifest_bytes = _canonical(manifest_body)
    ModelPackageOciManifest.model_validate_json(manifest_bytes, strict=True)
    return BuiltPackage(config, layers, manifest_bytes, f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}")
