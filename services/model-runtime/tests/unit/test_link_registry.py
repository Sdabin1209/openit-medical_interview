"""link_registry 와 게시 길: 실제 소켓의 시험용 OCI 레지스트리(TLS, 사설 루트, 기본 인증)로 push·pull 한다."""

from pathlib import Path

import pytest

from fakes.pki import make_pki
from fakes.registry import FakeRegistry
from fakes.servers import run_server
from model_runtime.link.publish_registry import OciPackagePublisher, PublishError
from model_runtime.link.registry import OciPackageSource
from model_runtime.types import PackageNotFoundError, RegistryUnavailableError
from package_factory import REPO, built, sha
from support import REGISTRY_PASSWORD, REGISTRY_USER

pytestmark = pytest.mark.anyio


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
