"""package_loader: 모델 패키지(OCI 아티팩트)를 검증하고 적재한다.

적재 전 검증: 매니페스트(artifactType, 목록표), 파일의 digest 와 크기, 모델 입출력 버전, model-runtime
버전(MAJOR.MINOR).
기반 모델은 서버의 프로파일이 정한 것과 같아야 한다. 검증을 통과해야 어댑터를 추론 엔진에 올린다. 입력은 패키지 digest 와 레지스트리 포트, 출력은 적재된 모델이다.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from model_runtime.contract.models import (
    AdapterEntry,
    ModelIoVersion,
    ModelPackageBlobDescriptor,
    ModelPackageBlobMediaType,
    ModelPackageManifest,
    ModelPackageOciManifest,
)
from model_runtime.types import (
    AdapterRegistry,
    AdapterRole,
    LoadedAdapter,
    LoadedPackage,
    PackageInvalidError,
    PackageSource,
)

# 왜 하나: 계약 ModelIoVersion 의 값이 model-io-v2 하나이고, 이 영역이 아는 모델 통신(prompt·output_guard)이 v2 뿐이다.
# 아는 통신이 없는 버전의 패키지는 적재하지 않는다(계약 README 모델 입출력의 버전)
SUPPORTED_MODEL_IO = frozenset({ModelIoVersion.model_io_v2})
_CHUNK = 1024 * 1024  # 왜: 큰 가중치 파일을 메모리에 다 올리지 않고 1 MiB 씩 해시한다. 값은 측정으로 정한 것이 아니다
_ADAPTER_MARKER = "adapter_config.json"  # 왜: PEFT 어댑터 폴더의 표준 설정 파일. vLLM 이 이 파일로 어댑터를 읽는다


@dataclass(frozen=True)
class InspectedPackage:
    """레지스트리에서 받아 계약과 맞춰 본 패키지의 목록(파일은 아직 받지 않았다)."""

    digest: str
    oci: ModelPackageOciManifest
    manifest: ModelPackageManifest


def _sha256_file(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            hasher.update(chunk)
            size += len(chunk)
    return f"sha256:{hasher.hexdigest()}", size


async def _fetch_verified(source: PackageSource, descriptor: ModelPackageBlobDescriptor, destination: Path) -> None:
    """파일을 받아 digest 와 크기가 목록과 같은지 확인한다. 이미 같은 파일이 있으면 다시 받지 않는다."""
    if destination.is_file() and await asyncio.to_thread(_sha256_file, destination) == (
        descriptor.digest.root,
        descriptor.size.root,
    ):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    await source.download_blob(descriptor.digest.root, partial)
    actual = await asyncio.to_thread(_sha256_file, partial)
    if actual != (descriptor.digest.root, descriptor.size.root):
        partial.unlink(missing_ok=True)
        raise PackageInvalidError("받은 파일의 digest 나 크기가 목록표와 다르다")
    partial.replace(destination)


def _major_minor(version: str) -> tuple[str, str]:
    major, minor, *_ = version.split(".")
    return major, minor


async def inspect_package(
    source: PackageSource, digest: str, workdir: Path, installed_version: str, base_model: str
) -> InspectedPackage:
    """매니페스트와 목록표를 받아 계약과 맞춰 본다. 어긋나면 PackageInvalidError, 없으면 PackageNotFoundError."""
    raw = await source.fetch_manifest(digest)
    if f"sha256:{hashlib.sha256(raw.content).hexdigest()}" != digest:
        raise PackageInvalidError("받은 매니페스트의 digest 가 요청한 digest 와 다르다")
    try:
        oci = ModelPackageOciManifest.model_validate_json(raw.content, strict=True)
    except ValidationError as error:
        # 왜 위치만: 오류 내용에 받은 값이 들어간다. 어느 칸이 어긋났는지만 쓴다
        place = ".".join(str(part) for part in error.errors(include_input=False)[0]["loc"])
        raise PackageInvalidError(f"매니페스트가 계약 ModelPackageOciManifest 와 다르다({place})") from error
    if oci.config.mediaType != ModelPackageBlobMediaType.application_vnd_openit_model_package_config_v1_json:
        raise PackageInvalidError("config 의 미디어 유형이 목록표 유형이 아니다")
    config_path = workdir / "config.json"
    await _fetch_verified(source, oci.config, config_path)
    try:
        manifest = ModelPackageManifest.model_validate_json(config_path.read_bytes(), strict=True)
    except ValidationError as error:
        place = ".".join(str(part) for part in error.errors(include_input=False)[0]["loc"])
        raise PackageInvalidError(f"목록표가 계약 ModelPackageManifest 와 다르다({place})") from error
    listed = {_key(entry.weights) for entry in manifest.adapters} | {
        _key(entry.system_prompt) for entry in manifest.adapters
    }
    if {_key(layer) for layer in oci.layers} != listed or len(listed) != 4:
        raise PackageInvalidError("매니페스트의 파일 목록이 목록표의 어댑터 파일과 다르다")
    for entry in manifest.adapters:
        if entry.weights.mediaType != ModelPackageBlobMediaType.application_vnd_openit_model_adapter_weights_v1:
            raise PackageInvalidError("어댑터 가중치 파일의 미디어 유형이 가중치 유형이 아니다")
        if (
            entry.system_prompt.mediaType
            != ModelPackageBlobMediaType.application_vnd_openit_model_adapter_system_prompt_v1
        ):
            raise PackageInvalidError("시스템 프롬프트 파일의 미디어 유형이 시스템 프롬프트 유형이 아니다")
    if manifest.model_io_version not in SUPPORTED_MODEL_IO:
        raise PackageInvalidError("이 서버가 아는 모델 통신이 없는 모델 입출력 버전이다")
    if manifest.base_model.root != base_model:
        # 왜: 어댑터는 학습한 기반 모델에만 맞는다. 이 서버의 엔진은 프로파일 표의 기반 모델 하나를 서빙한다(ADR 0007)
        raise PackageInvalidError("패키지의 기반 모델이 이 서버의 프로파일이 정한 기반 모델과 다르다")
    if _major_minor(manifest.model_runtime_version.root) != _major_minor(installed_version):
        raise PackageInvalidError("패키지를 만든 model-runtime 의 MAJOR.MINOR 가 서빙 설치본과 다르다")
    return InspectedPackage(digest, oci, manifest)


def _key(descriptor: ModelPackageBlobDescriptor) -> tuple[str, str, int]:
    return descriptor.mediaType.value, descriptor.digest.root, descriptor.size.root


def _extract(archive: Path, target: Path) -> None:
    """어댑터 폴더의 tar 를 푼다. 폴더 밖으로 나가는 경로, 링크, 특수 파일은 `data` 필터가 막는다(PEP 706)."""
    target.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:*") as tar:
            tar.extractall(target, filter="data")
    except (tarfile.TarError, OSError) as error:
        raise PackageInvalidError("어댑터 가중치 파일을 어댑터 폴더로 풀지 못했다") from error
    if not (target / _ADAPTER_MARKER).is_file():
        raise PackageInvalidError(f"어댑터 폴더에 {_ADAPTER_MARKER} 가 없다")


def _role(entry: AdapterEntry) -> AdapterRole:
    return AdapterRole(entry.role.value)


async def load_package(
    source: PackageSource,
    engine: AdapterRegistry,
    inspected: InspectedPackage,
    workdir: Path,
) -> LoadedPackage:
    """검증한 패키지의 파일을 받아 digest 를 확인하고 어댑터를 엔진에 올린다. 실패하면 이미 올린 어댑터를 내린다."""
    adapters: dict[AdapterRole, LoadedAdapter] = {}
    uploaded: list[str] = []
    prefix = inspected.digest.removeprefix("sha256:")[:12]
    try:
        for entry in inspected.manifest.adapters:
            role = _role(entry)
            tar_path = workdir / f"{role.value}.weights"
            prompt_path = workdir / f"{role.value}.system-prompt"
            await _fetch_verified(source, entry.weights, tar_path)
            await _fetch_verified(source, entry.system_prompt, prompt_path)
            folder = workdir / "adapters" / role.value
            await asyncio.to_thread(_extract, tar_path, folder)
            try:
                prompt = prompt_path.read_text(encoding="utf-8")
            except UnicodeDecodeError as error:
                raise PackageInvalidError("시스템 프롬프트 파일이 UTF-8 글자가 아니다") from error
            if not prompt.strip():
                raise PackageInvalidError("시스템 프롬프트 파일이 비었다")
            name = f"{role.value.lower()}-{prefix}"
            await engine.load_adapter(name, folder)
            uploaded.append(name)
            adapters[role] = LoadedAdapter(name, prompt, entry.serving_config)
    except BaseException:
        for name in uploaded:
            await engine.unload_adapter(name)
        raise
    if set(adapters) != {AdapterRole.LORA_A, AdapterRole.LORA_B}:
        for name in uploaded:
            await engine.unload_adapter(name)
        raise PackageInvalidError("목록표에 LoRA-A 와 LoRA-B 어댑터가 하나씩 있어야 한다")
    return LoadedPackage(inspected.digest, inspected.manifest, adapters, datetime.now(UTC))


def describe_digest_dir(digest: str) -> str:
    """패키지 하나의 작업 폴더 이름. digest 의 16진수 부분이라 경로로 안전하다(OciDigest 의 패턴이 보장)."""
    return digest.removeprefix("sha256:")


def loaded_summary(package: LoadedPackage) -> str:
    """LOADED 기록에 남기는 요약(문항 은행 버전과 모델 입출력 버전)."""
    return json.dumps(
        {
            "runtime_contract_version": package.runtime_contract_version,
            "model_io_version": package.model_io_version.value,
        },
        sort_keys=True,
    )
