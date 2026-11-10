"""계약 9.0.0 이 영역에 넘긴 입력들: 엔진 주소, 이름 표, 레지스트리 자격(기본 인증), 클라이언트 인증서, 프로파일
표, 평문 서버."""

import base64
import json
import socket
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from fakes.pki import make_pki
from fakes.registry import FakeRegistry
from fakes.servers import run_server
from model_runtime import serve
from model_runtime.link.hosts import install_hosts_table, read_hosts_table
from model_runtime.link.publish_registry import OciPackagePublisher, package_tag
from model_runtime.link.registry import OciPackageSource, basic_credentials
from model_runtime.main import SecretError, Settings, read_secret
from model_runtime.store.profiles import UnknownProfileError, load_profile
from model_runtime.types import RegistryUnavailableError
from package_factory import REPO, built, sha
from support import REGISTRY_PASSWORD, REGISTRY_USER, settings_for

pytestmark = pytest.mark.anyio


# ---- 이름 표(HostsTable) ----------------------------------------------------------------


def write_table(path: Path, *rows: tuple[str, str]) -> Path:
    path.write_text(json.dumps({"hosts": [{"name": n, "address": a} for n, a in rows]}), encoding="utf-8")
    return path


def test_hosts_table_is_read_with_the_contract_schema(tmp_path: Path) -> None:
    table = write_table(
        tmp_path / "hosts.json", ("Registry.Openit.Test", "192.0.2.11"), ("survey-service", "192.0.2.10")
    )
    assert read_hosts_table(table) == {"registry.openit.test": "192.0.2.11", "survey-service": "192.0.2.10"}
    seven = write_table(tmp_path / "many.json", *[(f"h{i}", "192.0.2.1") for i in range(7)])
    with pytest.raises(ValidationError):  # 계약 HostsTable 은 최대 6줄
        read_hosts_table(seven)
    (tmp_path / "bad.json").write_text('{"hosts": [{"name": "x"}]}', encoding="utf-8")
    with pytest.raises(ValidationError):
        read_hosts_table(tmp_path / "bad.json")


def test_hosts_table_resolves_listed_names_only_and_can_be_removed() -> None:
    restore = install_hosts_table({"registry.openit.test": "127.0.0.1"})
    try:
        listed = socket.getaddrinfo("Registry.Openit.Test", 443, type=socket.SOCK_STREAM)
        assert listed[0][4][0] == "127.0.0.1"
        other = socket.getaddrinfo("localhost", 443, type=socket.SOCK_STREAM)  # 표에 없는 이름은 시스템 풀이
        assert other[0][4][1] == 443
    finally:
        restore()
    with pytest.raises(socket.gaierror):
        socket.getaddrinfo("registry.openit.test", 443)


async def test_registry_is_reached_by_its_listed_name_with_tls_checked_against_that_name(tmp_path: Path) -> None:
    pki = make_pki(tmp_path / "pki")
    registry = FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD)
    package = built(tmp_path)
    with run_server(registry.app(), pki) as running:
        port = running.url.rsplit(":", 1)[1]
        url = f"https://registry.openit.test:{port}"  # 이 이름은 DNS 에 없다
        restore = install_hosts_table(
            read_hosts_table(write_table(tmp_path / "h.json", ("registry.openit.test", "127.0.0.1")))
        )
        try:
            publisher = OciPackagePublisher(url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root)
            publisher.publish(package)
            source = OciPackageSource(url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root, None)
            assert (await source.fetch_manifest(package.digest)).content == package.manifest
            publisher.close()
            source.close()
        finally:
            restore()


# ---- 레지스트리 자격(HTTP 기본 인증, RFC 7617) -----------------------------------------


def test_credentials_line_is_user_colon_password() -> None:
    assert basic_credentials("reader:secret") == ("reader", "secret")
    assert basic_credentials("reader:pa:ss:word") == (
        "reader",
        "pa:ss:word",
    )  # 비밀번호에는 콜론이 들어갈 수 있다(RFC 7617 2)
    assert basic_credentials("reader:") == ("reader", "")
    for bad in ("", "nocolon", ":nouser"):
        with pytest.raises(ValueError, match="사용자:비밀번호"):
            basic_credentials(bad)


def test_credentials_file_is_read_as_one_line_without_the_newline(tmp_path: Path) -> None:
    (tmp_path / "c").write_text("reader:secret\n", encoding="utf-8")
    assert read_secret("X", {"X_FILE": str(tmp_path / "c")}) == "reader:secret"
    with pytest.raises(SecretError):
        read_secret("X", {})


async def test_basic_authorization_is_rfc_7617_and_a_registry_without_auth_still_works(tmp_path: Path) -> None:
    """도전(401 Basic)을 받으면 `Basic base64(사용자:비밀번호)` 로 답한다(RFC 7617 2). 인증이 없는 로컬
    레지스트리는 도전이 없어
    그대로 돈다."""
    pki = make_pki(tmp_path / "pki")
    expected = "Basic " + base64.b64encode(b"reader:pa:ss").decode()
    challenged = FakeRegistry("reader", "pa:ss")
    open_registry = FakeRegistry("", "")
    open_registry.expected = ""  # 인증을 요구하지 않는다
    with run_server(challenged.app(), pki) as secured, run_server(open_registry.app(), pki) as local:
        for running in (secured, local):
            source = OciPackageSource(running.url, REPO, basic_credentials("reader:pa:ss"), pki.root, None)
            assert await source.list_manifests() == []
            source.close()
    assert challenged.requests, "인증이 필요한 레지스트리에 닿았다"
    assert challenged.expected == expected  # 서버가 받아들이는 값이 RFC 7617 형식과 같다


# ---- 클라이언트 인증서(계약 OPENIT_TLS_CERTIFICATE_FILE·KEY) ------------------------------


