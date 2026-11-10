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
        ({"OPENIT_PUBLIC_NAMES": "bad name"}, "OPENIT_PUBLIC_NAMES"),
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


def test_optional_inputs_have_the_contract_names_and_defaults(repo: Path) -> None:
    """계약 PlatformEnv 의 선택 입력 여섯: 없으면 기본값이고 값이 있으면 계약 스키마로 검증한다."""
    from openit_platform import settings
    from openit_platform.contract.models import PlatformEnv

    optional = {
        "OPENIT_PUBLIC_NAMES",
        "OPENIT_INGRESS_CERTIFICATE_FILE",
        "OPENIT_INGRESS_PRIVATE_KEY_FILE",
        "OPENIT_SERVICE_PORT",
        "OPENIT_ALERT_SMTP_SMARTHOST",
        "OPENIT_ALERT_HEARTBEAT_INTERVAL",
    }
    assert optional <= set(PlatformEnv.model_fields) and all(not PlatformEnv.model_fields[key].is_required() for key in optional)
    bare = {key: "" for key in optional}
    cfg = platform_settings(repo, **bare)
    assert cfg.public_names == ("openit.internal",)  # 이름을 안 주면 발급자의 호스트
    assert cfg.service_port == settings.DEFAULT_SERVICE_PORT and cfg.alert_heartbeat_interval == settings.DEFAULT_HEARTBEAT_INTERVAL
    assert cfg.ingress_certificate_file is None and cfg.alert_smtp_smarthost == ""
    given = platform_settings(repo, OPENIT_SERVICE_PORT="9443", OPENIT_ALERT_HEARTBEAT_INTERVAL="90s", OPENIT_PUBLIC_NAMES="openit.internal, registry")
    assert given.service_port == 9443 and given.alert_heartbeat_interval == "90s" and given.public_names == ("openit.internal", "registry")


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"OPENIT_ALERT_HEARTBEAT_INTERVAL": "soon"}, "OPENIT_ALERT_HEARTBEAT_INTERVAL"),
        ({"OPENIT_ALERT_HEARTBEAT_INTERVAL": "0m"}, "OPENIT_ALERT_HEARTBEAT_INTERVAL"),
        ({"OPENIT_ALERT_RECEIVER_URL": "mailto:ops@example.org", "OPENIT_ALERT_SMTP_SMARTHOST": "no-port"}, "OPENIT_ALERT_SMTP_SMARTHOST"),
        ({"OPENIT_SERVICE_PORT": "70000"}, "OPENIT_SERVICE_PORT"),
        ({"OPENIT_SERVICE_PORT": "https"}, "정수"),
        ({"OPENIT_PUBLIC_NAMES": "openit.internal,openit.internal"}, "같은 이름"),
    ],
)
def test_optional_inputs_are_checked_against_the_contract(repo: Path, override: dict[str, str], message: str) -> None:
    with pytest.raises(pki.ConfigError, match=message):
        platform_settings(repo, **override)
