"""입구(Envoy) 설정 생성(design.md 2절 gateway, ADR 0008, platform ADR 0002·0003).

입력: 영역들의 노출 선언(Exposure), 기기 허용 목록(DeviceAllowlist), 계약의 OpenAPI(작업별 인증 요구), 설치 설정.
출력: Envoy 부트스트랩 설정 하나(설정 파일에 비밀은 없다). 같은 입력은 같은 출력이다.

규칙(계약 README '인증', securitySchemes):
- 공개 입구는 ExposureAudience 가 HUMAN_OIDC·DEVICE_MTLS·EXTERNAL_MACHINE_TOKEN 인 경로만 낸다. MACHINE_TOKEN·DENIED 와 /healthz·/readyz·/metrics 는 내보내지 않는다(D129).
- 노출 선언이 가리키는 작업의 인증 요구(OpenAPI security)에 그 대상이 없으면 시작하지 않는다.
- 같은 (경로, 메서드)를 두 영역이 열면 시작하지 않는다.
- XFCC: 입구는 클라이언트가 보낸 X-Forwarded-Client-Cert 를 지우고 검증한 인증서로 다시 쓴다(forward_client_cert_details SANITIZE_SET).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_args

import yaml

from .contract.models import (
    DeviceAllowlist,
    Exposure,
    ExposureAudience,
    GatewayConnectLimitSeconds,
    GatewayPatientRouteLimitSeconds,
    MachineRole,
    ServiceName,
    UserRole,
)
from .pki import ConfigError
from .settings import GATEWAY_NAME, REALM, PlatformSettings

HEALTH_PATHS = ("/healthz", "/readyz", "/metrics")  # 입구로 내보내지 않는다(계약 platform.yaml 의 설명, D129)
PUBLIC_AUDIENCES = (ExposureAudience.HUMAN_OIDC, ExposureAudience.DEVICE_MTLS, ExposureAudience.EXTERNAL_MACHINE_TOKEN)
# 계약 securitySchemes 이름. 대상별로 작업의 어떤 요구가 그 대상을 허용하는지 정한다
SCHEME_OF = {
    ExposureAudience.HUMAN_OIDC: "oidc",
    ExposureAudience.DEVICE_MTLS: "device_mtls",
    ExposureAudience.EXTERNAL_MACHINE_TOKEN: "machine_token",
}
HTTP_METHODS = ("get", "post", "put", "delete")
CONNECT_SECONDS = int(get_args(GatewayConnectLimitSeconds.model_fields["root"].annotation)[0])  # 계약 상수(D125: gateway 1초)
ROUTE_SECONDS = int(get_args(GatewayPatientRouteLimitSeconds.model_fields["root"].annotation)[0])  # 계약 상수(D125: gateway 55초)
# 왜 3배: 알림 스트림은 heartbeat 를 AlertStreamHeartbeatSeconds(계약, 15초)마다 보낸다. 두 번 거르고도 연결을 유지하려는 이 구현의 선택값이며 측정하지 않았다(platform ADR 0003)
STREAM_IDLE_SECONDS = 3 * 15
EGRESS_FIRST_PORT = 3128  # 왜: HTTP CONNECT 프록시의 관례 포트(Squid 기본값)다. 영역마다 하나씩 이어서 쓴다
ANY_ADDRESS = "0.0.0.0"  # noqa: S104  왜: 컨테이너 안에서 모든 인터페이스로 받는다. 어디서 닿는지는 compose 네트워크가 정한다
ADMIN_PORT = 9901  # 컨테이너 안 루프백에만 연다(건강 확인용)
ACME_STORE = "/ingress-certs"  # ingress-acme(Caddy)가 인증서를 두는 공유 볼륨
ORG_DIR = "/etc/openit/ingress"  # organization 방식의 입구 인증서(deploy/pki/ingress/)
TRUST_LIST = "/etc/openit/trust-list.pem"
DEVICE_CA = "/etc/openit/device-ca.pem"
OAUTH2_PROXY = "oauth2-proxy"
OAUTH2_PROXY_PORT = 4180
KEYCLOAK = "keycloak"
KEYCLOAK_PORT = 8080
NS = "type.googleapis.com/envoy.extensions."


@dataclass(frozen=True)
class Operation:
    service: str
    path: str  # OpenAPI 경로(템플릿 포함)
    method: str  # 대문자
    security: tuple[dict[str, tuple[str, ...]], ...]
    streaming: bool


@dataclass
class Gateway:
    """입구가 정하는 것 전부(라우트, 허용 역할, 나가는 터널). 시험이 이 구조를 본다."""

    exposures: dict[str, Exposure]
    routes: list[RouteSpec] = field(default_factory=list)
    egress: list[EgressSpec] = field(default_factory=list)


@dataclass
class RouteSpec:
    service: str
    audiences: set[ExposureAudience]
    method: str | None  # None 이면 methods 로 가른다(접두어 경로)
    methods: tuple[str, ...]
    regex: str | None  # 작업 경로(템플릿을 정규식으로)
    prefix: str | None  # 작업이 없는 접두어 경로(정적 화면)
    roles: dict[ExposureAudience, tuple[str, ...]]
    streaming: bool = False


@dataclass(frozen=True)
class EgressSpec:
    service: str
    port: int
    targets: tuple[tuple[str, int], ...]


# ---------------------------------------------------------------- 입력 읽기


def load_exposures(folder: Path) -> dict[str, Exposure]:
    """<서비스 이름>.json 마다 Exposure 로 검증한다. 파일 이름이 ServiceName 이 아니면 거절한다."""
    found: dict[str, Exposure] = {}
    if not folder.is_dir():
        return found
    allowed = {item.value for item in ServiceName}
    for path in sorted(folder.glob("*.json")):
        if path.stem not in allowed:
            raise ConfigError(f"{path.name}: 파일 이름이 계약 ServiceName 이 아니다({', '.join(sorted(allowed))})")
        try:
            found[path.stem] = Exposure.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ConfigError(f"{path.name}: 노출 선언(Exposure)이 계약을 어겼다: {error}") from error
    return found


def load_allowlist(path: Path) -> DeviceAllowlist:
    """파일이 없으면 빈 목록이다(어떤 기기도 허용하지 않는다. 막는 쪽으로 닫힌다)."""
    if not path.is_file():
        return DeviceAllowlist(devices=[])
    try:
        return DeviceAllowlist.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ConfigError(f"{path.name}: 기기 허용 목록(DeviceAllowlist)이 계약을 어겼다: {error}") from error


def load_operations(contracts: Path, service: str) -> list[Operation]:
    """계약 OpenAPI(contracts/openapi/<서비스>.yaml)의 작업과 인증 요구. 계약은 읽기만 한다."""
    path = contracts / "openapi" / f"{service}.yaml"
    if not path.is_file():
        return []
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    operations: list[Operation] = []
    for route, item in document.get("paths", {}).items():
        for method in HTTP_METHODS:
            spec = item.get(method)
            if spec is None:
                continue
            security = tuple({name: tuple(roles) for name, roles in alternative.items()} for alternative in spec.get("security", []))
            streaming = any("text/event-stream" in (response.get("content") or {}) for response in (spec.get("responses") or {}).values())
            operations.append(Operation(service, route, method.upper(), security, streaming))
    return operations


# ---------------------------------------------------------------- 노출 선언 -> 라우트


def _under(prefix: str, path: str) -> bool:
    """경로 접두어(RFC 3986 의 경로 구간 단위)에 든다. '/v1/res' 는 '/v1/results' 를 가리키지 않는다."""
    base = prefix.rstrip("/")
    return path == base or path.startswith(base + "/") or prefix == "/"


def _roles(operation: Operation, audience: ExposureAudience) -> tuple[str, ...] | None:
    """작업의 인증 요구 중 이 대상을 허용하는 것들의 역할 합집합. 허용하는 요구가 없으면 None."""
    scheme = SCHEME_OF[audience]
    found = False
    roles: list[str] = []
    for alternative in operation.security:
        if scheme not in alternative:
            continue
        if audience is ExposureAudience.EXTERNAL_MACHINE_TOKEN and "area_mtls" in alternative:
            continue  # 왜: area_mtls 가 함께 있는 요구는 같은 서버 안의 영역 호출이다. 외부 호출자는 TLS 와 기계 토큰만으로 온다(계약 securitySchemes)
        found = True
        known = {item.value for item in (UserRole if audience is ExposureAudience.HUMAN_OIDC else MachineRole)}
        unknown = [role for role in alternative[scheme] if role not in known]
        if unknown:
            raise ConfigError(f"{operation.service}: {operation.method} {operation.path} 의 역할이 계약 열거에 없다: {', '.join(unknown)}")
        roles += [role for role in alternative[scheme] if role not in roles]
    if not found:
        return None
    return tuple(roles)


def _template_regex(path: str) -> str:
    """OpenAPI 경로 템플릿 /a/{id}/b 를 Envoy safe_regex(전체 일치)로. 템플릿 칸은 한 구간이다."""
    return "".join("[^/]+" if part.startswith("{") else re.escape(part) for part in re.split(r"(\{[^}]+\})", path) if part)


def plan(settings: PlatformSettings, exposures: dict[str, Exposure], contracts: Path, device_ca_present: bool) -> Gateway:
    gateway = Gateway(exposures=exposures)
    owners: dict[tuple[str, str], str] = {}
    by_operation: dict[tuple[str, str, str], RouteSpec] = {}
    for service, exposure in sorted(exposures.items()):
        operations = [op for op in load_operations(contracts, service) if op.path not in HEALTH_PATHS]
        for route in exposure.routes:
            audience = route.audience
            if audience not in PUBLIC_AUDIENCES:
                continue
            methods = tuple(sorted(method.value for method in route.methods))
            prefix = route.path_prefix.root
            if audience is ExposureAudience.DEVICE_MTLS and not device_ca_present:
                raise ConfigError(f"{service} 가 기기 경로({prefix})를 열었는데 OPENIT_DEVICE_CA_CERTIFICATE_FILE 이 없다")
            for method in methods:
                other = owners.setdefault((prefix, method), service)
                if other != service:
                    raise ConfigError(f"같은 공개 경로를 두 영역이 연다: {method} {prefix} ({other}, {service})")
            matched = [op for op in operations if _under(prefix, op.path) and op.method in methods]
            if not matched:
                gateway.routes.append(RouteSpec(service, {audience}, None, methods, None, prefix, {audience: ()}))
                continue
            opened = 0
            for op in matched:
                roles = _roles(op, audience)
                if roles is None:
                    # 왜 건너뜀: 접두어는 편의다. 그 작업이 이 대상을 허용하지 않으면 이 대상에게는 열지 않는다(최소 권한).
                    # 허용하는 작업이 하나도 없으면 아래에서 시작하지 않는다
                    continue
                if audience is not ExposureAudience.DEVICE_MTLS and not roles:
                    raise ConfigError(f"{service}: {op.method} {op.path} 의 {SCHEME_OF[audience]} 요구에 역할이 없다(역할을 알 수 없어 열지 않는다)")
                opened += 1
                key = (service, op.method, op.path)
                spec = by_operation.get(key)
                if spec is None:
                    spec = RouteSpec(service, set(), op.method, (op.method,), _template_regex(op.path), None, {}, op.streaming)
                    by_operation[key] = spec
                    gateway.routes.append(spec)
                spec.audiences.add(audience)
                spec.roles[audience] = roles
            if not opened:
                raise ConfigError(
                    f"{service}: 노출 선언({prefix}, {audience.value})이 계약의 인증 요구와 맞지 않는다: 이 경로의 작업 중 {SCHEME_OF[audience]} 를 허용하는 것이 없다"
                )
    for index, (service, exposure) in enumerate(sorted((s, e) for s, e in exposures.items() if e.egress)):
        targets: list[tuple[str, int]] = []
        for target in exposure.egress:
            inner = target.root
            if isinstance(inner, ServiceName):
                targets.append((inner.value, settings.service_port))
            else:
                targets.append((str(inner.host.root.root if hasattr(inner.host.root, "root") else inner.host.root), int(inner.port.root)))
        gateway.egress.append(EgressSpec(service, EGRESS_FIRST_PORT + index, tuple(dict.fromkeys(targets))))
    return gateway


def egress_manifest(settings: PlatformSettings, gateway: Gateway) -> dict[str, str]:
    """서비스 이름 -> 그 서비스의 OPENIT_EGRESS_PROXY 값(계약 EgressProxyUrl). deploy 가 서비스 환경 입력에 넣는다."""
    return {spec.service: f"http://{GATEWAY_NAME}:{spec.port}" for spec in gateway.egress}


# ---------------------------------------------------------------- Envoy 설정


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def ingress_certificate_paths(settings: PlatformSettings, issuer_key: str) -> tuple[str, str]:
    """입구 서버 인증서와 키의 컨테이너 안 경로."""
    if settings.ingress_mode == "organization":
        return f"{ORG_DIR}/tls.crt", f"{ORG_DIR}/tls.key"
    name = settings.public_names[0]
    base = f"{ACME_STORE}/certificates/{issuer_key}/{name}/{name}"
    return f"{base}.crt", f"{base}.key"


def gateway_client_paths(issuer_key: str) -> tuple[str, str]:
    base = f"{ACME_STORE}/certificates/{issuer_key}/{GATEWAY_NAME}/{GATEWAY_NAME}"
    return f"{base}.crt", f"{base}.key"


def _lua_device_check(allowlist: DeviceAllowlist, device_ca_present: bool) -> str:
    entries = "".join(f'  ["{item.device_id.root}/{item.serial_number.root.lstrip("0") or "0"}"] = true,\n' for item in allowlist.devices)
    return f"""local allowed = {{
{entries}}}

