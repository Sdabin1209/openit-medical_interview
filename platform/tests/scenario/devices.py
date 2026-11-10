"""시험용 기기 PKI: 조직 CA, 허용한 기기, 허용 목록에 없는 기기, 모르는 CA 가 낸 기기 인증서. 실제 키가 아니고 시험 폴더에서만 쓴다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


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
        key_path.write_bytes(self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        return cert_path, key_path


# 왜 고정한 넓은 기간: 입구(Envoy)는 실제 시각으로 유효 기간을 본다. 시험이 지금 시각에 기대지 않게 한다
NOT_BEFORE = datetime(2020, 1, 1, tzinfo=UTC)
NOT_AFTER = datetime(2100, 1, 1, tzinfo=UTC)


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def make_ca(common_name: str) -> Issued:
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(common_name))
        .issuer_name(_name(common_name))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOT_BEFORE)
        .not_valid_after(NOT_AFTER)
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


def make_device(ca: Issued, device_id: str, *, serial: int | None = None) -> Issued:
    """기기 인증서: 주체 CN 이 기기 ID 이고 클라이언트 인증 용도다(계약 DeviceId: 인증서 주체의 CN)."""
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(device_id))
        .issuer_name(ca.cert.subject)
        .public_key(key.public_key())
        .serial_number(serial if serial is not None else x509.random_serial_number() >> 64)  # 일련번호는 20옥텟 이하(RFC 5280). 시험은 짧게 둔다
        .not_valid_before(NOT_BEFORE)
        .not_valid_after(NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca.key.public_key()), critical=False)
        .sign(ca.key, hashes.SHA256())
    )
    return Issued(cert, key)
