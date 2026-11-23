"""package_loader: 적재 전 검증(매니페스트, 파일 digest, 모델 입출력 버전, 서빙 버전)과 어댑터 적재."""

import io
import tarfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from model_runtime.components.package_loader import inspect_package, load_package
from model_runtime.types import AdapterRole, PackageInvalidError, PackageNotFoundError
from package_factory import MemorySource, publish_memory, sha
from support import BASE_MODEL

pytestmark = pytest.mark.anyio


class Engine:
    def __init__(self, fail_on: int | None = None) -> None:
        self.loaded: dict[str, Path] = {}
        self.unloaded: list[str] = []
        self.fail_on = fail_on

    async def load_adapter(self, name: str, path: Path) -> None:
        if self.fail_on is not None and len(self.loaded) == self.fail_on:
            raise RuntimeError("엔진이 거절했다")
        assert (path / "adapter_config.json").is_file()
        self.loaded[name] = path

    async def unload_adapter(self, name: str) -> None:
        self.unloaded.append(name)


async def test_valid_package_is_loaded_with_prompts_and_serving(tmp_path: Path) -> None:
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src")
    engine = Engine()
    inspected = await inspect_package(
        source, digest, tmp_path / "work", "0.1.7", BASE_MODEL
    )  # MAJOR.MINOR 만 맞으면 된다
    package = await load_package(source, engine, inspected, tmp_path / "work")
    assert package.digest == digest and package.runtime_contract_version == 1
    assert package.adapters[AdapterRole.LORA_A].system_prompt == "프롬프트 A"
    assert package.adapters[AdapterRole.LORA_B].serving.max_new_tokens.root == 1208
    assert sorted(engine.loaded) == [f"lora_a-{digest[7:19]}", f"lora_b-{digest[7:19]}"]


async def test_second_load_reuses_verified_files(tmp_path: Path) -> None:
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src")
    for _ in range(2):
        inspected = await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)
        await load_package(source, Engine(), inspected, tmp_path / "work")
    assert len(source.downloads) == 5  # config 하나와 layer 넷. 둘째 적재와 검사는 받지 않았다


async def test_missing_package_is_not_found(tmp_path: Path) -> None:
    with pytest.raises(PackageNotFoundError):
        await inspect_package(MemorySource(), "sha256:" + "0" * 64, tmp_path, "0.1.0", BASE_MODEL)


def set_artifact_type(manifest: dict[str, Any]) -> None:
    manifest["artifactType"] = "application/vnd.example.other"


def break_layer_digest(manifest: dict[str, Any]) -> None:
    manifest["layers"][0]["digest"] = "sha256:" + "1" * 64


def drop_layer(manifest: dict[str, Any]) -> None:
    manifest["layers"] = manifest["layers"][:3]


def wrong_config_type(manifest: dict[str, Any]) -> None:
    manifest["config"]["mediaType"] = "application/vnd.openit.model.adapter.weights.v1"


def swap_media_types(manifest: dict[str, Any]) -> None:
    manifest["layers"][0]["mediaType"], manifest["layers"][1]["mediaType"] = (
        manifest["layers"][1]["mediaType"],
        manifest["layers"][0]["mediaType"],
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (set_artifact_type, "ModelPackageOciManifest"),
        (break_layer_digest, "파일 목록"),
        (drop_layer, "ModelPackageOciManifest"),
        (wrong_config_type, "ModelPackageOciManifest|config"),
    ],
)
async def test_manifest_violations_are_invalid(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], None], message: str
) -> None:
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src", mutate_manifest=mutate)
    with pytest.raises(PackageInvalidError, match=message):
        await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)


async def test_layer_media_types_must_match_roles(tmp_path: Path) -> None:
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src", mutate_manifest=swap_media_types)
    with pytest.raises(PackageInvalidError):
        await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)


async def test_manifest_bytes_must_match_the_requested_digest(tmp_path: Path) -> None:
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src")
    other = publish_memory(source, tmp_path / "src", seed="y")
    source.manifests[digest] = source.manifests[other]
    with pytest.raises(PackageInvalidError, match="digest"):
        await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)


