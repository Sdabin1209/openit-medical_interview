"""시험용 기기 PKI: 조직 CA 와 허용 목록에 올린 키오스크 기기 인증서. 샌드박스 설치 안에서만 쓰고 끝나면 지워진다(실제 키가 아니다).

기기 인증서의 모양은 계약 DeviceId(주체의 CN)와 DeviceAllowlist(기기 ID·일련번호)를 따른다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

# 왜 하루: E2E 한 번(수십 분)보다 길면 된다. 샌드박스와 함께 사라지는 시험용이라 더 길 이유가 없다
DEVICE_VALIDITY = timedelta(days=1)
# 왜 10년: `./deploy ca status` 가 기기 CA(조직 PKI 루트)의 남은 기간을 OPENIT_CA_WARN_ROOT(기본 4320h = 180일)와 견주어 실패로 본다. 조직 루트의 일반 수명(OPENIT_CA_ROOT_LIFETIME 기본 87600h = 10년)과 같게 둔다.
# 개인 키는 이 샌드박스 폴더에만 있고 끝나면 지워진다
CA_VALIDITY = timedelta(days=3650)


@dataclass(frozen=True)
class Issued:
    cert: x509.Certificate
    key: ec.EllipticCurvePrivateKey

    @property
    def serial_hex(self) -> str:
        return format(self.cert.serial_number, "x")

    def write(self, folder: Path, name: str) -> tuple[Path, Path]:
        cert_path, key_path = folder / f"{name}.crt", folder / f"{name}.key"
        cert_path.write_bytes(self.cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        )
        key_path.chmod(0o600)
        return cert_path, key_path


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def make_ca(common_name: str) -> Issued:
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(common_name))
        .issuer_name(_name(common_name))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + CA_VALIDITY)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    return Issued(cert, key)


def make_device(ca: Issued, device_id: str) -> Issued:
    """기기 인증서: 주체 CN 이 기기 ID 이고 클라이언트 인증 용도다."""
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(device_id))
        .issuer_name(ca.cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number() >> 64)  # 일련번호는 20옥텟 이하(RFC 5280). 짧게 둔다
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + DEVICE_VALIDITY)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca.key.public_key()), critical=False)
        .sign(ca.key, hashes.SHA256())
    )
    return Issued(cert, key)


def write_allowlist(path: Path, devices: dict[str, Issued]) -> None:
    """허용 목록(계약 DeviceAllowlist): 기기 ID 와 인증서 일련번호."""
    entries = [{"device_id": name, "serial_number": issued.serial_hex} for name, issued in devices.items()]
    path.write_text(json.dumps({"devices": entries}), encoding="utf-8")
