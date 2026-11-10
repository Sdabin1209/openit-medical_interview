"""link_registry 와 게시 길: 실제 소켓의 시험용 OCI 레지스트리(TLS, 사설 루트, 기본 인증)로 push·pull 한다."""

from pathlib import Path

import pytest

from fakes.pki import make_pki
from fakes.registry import FakeRegistry
from fakes.servers import connect_tunnel, run_server
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


# ---- 레지스트리 이름의 모양과 저장소 경로(게시·받기·목록이 같은 경로) -----------------------------


@pytest.mark.parametrize("registry_name", ["registry", "registry:443", "registry.openit.test"])
async def test_publish_fetch_and_list_use_the_same_repository_path_for_any_registry_name(
    tmp_path: Path, registry_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """레지스트리 이름이 기본 설치 값 `registry`(점·콜론 없음), `registry:443`, 점이 있는 이름이어도 세 호출이 모두
    `/v2/<저장소>/…` 로 간다. ORAS 는 첫 조각에 점·콜론이 없으면 저장소 경로로 읽는다(oci_reference.py)."""
    pki = make_pki(tmp_path / "pki")
    registry = FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD)
    package = built(tmp_path)
    with run_server(registry.app(), pki) as running, connect_tunnel(int(running.url.rsplit(":", 1)[1])) as tunnel:
        url = f"https://{registry_name}"
        credentials = (REGISTRY_USER, REGISTRY_PASSWORD)
        # 게시 도구는 터널 인자가 없다(관리 노드에서 직접 나간다). requests 의 표준 환경 변수로 같은 터널을 쓴다
        monkeypatch.setenv("HTTPS_PROXY", tunnel.url)
        monkeypatch.delenv("NO_PROXY", raising=False)
        publisher = OciPackagePublisher(url, REPO, credentials, pki.root)
        source = OciPackageSource(url, REPO, credentials, pki.root, tunnel.url)
        try:
            assert publisher.publish(package) == package.digest
            assert (await source.fetch_manifest(package.digest)).content == package.manifest
            target = tmp_path / "pulled.bin"
            await source.download_blob(package.layers[0].digest, target)
            assert sha(target.read_bytes()) == package.layers[0].digest
            assert [raw.digest for raw in await source.list_manifests()] == [package.digest]
        finally:
            publisher.close()
            source.close()
    assert set(tunnel.targets) == {f"{registry_name if ':' in registry_name else registry_name + ':443'}"}
    assert registry.requests, "레지스트리에 닿았다"
    assert all(path.startswith(f"{REPO}/") or path in ("", "/") for _, path in registry.requests)