async def test_config_that_is_not_the_contract_manifest_is_invalid(tmp_path: Path) -> None:
    source = MemorySource()
    # 계약 9.4.0 부터 v3 도 계약 값이라, 계약에 없는 버전으로 '계약 모양이 아닌 목록표'를 만든다
    digest = publish_memory(source, tmp_path / "src", mutate_config=lambda c: c.update(model_io_version="model-io-v9"))
    with pytest.raises(PackageInvalidError, match="ModelPackageManifest"):
        await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)


async def test_serving_version_must_share_major_minor(tmp_path: Path) -> None:
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src", version="0.2.0")
    with pytest.raises(PackageInvalidError, match=r"MAJOR\.MINOR"):
        await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)


async def test_corrupted_adapter_file_is_invalid_and_leaves_nothing_loaded(tmp_path: Path) -> None:
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src")
    inspected = await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)
    victim = inspected.manifest.adapters[1].weights.digest.root
    source.blobs[victim] = source.blobs[victim] + b"x"
    engine = Engine()
    with pytest.raises(PackageInvalidError, match="digest"):
        await load_package(source, engine, inspected, tmp_path / "work")
    assert [p for p in (tmp_path / "work").rglob("*.part")] == []


def archive_of(files: dict[str, bytes], link: tuple[str, str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        if link:
            info = tarfile.TarInfo(link[0])
            info.type, info.linkname = tarfile.SYMTYPE, link[1]
            tar.addfile(info)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "archive",
    [
        archive_of({"adapter_model.safetensors": b"w"}),  # adapter_config.json 이 없다
        archive_of({"adapter_config.json": b"{}", "../escape.txt": b"x"}),  # 폴더 밖으로 나가는 경로
        archive_of({"adapter_config.json": b"{}"}, link=("evil", "/etc/passwd")),  # 폴더 밖을 가리키는 링크
        b"not a tar",
    ],
)
async def test_unsafe_or_broken_adapter_archive_is_invalid(tmp_path: Path, archive: bytes) -> None:
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src")
    inspected = await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)
    # 가중치 파일을 바꾸고 목록표도 맞춰 digest 검사는 통과시킨다. 풀 때 막혀야 한다
    entry = inspected.manifest.adapters[0]
    old = entry.weights.digest.root
    source.blobs[sha(archive)] = archive
    object.__setattr__(entry.weights.digest, "root", sha(archive))
    object.__setattr__(entry.weights.size, "root", len(archive))
    del source.blobs[old]
    with pytest.raises(PackageInvalidError, match=r"풀지 못했다|adapter_config\.json"):
        await load_package(source, Engine(), inspected, tmp_path / "work")
    assert not (tmp_path / "escape.txt").exists() and not (tmp_path / "work" / "escape.txt").exists()


async def test_engine_refusal_unloads_what_was_loaded(tmp_path: Path) -> None:
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src")
    inspected = await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)
    engine = Engine(fail_on=1)
    with pytest.raises(RuntimeError):
        await load_package(source, engine, inspected, tmp_path / "work")
    assert engine.unloaded == [f"lora_a-{digest[7:19]}"]


async def test_empty_system_prompt_is_invalid(tmp_path: Path) -> None:
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src", prompts=("   ", "프롬프트 B"))
    inspected = await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)
    with pytest.raises(PackageInvalidError, match="비었다"):
        await load_package(source, Engine(), inspected, tmp_path / "work")


async def test_package_for_another_base_model_is_invalid(tmp_path: Path) -> None:
    """어댑터는 학습한 기반 모델에만 맞는다. 프로파일 표의 기반 모델과 다르면 적재하지 않는다(D74)."""
    source = MemorySource()
    digest = publish_memory(source, tmp_path / "src", base_model="Qwen/Qwen3-1.7B")
    with pytest.raises(PackageInvalidError, match="기반 모델"):
        await inspect_package(source, digest, tmp_path / "work", "0.1.0", BASE_MODEL)
