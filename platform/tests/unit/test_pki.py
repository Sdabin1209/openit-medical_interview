"""platform 의 pki(신뢰의 뿌리·인증서 수명 계산)와 감시 규칙의 일관성을 본다. docker 는 부르지 않는다(옛 위치: tools/checks/tests/test_deploy_pki.py)."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from openit_platform import pki as pki_module

NOW = datetime(2026, 11, 10, 9, 0, 0, tzinfo=UTC)  # 시험의 고정 시각. 인증서를 만들 때와 검증할 때 같은 값을 쓴다


def write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def pki() -> ModuleType:
    return pki_module


def _env(pki: ModuleType, repo: Path, **override: str) -> dict[str, str]:
    values: dict[str, str] = pki.parse_env_file(repo / "deploy" / "env.example")
    values.update(override)
    return values


def test_default_settings_are_valid(pki: ModuleType, repo: Path) -> None:
    env = _env(pki, repo)
    ca, registry = pki.ca_settings(env), pki.registry_settings(env)
    assert ca.leaf_minutes < ca.intermediate_minutes < ca.root_minutes
    assert registry.mode == "local" and registry.names == ["registry"]


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"OPENIT_CA_MODE": "both"}, "OPENIT_CA_MODE"),
        ({"OPENIT_LEAF_LIFETIME": "168"}, "OPENIT_LEAF_LIFETIME"),
        ({"OPENIT_LEAF_LIFETIME": "0h"}, "OPENIT_LEAF_LIFETIME"),
        ({"OPENIT_LEAF_LIFETIME": "99999h"}, "리프 < 중간 CA < 루트"),
        ({"OPENIT_CA_ALLOWED_DNS": "", "OPENIT_CA_ALLOWED_IPS": ""}, "아무것도 발급하지 못한다"),
        ({"OPENIT_CA_MODE": "institution"}, "OPENIT_CA_MODE"),  # 옛 이름: 계약 CaMode 는 self·organization
    ],
)
def test_bad_ca_settings_are_rejected(pki: ModuleType, repo: Path, override: dict[str, str], message: str) -> None:
    with pytest.raises(pki.ConfigError, match=message):
        pki.ca_settings(_env(pki, repo, **override))


def test_registry_modes(pki: ModuleType, repo: Path) -> None:
    with pytest.raises(pki.ConfigError, match="OPENIT_REGISTRY_ADDRESS"):
        pki.registry_settings(_env(pki, repo, OPENIT_REGISTRY_MODE="external"))
    with pytest.raises(pki.ConfigError, match="비워 둔다"):
        pki.registry_settings(_env(pki, repo, OPENIT_REGISTRY_ADDRESS="r.example.org"))
    external = pki.registry_settings(_env(pki, repo, OPENIT_REGISTRY_MODE="external", OPENIT_REGISTRY_ADDRESS="r.example.org/openit/"))
    assert external.address == "r.example.org/openit"


def test_env_override_must_use_known_keys(pki: ModuleType, tmp_path: Path) -> None:
    write(tmp_path, "env.example", "A=1\n")
    write(tmp_path, ".env", "B=2\n")
    with pytest.raises(pki.ConfigError, match="B"):
        pki.load_env(tmp_path)
    write(tmp_path, ".env", "A=2\n")
    assert pki.load_env(tmp_path) == {"A": "2"}


def test_ca_json_carries_acme_provisioner_policy_and_leaf_lifetime(pki: ModuleType, repo: Path) -> None:
    config: Any = pki.render_ca_json(pki.ca_settings(_env(pki, repo, OPENIT_LEAF_LIFETIME="5m", OPENIT_CA_ALLOWED_IPS="10.0.0.0/8")))
    (provisioner,) = config["authority"]["provisioners"]
    assert provisioner["type"] == "ACME" and provisioner["name"] == "acme"
    assert provisioner["claims"] == {"minTLSCertDuration": "5m", "maxTLSCertDuration": "5m", "defaultTLSCertDuration": "5m"}
    allow = config["authority"]["policy"]["x509"]["allow"]
    assert "*.openit.internal" in allow["dns"] and allow["ip"] == ["10.0.0.0/8"]
    assert config["tls"]["minVersion"] == 1.2
    assert pki.render_ca_json(pki.ca_settings(_env(pki, repo)))["authority"]["provisioners"][0]["claims"]["defaultTLSCertDuration"] == "168h"


def test_alert_threshold_matches_ca_status_threshold(pki: ModuleType, repo: Path) -> None:
    """Prometheus 규칙의 86400 초와 env.example 의 OPENIT_CA_WARN_LEAF 가 같아야 한다(두 곳이 어긋나면 경보 기준이 둘이 된다)."""
    rules = (repo / "platform" / "monitoring" / "rules.yml").read_text(encoding="utf-8")
    seconds = int(re.search(r"time\(\) < (\d+)", rules).group(1))  # type: ignore[union-attr]
    assert seconds == pki.ca_settings(_env(pki, repo)).warn_leaf_minutes * 60


def _make(subject: str, issuer: tuple[x509.Name, ec.EllipticCurvePrivateKey] | None, *, ca: bool, days: int) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)])
    issuer_name, issuer_key = issuer or (name, key)
    now = NOW
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=0 if ca and issuer else None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=ca,
                crl_sign=ca,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    )
    return builder.sign(issuer_key, hashes.SHA256()), key


def test_check_intermediate(pki: ModuleType) -> None:
    root, root_key = _make("Root", None, ca=True, days=3650)
    good, _ = _make("Inter", (root.subject, root_key), ca=True, days=1000)
    assert pki.check_intermediate(good, root, now=NOW) == []
    longer, _ = _make("Long", (root.subject, root_key), ca=True, days=4000)
    assert any("루트보다 오래" in p for p in pki.check_intermediate(longer, root, now=NOW))
    leaf, _ = _make("Leaf", (root.subject, root_key), ca=False, days=10)
    assert any("CA 가 참이 아니다" in p for p in pki.check_intermediate(leaf, root, now=NOW))
    other_root, _ = _make("Other", None, ca=True, days=3650)
    assert any("서명한 인증서가 아니다" in p for p in pki.check_intermediate(good, other_root, now=NOW))
    assert any("유효 기간 밖" in p for p in pki.check_intermediate(good, root, now=NOW + timedelta(days=2000)))


def test_bundle_allows_several_roots_without_duplicates(pki: ModuleType, tmp_path: Path) -> None:
    first, _ = _make("Root A", None, ca=True, days=100)
    second, _ = _make("Root B", None, ca=True, days=100)
    own = write(tmp_path, "own.crt", pki.pem_text([first]))
    write(tmp_path, "extra/b.crt", pki.pem_text([second]))
    write(tmp_path, "extra/dup.pem", pki.pem_text([first]))
    write(tmp_path, "extra/readme.txt", "무시")
    bundle = pki.build_bundle([own], tmp_path / "extra")
    assert len(x509.load_pem_x509_certificates(bundle.encode())) == 2


def test_bundle_without_roots_fails(pki: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(pki.ConfigError):
        pki.build_bundle([], tmp_path / "none")


def test_key_matches_cert(pki: ModuleType, tmp_path: Path) -> None:
    cert, key = _make("X", None, ca=True, days=10)
    path = tmp_path / "k.pem"
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(b"pw")))
    assert pki.key_matches_cert(path, b"pw", cert)
    other, _ = _make("Y", None, ca=True, days=10)
    assert not pki.key_matches_cert(path, b"pw", other)
    with pytest.raises(ValueError, match=r"(?i)password|decrypt|deserialize"):
        pki.key_matches_cert(path, b"wrong", cert)


def test_manual_certificate_alert_threshold_is_thirty_days(repo: Path) -> None:
    """조직이 준 인증서의 경보 기준(30일)은 규칙 파일과 deploy 의 ca status 가 같은 값을 쓴다(platform ADR 0005)."""
    rules = (repo / "platform" / "monitoring" / "rules.yml").read_text(encoding="utf-8")
    match = re.search(r'renewal="organization"\} - time\(\) < (\d+)', rules)
    assert match and int(match.group(1)) == 30 * 24 * 3600
    script = (repo / "deploy" / "deploy").read_text(encoding="utf-8")
    assert "ORGANIZATION_CERT_WARN_MINUTES = 30 * 24 * 60" in script


def test_verify_server_chain(pki: ModuleType) -> None:
    root_key = ec.generate_private_key(ec.SECP256R1())
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Root")])
    now = NOW
    root = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
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
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False)
        .sign(root_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    leaf = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "gateway.example")]))
        .issuer_name(root.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=5))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("gateway.example")]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(root_key, hashes.SHA256())
    )
    assert pki.verify_server_chain([leaf], [root], ["gateway.example"], now=NOW) == []
    assert pki.verify_server_chain([leaf], [root], ["other.example"], now=NOW)  # 이름이 다르다
    stranger, _ = _make("Stranger", None, ca=True, days=3650)
    assert pki.verify_server_chain([leaf], [stranger], ["gateway.example"], now=NOW)  # 신뢰하지 않는 루트
