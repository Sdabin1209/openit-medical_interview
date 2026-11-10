"""platform 설정 해석(설치 설정 -> 생성기 입력). docker 를 부르지 않는 순수 함수만 둔다.

입력의 이름과 모양은 계약 PlatformEnv 가 정한다(platform ADR 0001, 계약 9.0.0 의 platform-001). 값마다 계약 스키마의 칸 타입으로 검증하고
계약에 적힌 선택 입력(OPENIT_PUBLIC_NAMES 등)이 없을 때의 기본값만 이 파일이 정한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import TypeAdapter, ValidationError

from . import pki
from .contract.models import PlatformEnv
from .pki import ConfigError

REALM = "openit"  # 왜 고정: 계약 OidcIssuerUrl 의 예시가 /realms/openit 이고 realm 은 platform 이 만든다(realm 파일 하나, platform ADR 0003)
GATEWAY_NAME = "gateway"  # 영역들이 입구(게이트웨이)를 부르는 이름이다. 나가는 터널 주소와 영역 사이 mTLS 의 클라이언트 인증서 이름이 된다
# 왜 8443: 계약 OPENIT_SERVICE_PORT 는 선택 입력이다. 없으면 HTTPS 의 대체 포트로 널리 쓰는 8443(IANA 에 pcsync-https 로 등록)을 쓴다.
# 1024 이상이라 비 root 가 연다. 측정한 값이 아니다(platform ADR 0007)
DEFAULT_SERVICE_PORT = 8443
# 왜 1m: 계약 OPENIT_ALERT_HEARTBEAT_INTERVAL 은 선택 입력이고 값은 설치처가 정한다. 없을 때는 Prometheus 평가 주기(1m, monitoring/prometheus.yml)와 같게 둔다.
# 측정하지 않았다(platform ADR 0005)
DEFAULT_HEARTBEAT_INTERVAL = "1m"


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
    alert_heartbeat_interval: str  # Prometheus 기간 표기 그대로(계약 AlertHeartbeatInterval)

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


def _contract(key: str, value: Any) -> Any:
    """입력 하나를 계약 PlatformEnv 의 그 칸 타입으로 검증한다(칸 이름과 모양의 정본은 계약이다)."""
    annotation: Any = PlatformEnv.model_fields[key].annotation
    try:
        return TypeAdapter(annotation).validate_python(value)
    except ValidationError as error:
        raise ConfigError(f"{key} 가 계약 PlatformEnv 를 어겼다: {error.errors()[0]['msg']}") from error


def _given(env: dict[str, str], key: str) -> str | None:
    """선택 입력. 없거나 빈 값이면 없는 것이다."""
    value = env.get(key, "").strip()
    return value or None


def _port(env: dict[str, str], key: str, default: int | None) -> int:
    raw = _given(env, key)
    if raw is None:
        if default is None:
            raise ConfigError(f"{key} 가 없다(계약 PlatformEnv 의 필수 입력)")
        return default
    try:
        number = int(raw)
    except ValueError as error:
        raise ConfigError(f"{key} 는 정수여야 한다") from error
    return int(_contract(key, number).root)


def platform_settings(env: dict[str, str], deploy_dir: Path) -> PlatformSettings:
    mode = _contract("OPENIT_INGRESS_CERTIFICATE_MODE", env["OPENIT_INGRESS_CERTIFICATE_MODE"]).value
    issuer = env["OPENIT_OIDC_ISSUER_URL"].strip()
    _contract("OPENIT_OIDC_ISSUER_URL", issuer)
    parsed = urlsplit(issuer)
    if parsed.path != f"/realms/{REALM}":
        raise ConfigError(f"OPENIT_OIDC_ISSUER_URL 은 /realms/{REALM} 으로 끝나야 한다(현재 경로 '{parsed.path}')")
    if not parsed.hostname:
        raise ConfigError("OPENIT_OIDC_ISSUER_URL 에 호스트가 없다")
    raw_names = _given(env, "OPENIT_PUBLIC_NAMES")
    # 왜 발급자 호스트가 기본: 계약이 발급자의 호스트가 입구 이름 안에 있어야 한다고 정하므로, 이름을 주지 않으면 그 하나가 입구가 서비스하는 이름이다
    listed = [part.strip() for part in raw_names.split(",") if part.strip()] if raw_names else [parsed.hostname]
    names = tuple(item.root for item in _contract("OPENIT_PUBLIC_NAMES", listed))
    if len(set(names)) != len(names):
        raise ConfigError("OPENIT_PUBLIC_NAMES 에 같은 이름이 둘 이상 있다")
    if parsed.hostname not in names:
        raise ConfigError("OPENIT_OIDC_ISSUER_URL 의 호스트는 OPENIT_PUBLIC_NAMES 안에 있어야 한다(입구가 그 이름의 인증서를 낸다)")
    service_port = _port(env, "OPENIT_SERVICE_PORT", DEFAULT_SERVICE_PORT)
    listen_port = _port(env, "OPENIT_LISTEN_PORT", None)
    acme = env.get("OPENIT_ACME_DIRECTORY_URL", "").strip()
    if mode == "acme-public":
        if not acme.startswith("https://"):
            raise ConfigError("acme-public 은 OPENIT_ACME_DIRECTORY_URL(https)이 있어야 한다(계약 AcmeDirectoryUrl)")
        _contract("OPENIT_ACME_DIRECTORY_URL", acme)
    ca = pki.ca_settings(env)
    if mode == "private":
        outside = _names_allowed(names, ca.allowed_dns)
        if outside:
            raise ConfigError(f"OPENIT_PUBLIC_NAMES 가 OPENIT_CA_ALLOWED_DNS 밖이다(사설 CA 가 발급하지 않는다): {', '.join(outside)}")
    if _names_allowed((GATEWAY_NAME,), ca.allowed_dns):
        raise ConfigError(f"OPENIT_CA_ALLOWED_DNS 에 '{GATEWAY_NAME}' 가 있어야 한다(입구가 영역 서비스에 보일 클라이언트 인증서의 이름)")

    def optional_path(key: str) -> Path | None:
        value = _given(env, key)
        if value is None:
            return None
        # 왜 풀어서 검증: 설치 설정은 deploy/ 기준 상대 경로도 허용한다. 계약의 칸(절대 경로)은 풀린 값으로 확인한다
        path = pki.resolve_path(deploy_dir, value)
        _contract(key, str(path))
        return path

    cert, key = optional_path("OPENIT_INGRESS_CERTIFICATE_FILE"), optional_path("OPENIT_INGRESS_PRIVATE_KEY_FILE")
    if mode == "organization" and (cert is None or key is None):
        raise ConfigError("organization 은 OPENIT_INGRESS_CERTIFICATE_FILE 과 OPENIT_INGRESS_PRIVATE_KEY_FILE 이 있어야 한다")
    receiver = env["OPENIT_ALERT_RECEIVER_URL"].strip()
    if receiver:
        _contract("OPENIT_ALERT_RECEIVER_URL", receiver)
    smarthost = _given(env, "OPENIT_ALERT_SMTP_SMARTHOST")
    if smarthost:
        _contract("OPENIT_ALERT_SMTP_SMARTHOST", smarthost)
    # 왜 이 조건은 코드에 남나: 계약 설명(OPENIT_ALERT_SMTP_SMARTHOST 는 mailto 일 때 필수)에 있고 스키마의 조건부 필수로는 적히지 않았다
    if receiver and urlsplit(receiver).scheme == "mailto" and not smarthost:
        raise ConfigError("mailto 수신처는 OPENIT_ALERT_SMTP_SMARTHOST(<호스트>:<포트>)가 있어야 한다")
    heartbeat = _given(env, "OPENIT_ALERT_HEARTBEAT_INTERVAL")
    if heartbeat:
        _contract("OPENIT_ALERT_HEARTBEAT_INTERVAL", heartbeat)
    return PlatformSettings(
        ingress_mode=mode,
        public_names=names,
        issuer=issuer,
        public_host=parsed.hostname,
        public_port=parsed.port or 443,
        listen_port=listen_port,
        service_port=service_port,
        acme_directory_url=acme,
        internal_acme_directory_url=env["OPENIT_INTERNAL_ACME_DIRECTORY_URL"],
        device_ca_file=optional_path("OPENIT_DEVICE_CA_CERTIFICATE_FILE"),
        device_allowlist_file=pki.resolve_path(deploy_dir, env["OPENIT_DEVICE_ALLOWLIST_FILE"]),
        exposures_dir=pki.resolve_path(deploy_dir, env["OPENIT_EXPOSURES_DIR"]),
        machine_tokens_file=pki.resolve_path(deploy_dir, env["OPENIT_MACHINE_TOKENS_FILE"]),
        ingress_certificate_file=cert,
        ingress_private_key_file=key,
        alert_receiver_url=receiver,
        alert_smtp_smarthost=smarthost or "",
        alert_heartbeat_interval=heartbeat or DEFAULT_HEARTBEAT_INTERVAL,
    )
