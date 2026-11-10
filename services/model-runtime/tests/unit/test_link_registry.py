"""link_registry 와 게시 길: 실제 소켓의 시험용 OCI 레지스트리(TLS, 사설 루트, 기본 인증)로 push·pull 한다."""

from pathlib import Path

import pytest

from fakes.pki import make_pki
from fakes.registry import FakeRegistry
from fakes.servers import run_server
from model_runtime.components.package_publish import AdapterFiles, BuiltPackage, build_package, pack_adapter_folder
from model_runtime.link.publish_registry import OciPackagePublisher, PublishError
from model_runtime.link.registry import OciPackageSource
from model_runtime.types import PackageNotFoundError, RegistryUnavailableError
from package_factory import EVALUATION, SERVING, sha
from support import REGISTRY_PASSWORD, REGISTRY_USER, adapter_folder

pytestmark = pytest.mark.anyio
REPO = "openit/model-package"


def built(tmp: Path) -> BuiltPackage:
    adapters: dict[str, AdapterFiles] = {}
    for role in ("LORA_A", "LORA_B"):
        archive = tmp / f"{role}.tar"
        pack_adapter_folder(adapter_folder(tmp, role, role.encode()), archive)
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


async def test_push_then_pull_by_digest(tmp_path: Path) -> None:
    pki = make_pki(tmp_path / "pki")
    registry = FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD)
    package = built(tmp_path)
    with run_server(registry.app(), pki) as running:
        publisher = OciPackagePublisher(running.url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root)
        assert publisher.publish(package) == package.digest
        assert set(registry.blobs) == {package.config.digest, *(layer.digest for layer in package.layers)}
        source = OciPackageSource(running.url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root, None)
        raw = await source.fetch_manifest(package.digest)
        assert raw.content == package.manifest and sha(raw.content) == package.digest
        target = tmp_path / "pulled" / "a.bin"
        await source.download_blob(package.layers[0].digest, target)
        assert sha(target.read_bytes()) == package.layers[0].digest
        publisher.close()
        source.close()


async def test_missing_manifest_and_blob_are_not_found(tmp_path: Path) -> None:
    pki = make_pki(tmp_path / "pki")
    with run_server(FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD).app(), pki) as running:
        source = OciPackageSource(running.url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root, None)
        with pytest.raises(PackageNotFoundError):
            await source.fetch_manifest("sha256:" + "0" * 64)
        with pytest.raises(PackageNotFoundError):
            await source.download_blob("sha256:" + "0" * 64, tmp_path / "x")
        source.close()


async def test_wrong_credentials_and_untrusted_root_are_unavailable(tmp_path: Path) -> None:
    pki = make_pki(tmp_path / "pki")
    other = make_pki(tmp_path / "other-pki")
    with run_server(FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD).app(), pki) as running:
        bad_password = OciPackageSource(running.url, REPO, (REGISTRY_USER, "nope"), pki.root, None)
        with pytest.raises(RegistryUnavailableError):
            await bad_password.fetch_manifest("sha256:" + "0" * 64)
        untrusted = OciPackageSource(
            running.url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), other.root, None
        )  # 사설 루트가 다르다
        with pytest.raises(RegistryUnavailableError):
            await untrusted.fetch_manifest("sha256:" + "0" * 64)
        bad_password.close()
        untrusted.close()


def test_publish_with_wrong_credentials_fails_without_leaking_them(tmp_path: Path) -> None:
    pki = make_pki(tmp_path / "pki")
    package = built(tmp_path)
    with run_server(FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD).app(), pki) as running:
        publisher = OciPackagePublisher(running.url, REPO, (REGISTRY_USER, "leaky-password-123"), pki.root)
        try:
            with pytest.raises(PublishError) as info:
                publisher.publish(package)
        finally:
            publisher.close()
    assert "leaky-password-123" not in str(info.value)
