"""신뢰의 뿌리와 인증서 수명 계산(ADR 0013, 0014, 0015). docker 를 부르지 않는 순수 함수만 둔다(시험이 쉽다).

- 설정: deploy/env.example(기본값)을 읽고 deploy/.env 가 덮어쓴다. compose 도 같은 두 파일을 읽는다.
- 인증서 읽기·검증은 cryptography(Apache-2.0 OR BSD-3-Clause)로 한다.
- step-ca 의 ca.json 을 설정 값에서 만든다(손으로 고치지 않는다).
"""

from __future__ import annotations

import json
import re
import socket
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

CA_MODES = ("self", "institution")
PUBLIC_MODES = ("private", "institution", "public-acme")
REGISTRY_MODES = ("local", "external")
KEY_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


class ConfigError(ValueError):
    """설정이 틀렸다. 호출자는 멈춰야 한다."""


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = KEY_RE.match(line)
        if not match:
            raise ConfigError(f"{path.name}:{number}: KEY=값 형식이 아니다")
        values[match.group(1)] = match.group(2).strip()
    return values


def load_env(deploy_dir: Path) -> dict[str, str]:
    """env.example 을 바탕으로 .env 가 덮어쓴 값. 상속받은 환경 변수는 읽지 않는다(RUNTIME R9.1)."""
    values = parse_env_file(deploy_dir / "env.example")
    local = deploy_dir / ".env"
    if local.is_file():
        override = parse_env_file(local)
        unknown = sorted(set(override) - set(values))
        if unknown:
            raise ConfigError(f".env 에 env.example 에 없는 키가 있다: {', '.join(unknown)}")
        values.update(override)
    return values


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _hours(env: dict[str, str], key: str) -> int:
    try:
        number = int(env[key])
    except (KeyError, ValueError) as error:
        raise ConfigError(f"{key} 는 시간 단위 정수여야 한다") from error
    if number <= 0:
        raise ConfigError(f"{key} 는 0 보다 커야 한다")
    return number


@dataclass(frozen=True)
class CaSettings:
    mode: str
    name: str
    dns_names: list[str]
    allowed_dns: list[str]
    allowed_ips: list[str]
    root_hours: int
    intermediate_hours: int
    leaf_hours: int
    warn_root_hours: int
    warn_intermediate_hours: int
    warn_leaf_hours: int
    acme_directory_url: str


@dataclass(frozen=True)
class RegistrySettings:
    mode: str
    address: str
    names: list[str]


def ca_settings(env: dict[str, str]) -> CaSettings:
    mode = env["OPENIT_CA_MODE"]
    if mode not in CA_MODES:
        raise ConfigError(f"OPENIT_CA_MODE 는 {', '.join(CA_MODES)} 중 하나여야 한다(현재 '{mode}')")
    settings = CaSettings(
        mode=mode,
        name=env["OPENIT_CA_NAME"],
        dns_names=_split(env["OPENIT_CA_DNS_NAMES"]),
        allowed_dns=_split(env["OPENIT_CA_ALLOWED_DNS"]),
        allowed_ips=_split(env["OPENIT_CA_ALLOWED_IPS"]),
        root_hours=_hours(env, "OPENIT_CA_ROOT_LIFETIME_HOURS"),
        intermediate_hours=_hours(env, "OPENIT_CA_INTERMEDIATE_LIFETIME_HOURS"),
        leaf_hours=_hours(env, "OPENIT_LEAF_LIFETIME_HOURS"),
        warn_root_hours=_hours(env, "OPENIT_CA_WARN_ROOT_HOURS"),
        warn_intermediate_hours=_hours(env, "OPENIT_CA_WARN_INTERMEDIATE_HOURS"),
        warn_leaf_hours=_hours(env, "OPENIT_CA_WARN_LEAF_HOURS"),
        acme_directory_url=env["OPENIT_INTERNAL_ACME_DIRECTORY_URL"],
    )
    if not settings.name or not settings.dns_names:
        raise ConfigError("OPENIT_CA_NAME 과 OPENIT_CA_DNS_NAMES 는 비울 수 없다")
    if not settings.allowed_dns and not settings.allowed_ips:
        raise ConfigError("OPENIT_CA_ALLOWED_DNS 와 OPENIT_CA_ALLOWED_IPS 가 모두 비면 CA 가 아무것도 발급하지 못한다")
    # 왜: 하위 인증서는 상위보다 오래 살 수 없다(RFC 5280 6.1.3 경로 검증). 어기면 중간 CA 가 만료되는 날 리프도 함께 죽는다
    if not settings.leaf_hours < settings.intermediate_hours < settings.root_hours:
        raise ConfigError("수명은 리프 < 중간 CA < 루트 여야 한다")
    public = env["OPENIT_PUBLIC_CERT_MODE"]
    if public not in PUBLIC_MODES:
        raise ConfigError(f"OPENIT_PUBLIC_CERT_MODE 는 {', '.join(PUBLIC_MODES)} 중 하나여야 한다(현재 '{public}')")
    if public == "public-acme" and not _split(env["OPENIT_PUBLIC_NAMES"]):
        raise ConfigError("public-acme 는 OPENIT_PUBLIC_NAMES(공개 도메인)가 있어야 한다")
    return settings


