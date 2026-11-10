"""platform 설정 해석(설치 설정 -> 생성기 입력). docker 를 부르지 않는 순수 함수만 둔다.

설치 설정의 이름은 계약 PlatformEnv 를 따른다(platform ADR 0001). 계약에 없는 설치 값은 change-requests/platform-001 에 적었다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from . import pki
from .pki import ConfigError

REALM = "openit"  # 왜 고정: 계약 OidcIssuerUrl 의 예시가 /realms/openit 이고 realm 은 platform 이 만든다(realm 파일 하나, platform ADR 0003)
DNS_NAME_RE = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")  # RFC 1123 2.1
GATEWAY_NAME = "gateway"  # 영역들이 입구(게이트웨이)를 부르는 이름이다. 나가는 터널 주소와 영역 사이 mTLS 의 클라이언트 인증서 이름이 된다
MIN_UNPRIVILEGED_PORT = 1024  # 입구는 비 root 로 돌아 낮은 포트를 열지 못한다


@dataclass(frozen=True)
class PlatformSettings:
    ingress_mode: str
    public_names: tuple[str, ...]
    issuer: str
    public_host: str
    public_port: int
    listen_port: int
    service_port: int
    acme_directory_url: str
    internal_acme_directory_url: str
    device_ca_file: Path | None
    device_allowlist_file: Path
    exposures_dir: Path
    machine_tokens_file: Path
    ingress_certificate_file: Path | None
    ingress_private_key_file: Path | None
    alert_receiver_url: str
    alert_smtp_smarthost: str
    alert_heartbeat_minutes: int

    @property
    def public_base_url(self) -> str:
        default = self.public_port == 443
        return f"https://{self.public_host}" + ("" if default else f":{self.public_port}")

    @property
    def jwks_url(self) -> str:
        """입구가 서명 공개 키를 읽는 안쪽 주소. 발급자 주소(입구를 지난다)가 아니라 Keycloak 에 바로 간다(입구가 시작하기 전에도 읽을 수 있게)."""
        return f"http://keycloak:8080/realms/{REALM}/protocol/openid-connect/certs"


def _names_allowed(names: tuple[str, ...], allowed: list[str]) -> list[str]:
    def ok(name: str) -> bool:
        return any(name == rule or (rule.startswith("*.") and name.endswith(rule[1:])) for rule in allowed)

    return [name for name in names if not ok(name)]


def platform_settings(env: dict[str, str], deploy_dir: Path) -> PlatformSettings:
    mode = env["OPENIT_INGRESS_CERTIFICATE_MODE"]
    if mode not in pki.INGRESS_MODES:
        raise ConfigError(f"OPENIT_INGRESS_CERTIFICATE_MODE 는 {', '.join(pki.INGRESS_MODES)} 중 하나여야 한다(현재 '{mode}')")
    names = tuple(item for item in (part.strip() for part in env["OPENIT_PUBLIC_NAMES"].split(",")) if item)
    if not names:
        raise ConfigError("OPENIT_PUBLIC_NAMES 는 비울 수 없다(입구 인증서의 이름이다)")
    bad = [name for name in names if not DNS_NAME_RE.match(name)]
    if bad or len(set(names)) != len(names):
        raise ConfigError(f"OPENIT_PUBLIC_NAMES 는 중복 없는 DNS 이름(RFC 1123)이어야 한다: {', '.join(bad) or '중복'}")
    issuer = env["OPENIT_OIDC_ISSUER_URL"].strip()
    parsed = urlsplit(issuer)
    if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment:
        raise ConfigError("OPENIT_OIDC_ISSUER_URL 은 https 주소여야 한다(계약 OidcIssuerUrl, OIDC Discovery 1.0 3)")
    if parsed.path != f"/realms/{REALM}":
        raise ConfigError(f"OPENIT_OIDC_ISSUER_URL 은 /realms/{REALM} 으로 끝나야 한다(현재 경로 '{parsed.path}')")
    if parsed.hostname not in names:
        raise ConfigError("OPENIT_OIDC_ISSUER_URL 의 호스트는 OPENIT_PUBLIC_NAMES 안에 있어야 한다(입구가 그 이름의 인증서를 낸다)")
    ports: dict[str, int] = {}
    for key in ("OPENIT_LISTEN_PORT", "OPENIT_SERVICE_PORT"):
        try:
            ports[key] = int(env[key])
        except ValueError as error:
            raise ConfigError(f"{key} 는 정수여야 한다") from error
        if not MIN_UNPRIVILEGED_PORT <= ports[key] <= 65535:
            raise ConfigError(f"{key} 는 {MIN_UNPRIVILEGED_PORT}~65535 여야 한다(비 root 로 돈다)")
    acme = env["OPENIT_ACME_DIRECTORY_URL"].strip()
    if mode == "acme-public" and not acme.startswith("https://"):
        raise ConfigError("acme-public 은 OPENIT_ACME_DIRECTORY_URL(https)이 있어야 한다(계약 AcmeDirectoryUrl)")
    ca = pki.ca_settings(env)
    if mode == "private":
        outside = _names_allowed(names, ca.allowed_dns)
        if outside:
            raise ConfigError(f"OPENIT_PUBLIC_NAMES 가 OPENIT_CA_ALLOWED_DNS 밖이다(사설 CA 가 발급하지 않는다): {', '.join(outside)}")
    if _names_allowed((GATEWAY_NAME,), ca.allowed_dns):
        raise ConfigError(f"OPENIT_CA_ALLOWED_DNS 에 '{GATEWAY_NAME}' 가 있어야 한다(입구가 영역 서비스에 보일 클라이언트 인증서의 이름)")

    def optional(key: str) -> Path | None:
        value = env[key].strip()
        return pki.resolve_path(deploy_dir, value) if value else None

    cert, key = optional("OPENIT_INGRESS_CERTIFICATE_FILE"), optional("OPENIT_INGRESS_PRIVATE_KEY_FILE")
    if mode == "organization" and (cert is None or key is None):
        raise ConfigError("organization 은 OPENIT_INGRESS_CERTIFICATE_FILE 과 OPENIT_INGRESS_PRIVATE_KEY_FILE 이 있어야 한다")
    receiver = env["OPENIT_ALERT_RECEIVER_URL"].strip()
    if receiver:
        scheme = urlsplit(receiver).scheme
        if scheme not in ("https", "mailto"):
            raise ConfigError("OPENIT_ALERT_RECEIVER_URL 은 https 웹훅 또는 mailto 여야 한다(계약 AlertReceiverUrl)")
        if scheme == "mailto" and not env["OPENIT_ALERT_SMTP_SMARTHOST"].strip():
            raise ConfigError("mailto 수신처는 OPENIT_ALERT_SMTP_SMARTHOST(<호스트>:<포트>)가 있어야 한다")
    return PlatformSettings(
        ingress_mode=mode,
        public_names=names,
        issuer=issuer,
        public_host=parsed.hostname,
        public_port=parsed.port or 443,
        listen_port=ports["OPENIT_LISTEN_PORT"],
        service_port=ports["OPENIT_SERVICE_PORT"],
        acme_directory_url=acme,
        internal_acme_directory_url=env["OPENIT_INTERNAL_ACME_DIRECTORY_URL"],
        device_ca_file=optional("OPENIT_DEVICE_CA_CERTIFICATE_FILE"),
        device_allowlist_file=pki.resolve_path(deploy_dir, env["OPENIT_DEVICE_ALLOWLIST_FILE"]),
        exposures_dir=pki.resolve_path(deploy_dir, env["OPENIT_EXPOSURES_DIR"]),
        machine_tokens_file=pki.resolve_path(deploy_dir, env["OPENIT_MACHINE_TOKENS_FILE"]),
        ingress_certificate_file=cert,
        ingress_private_key_file=key,
        alert_receiver_url=receiver,
        alert_smtp_smarthost=env["OPENIT_ALERT_SMTP_SMARTHOST"].strip(),
        alert_heartbeat_minutes=pki._minutes(env, "OPENIT_ALERT_HEARTBEAT_INTERVAL"),
    )