local function normalize_serial(serial)
  local stripped = string.lower(serial):gsub("^0+", "")
  if stripped == "" then return "0" end
  return stripped
end

local function common_name(subject)
  for part in string.gmatch(subject, "[^,]+") do
    local value = string.match(part, "^%s*CN=(.+)$")
    if value ~= nil then return value end
  end
  return nil
end

-- 왜 요청 첫머리: 위조된 신원 머리글을 지우고, 기기 인증서가 허용 목록(기기 ID 와 일련번호)에 있는지 본다.
-- 세션 확인(oauth2-proxy)을 건너뛸 요청(기기 또는 기계 토큰)을 표시한다.
function envoy_on_request(handle)
  handle:headers():remove("x-auth-request-access-token")
  handle:headers():remove("x-auth-request-user")
  handle:headers():remove("x-auth-request-email")
  local skip = "no"
  local authorization = handle:headers():get("authorization")
  if authorization ~= nil and string.lower(string.sub(authorization, 1, 7)) == "bearer " then
    skip = "yes"
  end
  local ssl = handle:streamInfo():downstreamSslConnection()
  if ssl ~= nil and ssl:peerCertificatePresented() then
    local cn = common_name(ssl:subjectPeerCertificate())
    local serial = ssl:serialNumberPeerCertificate()
    if {"false" if device_ca_present else "true"} or cn == nil or serial == nil or not allowed[cn .. "/" .. normalize_serial(serial)] then
      handle:respond({{[":status"] = "403", ["content-type"] = "text/plain"}}, "device certificate is not allowed\\n")
      return
    end
    skip = "yes"
  end
  handle:streamInfo():dynamicMetadata():set("openit", "skip_session", skip)