def registry_settings(env: dict[str, str]) -> RegistrySettings:
    mode = env["OPENIT_REGISTRY_MODE"]
    if mode not in REGISTRY_MODES:
        raise ConfigError(f"OPENIT_REGISTRY_MODE 는 {', '.join(REGISTRY_MODES)} 중 하나여야 한다(현재 '{mode}')")
    address = env["OPENIT_REGISTRY_ADDRESS"].strip().rstrip("/")
    if mode == "external" and not address:
        raise ConfigError("external 레지스트리는 OPENIT_REGISTRY_ADDRESS 가 있어야 한다")
    if mode == "local" and address:
        raise ConfigError("local 레지스트리는 OPENIT_REGISTRY_ADDRESS 를 비워 둔다(주소는 배정된 포트로 정해진다)")
    names = _split(env["OPENIT_REGISTRY_NAMES"])
    if mode == "local" and not names:
        raise ConfigError("local 레지스트리는 OPENIT_REGISTRY_NAMES 가 있어야 한다")
    return RegistrySettings(mode=mode, address=address, names=names)


def resolve_path(deploy_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (deploy_dir / path).resolve()


# ---------------------------------------------------------------- step-ca 설정


def render_ca_json(settings: CaSettings) -> dict[str, Any]:
    """step-ca 의 ca.json. 경로는 컨테이너 안 경로다(compose.yaml 의 마운트와 같다)."""
    policy: dict[str, list[str]] = {}
    if settings.allowed_dns:
        policy["dns"] = settings.allowed_dns
    if settings.allowed_ips:
        policy["ip"] = settings.allowed_ips
    leaf = f"{settings.leaf_hours}h"
    return {
        "root": "/home/step/certs/root_ca.crt",
        "crt": "/home/step/certs/intermediate_ca.crt",
        "key": "/run/secrets/step_ca_intermediate_key",
        "address": ":9000",
        "dnsNames": settings.dns_names,
        "logger": {"format": "json"},
        "db": {"type": "badgerv2", "dataSource": "/home/step/db"},
        "authority": {
            "provisioners": [
                {
                    "type": "ACME",
                    "name": "acme",
                    "claims": {
                        # 왜 min 5m: step-ca 의 기본 하한이다. 이보다 짧은 수명은 step-ca 가 거부한다
                        "minTLSCertDuration": "5m",
                        # 왜 max = default: 리프 수명의 상한을 설정 값 하나로 둔다. ACME 요청에는 수명 칸이 없어 기본값이 곧 발급 수명이다
                        "maxTLSCertDuration": leaf,
                        "defaultTLSCertDuration": leaf,
                    },
                }
            ],
            "policy": {"x509": {"allow": policy}},
        },
        # 왜 1.2 이상: TLS 1.0/1.1 은 RFC 8996 이 폐기했다. 암호 목록은 step-ca 기본값(Go 표준 라이브러리의 안전한 목록)을 쓴다
        "tls": {"minVersion": 1.2, "maxVersion": 1.3, "renegotiation": False},
    }


def render_ca_json_text(settings: CaSettings) -> str:
    return json.dumps(render_ca_json(settings), indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- 인증서 읽기


def load_certs(path: Path) -> list[x509.Certificate]:
    return x509.load_pem_x509_certificates(path.read_bytes())


def load_cert(path: Path) -> x509.Certificate:
    return load_certs(path)[0]


def subject_text(cert: x509.Certificate) -> str:
    return cert.subject.rfc4514_string()


def remaining(cert: x509.Certificate, now: datetime | None = None) -> timedelta:
    return cert.not_valid_after_utc - (now or datetime.now(UTC))


def key_matches_cert(key_path: Path, password: bytes | None, cert: x509.Certificate) -> bool:
    key = serialization.load_pem_private_key(key_path.read_bytes(), password)
    fmt = serialization.PublicFormat.SubjectPublicKeyInfo
    enc = serialization.Encoding.DER
    return key.public_key().public_bytes(enc, fmt) == cert.public_key().public_bytes(enc, fmt)


def check_intermediate(cert: x509.Certificate, root: x509.Certificate, now: datetime | None = None) -> list[str]:
    """중간 CA 인증서가 루트 아래의 CA 로 쓸 수 있는지(RFC 5280 4.2.1.9 basicConstraints, 4.2.1.3 keyUsage). 문제 목록, 비면 통과."""
    problems: list[str] = []
    try:
        cert.verify_directly_issued_by(root)
    except Exception as error:  # noqa: BLE001  왜: cryptography 가 서명·이름·확장 불일치를 여러 예외로 낸다. 모두 같은 뜻의 실패다
        problems.append(f"루트가 서명한 인증서가 아니다: {error}")
    try:
        constraints = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        if not constraints.ca:
            problems.append("basicConstraints 의 CA 가 참이 아니다")
    except x509.ExtensionNotFound:
        problems.append("basicConstraints 가 없다")
    try:
        usage = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not usage.key_cert_sign:
            problems.append("keyUsage 에 keyCertSign 이 없다")
    except x509.ExtensionNotFound:
        problems.append("keyUsage 가 없다")
    moment = now or datetime.now(UTC)
    if not cert.not_valid_before_utc <= moment <= cert.not_valid_after_utc:
        problems.append("지금은 유효 기간 밖이다")
    if cert.not_valid_after_utc > root.not_valid_after_utc:
        problems.append("중간 CA 가 루트보다 오래 산다")
    return problems


def pem_text(certs: list[x509.Certificate]) -> str:
    return "".join(c.public_bytes(serialization.Encoding.PEM).decode("ascii") for c in certs)


def build_bundle(roots: list[Path], extra_dir: Path) -> str:
    """신뢰 목록 PEM. 이 설치의 루트들 + 추가 폴더의 *.crt·*.pem. 같은 인증서는 한 번만(지문으로)."""
    sources = [*roots]
    if extra_dir.is_dir():
        sources += sorted(p for p in extra_dir.iterdir() if p.is_file() and p.suffix in {".crt", ".pem"})
    seen: set[bytes] = set()
    unique: list[x509.Certificate] = []
    for path in sources:
        for cert in load_certs(path):
            fingerprint = cert.fingerprint(hashes.SHA256())
            if fingerprint not in seen:
                seen.add(fingerprint)
                unique.append(cert)
    if not unique:
        raise ConfigError("신뢰 목록에 넣을 루트가 하나도 없다")
    return pem_text(unique)


# ---------------------------------------------------------------- 서버 인증서 읽기(검증하면서)


def fetch_leaf(host: str, port: int, server_name: str, bundle: Path, timeout: float = 5.0) -> x509.Certificate:
    """TLS 로 접속해 서버의 리프 인증서를 읽는다. 신뢰 목록(과 시스템 신뢰 저장소)으로 검증하고, 실패하면 예외다(검증을 끄지 않는다)."""
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=str(bundle))
    with socket.create_connection((host, port), timeout=timeout) as raw, context.wrap_socket(raw, server_hostname=server_name) as tls:
        # 왜 binary_form: 검증된 핸드셰이크의 상대 인증서를 DER 로 받는다(getpeercert() 는 검증 뒤 사전 형태라 serial 등이 문자열이다)
        der = tls.getpeercert(binary_form=True)
    if not der:
        raise ssl.SSLError("서버가 인증서를 내놓지 않았다")
    return x509.load_der_x509_certificate(der)
