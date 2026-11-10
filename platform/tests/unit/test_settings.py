"""설치 설정 해석: 계약의 이름과 값, 잘못된 값은 시작 전에 멈춘다."""

from pathlib import Path

import pytest

from openit_platform import pki
from openit_platform.settings import PlatformSettings

from .helpers import platform_settings


def test_defaults_are_valid(repo: Path) -> None:
    cfg: PlatformSettings = platform_settings(repo)
    assert cfg.ingress_mode == "private" and cfg.public_names == ("openit.internal",)
    assert cfg.public_base_url == "https://openit.internal:8443" and cfg.listen_port == 8443
    assert cfg.jwks_url.startswith("http://keycloak:8080/realms/openit/")


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"OPENIT_INGRESS_CERTIFICATE_MODE": "public-acme"}, "OPENIT_INGRESS_CERTIFICATE_MODE"),  # 옛 이름
        ({"OPENIT_INGRESS_CERTIFICATE_MODE": "acme-public", "OPENIT_ACME_DIRECTORY_URL": "http://insecure/"}, "https"),
        ({"OPENIT_INGRESS_CERTIFICATE_MODE": "organization"}, "OPENIT_INGRESS_CERTIFICATE_FILE"),
        ({"OPENIT_OIDC_ISSUER_URL": "http://openit.internal:8443/realms/openit"}, "https"),
        ({"OPENIT_OIDC_ISSUER_URL": "https://openit.internal:8443/realms/other"}, "/realms/openit"),
        ({"OPENIT_OIDC_ISSUER_URL": "https://elsewhere.example/realms/openit"}, "OPENIT_PUBLIC_NAMES"),
        ({"OPENIT_PUBLIC_NAMES": "bad name"}, "DNS"),
        ({"OPENIT_PUBLIC_NAMES": "openit.example", "OPENIT_OIDC_ISSUER_URL": "https://openit.example/realms/openit"}, "OPENIT_CA_ALLOWED_DNS"),
        ({"OPENIT_LISTEN_PORT": "443"}, "1024"),
        ({"OPENIT_CA_ALLOWED_DNS": "registry,step-ca,openit.internal"}, "gateway"),
        ({"OPENIT_ALERT_RECEIVER_URL": "http://hook.example/x"}, "https 웹훅 또는 mailto"),
        ({"OPENIT_ALERT_RECEIVER_URL": "mailto:ops@example.org"}, "OPENIT_ALERT_SMTP_SMARTHOST"),
    ],
)
def test_bad_values_are_rejected(repo: Path, override: dict[str, str], message: str) -> None:
    with pytest.raises(pki.ConfigError, match=message):
        platform_settings(repo, **override)


def test_issuer_without_port_means_443(repo: Path) -> None:
    cfg = platform_settings(repo, OPENIT_OIDC_ISSUER_URL="https://openit.internal/realms/openit")
    assert cfg.public_base_url == "https://openit.internal"