end
"""


LUA_TOKEN = """-- 왜: oauth2-proxy 는 세션 쿠키가 맞으면 접근 토큰을 X-Auth-Request-Access-Token 으로 준다.
-- 영역 서비스는 Authorization: Bearer 만 읽는다(계약 securitySchemes oidc).
function envoy_on_request(handle)
  local token = handle:headers():get("x-auth-request-access-token")
  if token ~= nil then
    handle:headers():replace("authorization", "Bearer " .. token)
    handle:headers():remove("x-auth-request-access-token")
  end
end
"""  # noqa: S105  왜: 토큰 값이 아니라 토큰을 옮기는 Lua 코드다


def _typed(type_url: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"@type": NS + type_url.replace("/", "."), **body}


def _access_log() -> list[dict[str, Any]]:
    # 왜 쿼리를 뺀 경로: OIDC 콜백의 쿼리에 인가 코드가 있다. 토큰·쿠키·XFCC 도 남기지 않는다(비밀은 로그에 넣지 않는다)
    fmt = {
        "time": "%START_TIME%",
        "method": "%REQ(:METHOD)%",
        "path": "%REQ_WITHOUT_QUERY(:PATH)%",
        "status": "%RESPONSE_CODE%",
        "flags": "%RESPONSE_FLAGS%",
        "upstream": "%UPSTREAM_CLUSTER%",
        "duration_ms": "%DURATION%",
        "tls": "%DOWNSTREAM_TLS_VERSION%",
    }
    return [
        {
            "name": "envoy.access_loggers.stdout",
            "typed_config": {
                "@type": "type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog",
                "log_format": {
                    "json_format": fmt,
                    "formatters": [
                        {
                            "name": "envoy.formatter.req_without_query",
                            "typed_config": {"@type": "type.googleapis.com/envoy.extensions.formatter.req_without_query.v3.ReqWithoutQuery"},
                        }
                    ],
                },
            },
        }
    ]


SDS_DIR = "/etc/envoy/sds"  # 인증서 비밀(Secret)을 담은 파일 폴더. 입구 설정은 이 파일을 SDS 로 가리킨다
SECRET_INGRESS = "ingress_cert"  # noqa: S105  Envoy Secret 의 이름이다(값이 아니다)
SECRET_CLIENT = "gateway_client"  # noqa: S105
SECRET_TYPE = "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.Secret"  # noqa: S105


def _sds_ref(name: str) -> dict[str, Any]:
    return {"name": name, "sds_config": {"resource_api_version": "V3", "path_config_source": {"path": f"{SDS_DIR}/{name}.yaml"}}}


def _sds_file(name: str, cert: tuple[str, str]) -> dict[str, Any]:
    """파일 기반 SDS 의 Secret. 인증서 폴더(watched_directory)에 파일이 옮겨 들어오면(Caddy 의 갱신) 인증서와 키를 한 쌍으로 다시 읽는다."""
    certificate = {"certificate_chain": {"filename": cert[0]}, "private_key": {"filename": cert[1]}, "watched_directory": {"path": Path(cert[0]).parent.as_posix()}}
    return {"resources": [{"@type": SECRET_TYPE, "name": name, "tls_certificate": certificate}]}


def _tls_context(secret: str, validation: dict[str, Any] | None, *, client: bool, sni: str | None = None) -> dict[str, Any]:
    # 왜 SDS 파일이고 인라인이 아닌가: 인라인 tls_certificates 는 watched_directory 를 두어도 갱신된 파일을 다시 읽지 않았다(시험에서 확인).
    # 파일 기반 SDS 는 다시 읽는다(platform ADR 0002)
    common: dict[str, Any] = {
        "tls_params": {"tls_minimum_protocol_version": "TLSv1_2"},  # 왜 1.2 이상: TLS 1.0/1.1 은 RFC 8996 이 폐기했다
        "tls_certificate_sds_secret_configs": [_sds_ref(secret)],
    }
    if validation:
        common["validation_context"] = validation
    if client:
        return {"name": "envoy.transport_sockets.tls", "typed_config": _typed("transport_sockets/tls/v3.UpstreamTlsContext", {"common_tls_context": common, "sni": sni})}
    common["alpn_protocols"] = ["h2", "http/1.1"]
    return {"name": "envoy.transport_sockets.tls", "typed_config": _typed("transport_sockets/tls/v3.DownstreamTlsContext", {"common_tls_context": common})}


def _cluster(name: str, host: str, port: int, *, tls: dict[str, Any] | None = None) -> dict[str, Any]:
    cluster: dict[str, Any] = {
        "name": name,
        "type": "STRICT_DNS",
        "connect_timeout": f"{CONNECT_SECONDS}s",
        "dns_lookup_family": "V4_ONLY",
        "load_assignment": {"cluster_name": name, "endpoints": [{"lb_endpoints": [{"endpoint": {"address": {"socket_address": {"address": host, "port_value": port}}}}]}]},
    }
    if tls:
        cluster["transport_socket"] = tls
    return cluster


def _rbac_policies(spec: RouteSpec) -> dict[str, Any]:
    policies: dict[str, Any] = {}
    for audience, roles in spec.roles.items():
        if audience is ExposureAudience.DEVICE_MTLS:
            # 왜 정규식 .+: authenticated 에 이름이 없으면 TLS 연결이기만 하면 맞는다. 클라이언트 인증서가 없으면 이름이 비어 맞지 않는다
            policies["device"] = {"permissions": [{"any": True}], "principals": [{"authenticated": {"principal_name": {"safe_regex": {"regex": ".+"}}}}]}
        else:
            for role in roles:
                policies[f"role:{role}"] = {
                    "permissions": [{"any": True}],
                    "principals": [
                        {
                            "metadata": {
                                "filter": "envoy.filters.http.jwt_authn",
                                "path": [{"key": "jwt_payload"}, {"key": "realm_access"}, {"key": "roles"}],
                                "value": {"list_match": {"one_of": {"string_match": {"exact": role}}}},
                            }
                        }
                    ],
                }
    return policies


def _route_entry(spec: RouteSpec, method: str | None) -> dict[str, Any]:
    match: dict[str, Any] = {"safe_regex": {"regex": spec.regex}} if spec.regex is not None else {"prefix": spec.prefix}
    headers = [{"name": ":method", "string_match": {"exact": method}}] if method else []
    if headers:
        match["headers"] = headers
    human = ExposureAudience.HUMAN_OIDC in spec.audiences
    bearer = human or ExposureAudience.EXTERNAL_MACHINE_TOKEN in spec.audiences
    per_filter: dict[str, Any] = {}
    if not human:
        per_filter["envoy.filters.http.ext_authz"] = _typed("filters/http/ext_authz/v3.ExtAuthzPerRoute", {"disabled": True})
    if bearer:
        optional = ExposureAudience.DEVICE_MTLS in spec.audiences
        per_filter["envoy.filters.http.jwt_authn"] = _typed(
            "filters/http/jwt_authn/v3.PerRouteConfig", {"requirement_name": f"{_slug(spec.service)}{'_or_none' if optional else ''}"}
        )
    else:
        per_filter["envoy.filters.http.jwt_authn"] = _typed("filters/http/jwt_authn/v3.PerRouteConfig", {"disabled": True})
    policies = _rbac_policies(spec)
    if policies:
        per_filter["envoy.filters.http.rbac"] = _typed("filters/http/rbac/v3.RBACPerRoute", {"rbac": {"rules": {"action": "ALLOW", "policies": policies}}})
    action: dict[str, Any] = {
        "cluster": f"service_{_slug(spec.service)}",
        "timeout": "0s" if spec.streaming else f"{ROUTE_SECONDS}s",
        # 왜 Host 를 서비스 이름으로: 서비스 주소는 https://<영역 이름>(D129, 계약 servers)이고 서비스의 TLS 서버 이름도 그 이름이다. 원래 Host 는 X-Forwarded-Host 로 남긴다
        "host_rewrite_literal": spec.service,
        "append_x_forwarded_host": True,
    }
    if spec.streaming:
        action["idle_timeout"] = f"{STREAM_IDLE_SECONDS}s"
    return {"match": match, "route": action, "typed_per_filter_config": per_filter}


def _builtin_routes() -> list[dict[str, Any]]:
    public = {
        "envoy.filters.http.ext_authz": _typed("filters/http/ext_authz/v3.ExtAuthzPerRoute", {"disabled": True}),
        "envoy.filters.http.jwt_authn": _typed("filters/http/jwt_authn/v3.PerRouteConfig", {"disabled": True}),
    }
    realm = f"/realms/{REALM}/"
    return [
        # 입구가 열지 않는 상태 경로(D129)
        *({"match": {"path": path}, "direct_response": {"status": 404}, "typed_per_filter_config": dict(public)} for path in HEALTH_PATHS),
        # 로그인에 필요한 경로. 로그인 전에 열려야 하므로 인증을 걸지 않는다(계약에 이 대상이 없다: change-requests/platform-001). 관리 콘솔(/admin)과 master realm 은 열지 않는다
        {"match": {"prefix": realm}, "route": {"cluster": KEYCLOAK, "timeout": f"{ROUTE_SECONDS}s"}, "typed_per_filter_config": dict(public)},
        {"match": {"prefix": "/resources/"}, "route": {"cluster": KEYCLOAK, "timeout": f"{ROUTE_SECONDS}s"}, "typed_per_filter_config": dict(public)},
        {"match": {"prefix": "/oauth2/"}, "route": {"cluster": OAUTH2_PROXY, "timeout": f"{ROUTE_SECONDS}s"}, "typed_per_filter_config": dict(public)},
    ]


def build_envoy(settings: PlatformSettings, gateway: Gateway, allowlist: DeviceAllowlist, ingress_issuer_key: str, internal_issuer_key: str) -> dict[str, Any]:
    device_ca_present = settings.device_ca_file is not None
    services = sorted({spec.service for spec in gateway.routes})
    human_services = sorted({spec.service for spec in gateway.routes if spec.audiences & {ExposureAudience.HUMAN_OIDC, ExposureAudience.EXTERNAL_MACHINE_TOKEN}})
    validation = {"trusted_ca": {"filename": DEVICE_CA}} if device_ca_present else None
    # 서비스 단위 라우트: 작업 라우트(긴 것) -> 접두어 라우트(긴 접두어가 먼저)
    entries: list[dict[str, Any]] = []
    for spec in gateway.routes:
        if spec.regex is not None:
            entries.append(_route_entry(spec, spec.method))
    prefixed = sorted((s for s in gateway.routes if s.prefix is not None), key=lambda s: -len(s.prefix or ""))
    for spec in prefixed:
        entries += [_route_entry(spec, method) for method in spec.methods]
    entries.append(
        {
            "match": {"prefix": "/"},
            "direct_response": {"status": 404},
            "typed_per_filter_config": {
                "envoy.filters.http.ext_authz": _typed("filters/http/ext_authz/v3.ExtAuthzPerRoute", {"disabled": True}),
                "envoy.filters.http.jwt_authn": _typed("filters/http/jwt_authn/v3.PerRouteConfig", {"disabled": True}),
            },
        }
    )
    jwt_providers = {
        _slug(service): {
            "issuer": settings.issuer,
            "audiences": [service],
            "forward": True,  # 왜 참: 서비스가 접근 토큰을 다시 검증한다(계약). 끄면 입구가 Authorization 을 지운다
            "remote_jwks": {"http_uri": {"uri": settings.jwks_url, "cluster": KEYCLOAK, "timeout": "5s"}, "cache_duration": "600s"},
            "payload_in_metadata": "jwt_payload",
        }
        for service in human_services
    }
    requirements: dict[str, Any] = {}
    for service in human_services:
        requirements[_slug(service)] = {"provider_name": _slug(service)}
        requirements[f"{_slug(service)}_or_none"] = {"requires_any": {"requirements": [{"provider_name": _slug(service)}, {"allow_missing": {}}]}}
    http_filters: list[dict[str, Any]] = [
        {
            "name": "envoy.filters.http.lua",
            "typed_config": _typed("filters/http/lua/v3.Lua", {"default_source_code": {"inline_string": _lua_device_check(allowlist, device_ca_present)}}),
        },
        {
            "name": "envoy.filters.http.ext_authz",
            "typed_config": _typed(
                "filters/http/ext_authz/v3.ExtAuthz",
                {
                    "transport_api_version": "V3",
                    "failure_mode_allow": False,
                    "status_on_error": {"code": "ServiceUnavailable"},
                    # 왜 filter_enabled_metadata: 기기 인증서나 Bearer 토큰으로 온 요청은 세션 확인을 건너뛴다(앞의 Lua 가 표시한다)
                    "filter_enabled_metadata": {"filter": "openit", "path": [{"key": "skip_session"}], "value": {"string_match": {"exact": "no"}}},
                    "http_service": {
                        "server_uri": {"uri": f"http://{OAUTH2_PROXY}:{OAUTH2_PROXY_PORT}", "cluster": OAUTH2_PROXY, "timeout": "2s"},
                        "authorization_request": {"allowed_headers": {"patterns": [{"exact": "cookie"}]}},
                        "authorization_response": {
                            "allowed_upstream_headers": {"patterns": [{"exact": "x-auth-request-access-token"}]},
                            "allowed_client_headers": {"patterns": [{"exact": "location"}, {"exact": "set-cookie"}, {"exact": "content-type"}]},
                        },
                    },
                },
            ),
        },
        {"name": "envoy.filters.http.lua.token", "typed_config": _typed("filters/http/lua/v3.Lua", {"default_source_code": {"inline_string": LUA_TOKEN}})},
        {
            "name": "envoy.filters.http.jwt_authn",
            "typed_config": _typed("filters/http/jwt_authn/v3.JwtAuthentication", {"providers": jwt_providers, "requirement_map": requirements}),
        },
        {"name": "envoy.filters.http.rbac", "typed_config": _typed("filters/http/rbac/v3.RBAC", {})},
        {"name": "envoy.filters.http.router", "typed_config": _typed("filters/http/router/v3.Router", {})},
    ]
    if not jwt_providers:
        http_filters = [f for f in http_filters if f["name"] != "envoy.filters.http.jwt_authn"]
    hcm = _typed(
        "filters/network/http_connection_manager/v3.HttpConnectionManager",
        {
            "stat_prefix": "ingress",
            "codec_type": "AUTO",
            "use_remote_address": True,
            "normalize_path": True,
            "merge_slashes": True,
            "path_with_escaped_slashes_action": "REJECT_REQUEST",
            "common_http_protocol_options": {"headers_with_underscores_action": "REJECT_REQUEST"},
            "request_headers_timeout": "10s",  # 왜: 헤더를 천천히 보내 연결을 붙잡는 공격(slowloris)을 막는 Envoy 문서의 권고 항목. 값은 선택이며 측정하지 않았다
            "forward_client_cert_details": "SANITIZE_SET",
            "set_current_client_cert_details": {"subject": True, "uri": False, "dns": False},
            "access_log": _access_log(),
            "route_config": {"name": "ingress", "virtual_hosts": [{"name": "ingress", "domains": ["*"], "routes": [*_builtin_routes(), *entries]}]},
            "http_filters": http_filters,
        },
    )
    listeners: list[dict[str, Any]] = [
        {
            "name": "ingress",
            "address": {"socket_address": {"address": ANY_ADDRESS, "port_value": settings.listen_port}},
            "filter_chains": [
                {
                    "transport_socket": _tls_context(SECRET_INGRESS, validation, client=False),
                    "filters": [{"name": "envoy.filters.network.http_connection_manager", "typed_config": hcm}],
                }
            ],
        }
    ]
    # 나가는 터널은 영역마다 포트 하나(포트가 곧 그 영역이다). 선언한 상대의 host:port 로만 CONNECT 를 이어 준다(D128)
    clusters: list[dict[str, Any]] = [
        _cluster(KEYCLOAK, KEYCLOAK, KEYCLOAK_PORT),
        _cluster(OAUTH2_PROXY, OAUTH2_PROXY, OAUTH2_PROXY_PORT),
    ]
    mtls = {"trusted_ca": {"filename": TRUST_LIST}}
    for service in services:
        upstream_validation = {**mtls, "match_typed_subject_alt_names": [{"san_type": "DNS", "matcher": {"exact": service}}]}
        clusters.append(
            _cluster(
                f"service_{_slug(service)}",
                service,
                settings.service_port,
                tls=_tls_context(SECRET_CLIENT, upstream_validation, client=True, sni=service),
            )
        )
    for spec in gateway.egress:
        routes: list[dict[str, Any]] = []
        for host, port in spec.targets:
            cluster = f"egress_{_slug(spec.service)}_{_slug(host)}_{port}"
            if all(c["name"] != cluster for c in clusters):
                clusters.append(_cluster(cluster, host, port))
            routes.append(
                {
                    "match": {"connect_matcher": {}, "headers": [{"name": ":authority", "string_match": {"exact": f"{host}:{port}"}}]},
                    "route": {"cluster": cluster, "upgrade_configs": [{"upgrade_type": "CONNECT", "connect_config": {}}]},
                }
            )
        # 왜 두 줄: CONNECT 요청은 접두어 일치에 걸리지 않아 connect_matcher 로 따로 거절한다(없으면 404 가 된다)
        denied = {"status": 403, "body": {"inline_string": "egress target is not declared\n"}}
        routes.append({"match": {"connect_matcher": {}}, "direct_response": denied})
        routes.append({"match": {"prefix": "/"}, "direct_response": denied})
        egress_hcm = _typed(
            "filters/network/http_connection_manager/v3.HttpConnectionManager",
            {
                "stat_prefix": f"egress_{_slug(spec.service)}",
                "codec_type": "HTTP1",
                "access_log": _access_log(),
                "upgrade_configs": [{"upgrade_type": "CONNECT"}],
                "route_config": {"name": f"egress_{_slug(spec.service)}", "virtual_hosts": [{"name": "egress", "domains": ["*"], "routes": routes}]},
                "http_filters": [{"name": "envoy.filters.http.router", "typed_config": _typed("filters/http/router/v3.Router", {})}],
            },
        )
        listeners.append(
            {
                "name": f"egress_{_slug(spec.service)}",
                "address": {"socket_address": {"address": ANY_ADDRESS, "port_value": spec.port}},
                "filter_chains": [{"filters": [{"name": "envoy.filters.network.http_connection_manager", "typed_config": egress_hcm}]}],
            }
        )
    return {
        # 왜 node: 파일 기반 SDS 는 노드 식별자를 요구한다(Envoy 의 오류 메시지). 값은 의미가 없다
        "node": {"id": GATEWAY_NAME, "cluster": REALM},
        # 왜 루프백: 관리 인터페이스를 밖에 열면 설정 변경·종료가 가능하다(Envoy 문서의 경고, ADR 0008)
        "admin": {"address": {"socket_address": {"address": "127.0.0.1", "port_value": ADMIN_PORT}}},
        "static_resources": {"listeners": listeners, "clusters": clusters},
    }


def build_sds(settings: PlatformSettings, ingress_issuer_key: str, internal_issuer_key: str) -> dict[str, str]:
    """SDS 파일 이름(gateway/sds 기준) -> 내용. 입구 서버 인증서와 영역 서비스에 보일 클라이언트 인증서."""
    files = {
        f"{SECRET_INGRESS}.yaml": _sds_file(SECRET_INGRESS, ingress_certificate_paths(settings, ingress_issuer_key)),
        f"{SECRET_CLIENT}.yaml": _sds_file(SECRET_CLIENT, gateway_client_paths(internal_issuer_key)),
    }
    return {name: "# 이 파일은 ./deploy 가 만든다. 손으로 고치지 않는다.\n" + yaml.safe_dump(body, sort_keys=False) for name, body in files.items()}


def render(config: dict[str, Any]) -> str:
    return "# 이 파일은 ./deploy 가 platform/src/openit_platform/gateway.py 로 만든다. 손으로 고치지 않는다(비밀은 없다).\n" + yaml.safe_dump(
        config, sort_keys=False, allow_unicode=True
    )


def summary(gateway: Gateway) -> str:
    """사람이 읽는 요약(라우트 수, 영역별 대상). deploy 가 출력한다."""
    lines = [f"{len(gateway.routes)}개 경로, 나가는 터널 {len(gateway.egress)}개"]
    for service in sorted({s.service for s in gateway.routes}):
        audiences = sorted({a.value for s in gateway.routes if s.service == service for a in s.audiences})
        lines.append(f"  {service}: {sum(1 for s in gateway.routes if s.service == service)}개 경로 ({', '.join(audiences)})")
    return "\n".join(lines)
