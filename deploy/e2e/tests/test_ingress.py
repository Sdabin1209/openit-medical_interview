"""입구 클라이언트: 접속은 127.0.0.1 의 게시 포트로 하되 TLS 이름·인증서 검증·Host 는 입구의 공개 이름 그대로다(로컬 TLS 서버, 네트워크 밖으로 나가지 않는다)."""

from __future__ import annotations

import json
import ssl
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from openit_e2e import devices
from openit_e2e.ingress import Ingress


def _server_cert(ca: devices.Issued, name: str) -> devices.Issued:
    from datetime import UTC, datetime, timedelta

    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
        .issuer_name(ca.cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca.key, hashes.SHA256())
    )
    return devices.Issued(cert, key)


class Echo(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        peer = self.connection.getpeercert()  # type: ignore[attr-defined]
        subject = dict(item[0] for item in peer["subject"]) if peer else {}
        body = json.dumps({"host": self.headers["Host"], "path": self.path, "client_cn": subject.get("commonName")}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def server(tmp_path: Path) -> Iterator[tuple[int, Path, devices.Issued, devices.Issued]]:
    ca = devices.make_ca("Test CA")
    server_cert = _server_cert(ca, "openit.internal")
    device = devices.make_device(ca, "kiosk-x")
    trust = tmp_path / "trust.pem"
    trust.write_bytes(ca.cert.public_bytes(serialization.Encoding.PEM))
    cert_file, key_file = server_cert.write(tmp_path, "server")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_file), str(key_file))
    context.load_verify_locations(str(trust))
    context.verify_mode = ssl.CERT_OPTIONAL
    httpd = HTTPServer(("127.0.0.1", 0), Echo)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1], trust, ca, device
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_connects_to_the_published_port_with_the_public_name(server: tuple[int, Path, devices.Issued, devices.Issued]) -> None:
    port, trust, _, _ = server
    with Ingress(port, trust).client() as client:
        reply = client.get("/v1/x?y=1")
    assert reply.status_code == 200
    assert reply.json() == {
        "host": "openit.internal:8443",
        "path": "/v1/x?y=1",
        "client_cn": None,
    }  # Host 는 공개 이름과 포트, 포트는 게시 포트로 바뀌어 접속했다


def test_device_certificate_is_presented(server: tuple[int, Path, devices.Issued, devices.Issued], tmp_path: Path) -> None:
    port, trust, _, device = server
    files = device.write(tmp_path, "device")
    with Ingress(port, trust).client(device=files) as client:
        assert client.get("/").json()["client_cn"] == "kiosk-x"


def test_certificate_from_an_untrusted_ca_is_refused(server: tuple[int, Path, devices.Issued, devices.Issued], tmp_path: Path) -> None:
    port, _, _, _ = server
    other = tmp_path / "other.pem"
    other.write_bytes(devices.make_ca("Other CA").cert.public_bytes(serialization.Encoding.PEM))
    with pytest.raises(httpx.ConnectError), Ingress(port, other).client() as client:
        client.get("/")


def test_device_serial_numbers_fit_the_rfc5280_limit() -> None:
    ca = devices.make_ca("Test CA")
    assert len(devices.make_device(ca, "d").cert.serial_number.to_bytes(21, "big").lstrip(b"\0")) <= 20