@pytest.fixture
def no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """oras 는 실패한 요청을 5번 다시 보내며 사이에 쉰다(2+3^n 초). 시험은 쉬지 않게 해 다시 보내기만 거친다."""

    def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(time, "sleep", no_sleep)


async def test_client_certificate_is_shown_to_a_registry_that_requires_mtls(
    tmp_path: Path, no_retry_sleep: None
) -> None:
    pki = make_pki(tmp_path / "pki")
    package = built(tmp_path)
    registry = FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD)
    with run_server(registry.app(), pki, require_client_cert=True) as running:
        with_cert = OciPackageSource(
            running.url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root, None, (pki.client_cert, pki.client_key)
        )
        registry.manifests[package.digest] = (package.manifest, "application/vnd.oci.image.manifest.v1+json")
        assert (await with_cert.fetch_manifest(package.digest)).digest == package.digest
        without = OciPackageSource(running.url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root, None)
        with pytest.raises(RegistryUnavailableError):
            await without.fetch_manifest(package.digest)
        with_cert.close()
        without.close()


async def test_missing_client_certificate_file_is_unavailable_not_a_crash(tmp_path: Path, no_retry_sleep: None) -> None:
    pki = make_pki(tmp_path / "pki")
    with run_server(FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD).app(), pki) as running:
        source = OciPackageSource(
            running.url,
            REPO,
            (REGISTRY_USER, REGISTRY_PASSWORD),
            pki.root,
            None,
            (tmp_path / "no.pem", tmp_path / "no.key"),
        )
        with pytest.raises(RegistryUnavailableError):
            await source.fetch_manifest("sha256:" + "0" * 64)
        source.close()


# ---- 게시된 패키지 목록(태그 목록과 매니페스트 조회) ---------------------------------------


async def test_listing_follows_tag_pagination_and_skips_other_tags(tmp_path: Path) -> None:
    pki = make_pki(tmp_path / "pki")
    registry = FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD)
    with run_server(registry.app(), pki) as running:
        publisher = OciPackagePublisher(running.url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root)
        digests: set[str] = set()
        for index in range(4):  # 쪽 크기 100 을 못 채우므로 쪽 나누기는 작은 쪽으로 따로 본다
            sub = tmp_path / f"p{index}"
            sub.mkdir()
            digests.add(publisher.publish(built(sub, seed=str(index))))
        registry.tags["latest"] = sorted(digests)[0]  # 패키지 태그가 아닌 태그는 목록에 들지 않는다
        source = OciPackageSource(running.url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root, None)
        assert {raw.digest for raw in await source.list_manifests()} == digests
        assert all(sha(raw.content) == raw.digest for raw in await source.list_manifests())
        small_pages = OciPackageSource(
            running.url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root, None, tags_page=2
        )  # 쪽 나누기(Link rel=next)를 따라가는지 본다
        assert {raw.digest for raw in await small_pages.list_manifests()} == digests
        small_pages.close()
        assert any(path.endswith("tags/list") for _, path in registry.requests)
        publisher.close()
        source.close()


async def test_listing_an_unknown_repository_is_empty_and_wrong_credentials_are_unavailable(tmp_path: Path) -> None:
    pki = make_pki(tmp_path / "pki")
    with run_server(FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD).app(), pki) as running:
        good = OciPackageSource(running.url, REPO, (REGISTRY_USER, REGISTRY_PASSWORD), pki.root, None)
        assert await good.list_manifests() == []
        bad = OciPackageSource(running.url, REPO, (REGISTRY_USER, "nope"), pki.root, None)
        with pytest.raises(RegistryUnavailableError):
            await bad.list_manifests()
        good.close()
        bad.close()


def test_package_tag_is_a_valid_oci_tag_made_from_the_digest() -> None:
    digest = "sha256:" + "ab" * 32
    assert package_tag(digest) == "sha256-" + "ab" * 32
    assert len(package_tag(digest)) <= 128  # OCI Distribution Spec 의 태그 길이 한도


# ---- 프로파일 표 ------------------------------------------------------------------------


def test_profile_table_gives_the_base_model() -> None:
    assert load_profile("gpu-12g").base_model.root == "Qwen/Qwen3-1.7B"
    assert load_profile("rtx4090-24g").base_model.root == "Qwen/Qwen3-8B"
    with pytest.raises(UnknownProfileError, match="gpu-12g"):
        load_profile("no-such-profile")


def test_profile_table_shape_is_validated() -> None:
    with pytest.raises(ValidationError):
        load_profile("x", '{"profiles": {"x": {"base_model": "bad name with spaces"}}}')
    with pytest.raises(ValidationError):
        load_profile("x", '{"profiles": {"x": {"base_model": "Qwen/Qwen3-8B", "gpu": 1}}}')


# ---- 서버는 TLS 를 끝내지 않는다 -------------------------------------------------------------


def test_server_listens_on_the_given_port_in_plain_http(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pki = make_pki(tmp_path / "pki")
    settings = settings_for(tmp_path, pki, "https://registry.invalid", listen_port=8123)
    calls: list[dict[str, object]] = []

    def fake_create_app(_settings: Settings) -> str:
        return "app"

    def fake_run(app: object, **kwargs: object) -> None:
        calls.append({"app": app, **kwargs})

    monkeypatch.setattr(serve, "Settings", lambda: settings)
    monkeypatch.setattr(serve, "create_app", fake_create_app)
    monkeypatch.setattr(serve.uvicorn, "run", fake_run)
    assert serve.main() == 0
    (call,) = calls
    assert call["port"] == 8123 and call["host"] == "0.0.0.0"  # noqa: S104
    assert not any(key.startswith("ssl_") for key in call)  # TLS 인자가 없다(영역 게이트웨이가 끝낸다)
