"""deploy/pki.py(신뢰의 뿌리·인증서 수명 계산)와 감시 규칙의 일관성을 본다. docker 는 부르지 않는다."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from .conftest_helpers import write


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
        ({"OPENIT_PUBLIC_CERT_MODE": "magic"}, "OPENIT_PUBLIC_CERT_MODE"),
        ({"OPENIT_PUBLIC_CERT_MODE": "public-acme", "OPENIT_PUBLIC_NAMES": ""}, "공개 도메인"),
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
    rules = (repo / "deploy" / "monitoring" / "rules.yml").read_text(encoding="utf-8")
    seconds = int(re.search(r"time\(\) < (\d+)", rules).group(1))  # type: ignore[union-attr]
    assert seconds == pki.ca_settings(_env(pki, repo)).warn_leaf_minutes * 60


def _make(subject: str, issuer: tuple[x509.Name, ec.EllipticCurvePrivateKey] | None, *, ca: bool, days: int) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)])
    issuer_name, issuer_key = issuer or (name, key)
    now = datetime.now(UTC)
    builder = (
        x509.CertificateBuilder().subject_name(name).issuer_name(issuer_name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=0 if ca and issuer else None), critical=True)
        .add_extension(
            x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False, key_agreement=False,
                          key_cert_sign=ca, crl_sign=ca, encipher_only=False, decipher_only=False),
            critical=True,
        )
    )
    return builder.sign(issuer_key, hashes.SHA256()), key


def test_check_intermediate(pki: ModuleType) -> None:
    root, root_key = _make("Root", None, ca=True, days=3650)
    good, _ = _make("Inter", (root.subject, root_key), ca=True, days=1000)
    assert pki.check_intermediate(good, root) == []
    longer, _ = _make("Long", (root.subject, root_key), ca=True, days=4000)
    assert any("루트보다 오래" in p for p in pki.check_intermediate(longer, root))
    leaf, _ = _make("Leaf", (root.subject, root_key), ca=False, days=10)
    assert any("CA 가 참이 아니다" in p for p in pki.check_intermediate(leaf, root))
    other_root, _ = _make("Other", None, ca=True, days=3650)
    assert any("서명한 인증서가 아니다" in p for p in pki.check_intermediate(good, other_root))
    assert any("유효 기간 밖" in p for p in pki.check_intermediate(good, root, now=datetime.now(UTC) + timedelta(days=2000)))


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
    with pytest.raises(ValueError, match=r"(?i)password|decrypt"):
        pki.key_matches_cert(path, b"wrong", cert)
