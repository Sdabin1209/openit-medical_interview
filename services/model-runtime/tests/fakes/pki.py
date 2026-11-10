"""시험용 사설 PKI(루트 CA, 서버 인증서, 클라이언트 인증서). 시험이 임시 폴더에 만들고 끝나면 사라진다. 비밀은 실제
값이 아니다."""

import datetime
import ipaddress
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


@dataclass(frozen=True)
class Pki:
    root: Path
    server_cert: Path
    server_key: Path
    client_cert: Path
    client_key: Path


def _name(common: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common)])


def _write_key(path: Path, key: ec.EllipticCurvePrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )


def _issue(
    ca_key: ec.EllipticCurvePrivateKey,
    ca_name: x509.Name,
    common: str,
    usage: x509.ObjectIdentifier,
    names: list[x509.GeneralName],
) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.datetime.now(datetime.UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(common))
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
    )
    if names:
        builder = builder.add_extension(x509.SubjectAlternativeName(names), critical=False)
    return builder.sign(ca_key, hashes.SHA256()), key


def make_pki(folder: Path) -> Pki:
    """루트 CA 하나와 그가 서명한 서버·클라이언트 인증서를 folder 에 만든다."""
    folder.mkdir(parents=True, exist_ok=True)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = _name("openit-test-root")
    now = datetime.datetime.now(datetime.UTC)
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    hosts: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName("registry.openit.test"),  # 이름 표 시험이 가짜 이름을 127.0.0.1 로 풀어 접속한다
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]
    server, server_key = _issue(ca_key, ca_name, "localhost", ExtendedKeyUsageOID.SERVER_AUTH, hosts)
    client, client_key = _issue(ca_key, ca_name, "survey-service", ExtendedKeyUsageOID.CLIENT_AUTH, [])
    pki = Pki(
        root=folder / "root.pem",
        server_cert=folder / "server.pem",
        server_key=folder / "server.key",
        client_cert=folder / "client.pem",
        client_key=folder / "client.key",
    )
    pki.root.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    pki.server_cert.write_bytes(server.public_bytes(serialization.Encoding.PEM))
    pki.client_cert.write_bytes(client.public_bytes(serialization.Encoding.PEM))
    _write_key(pki.server_key, server_key)
    _write_key(pki.client_key, client_key)
    return pki
