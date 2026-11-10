"""서버별 가장자리(area-edge)의 Envoy 설정(ADR 0026, 설계서 6절 배치).

서비스를 서버 여러 대에 나누면 영역 게이트웨이(Caddy)가 다른 서버의 호출을 받고 영역 서비스가 다른 서버의 상대에게 나가야 한다.
서버 한 대에는 영역 게이트웨이가 여럿일 수 있는데 서버의 주소는 하나라서 TLS 포트(OPENIT_SERVICE_PORT)와 ACME 의 80 번을 영역마다 게시할 수 없다.
그래서 서버마다 가장자리 Envoy 하나가 같은 포트로 받아 서버 이름(SNI·Host)으로 그 서버 안의 영역 게이트웨이에 이어 준다. 하는 일은 셋이다.

- TLS 8443(OPENIT_SERVICE_PORT): SNI 로 가르는 TCP 통과. TLS 를 끝내지 않는다(mTLS 는 영역 게이트웨이가 끝낸다, ADR 0021).
- 80: ACME http-01 검증 경로(/.well-known/acme-challenge/)만 Host 로 가려 영역 게이트웨이에 넘긴다(RFC 8555 8.3: 검증은 80 번이다).
- 9100: 감시(Prometheus)가 영역의 상태·지표 경로를 Host 로 가려 읽는다(영역 게이트웨이가 상태 경로 셋만 서비스에 잇는다, platform ADR 0007).
- 나가는 터널: 플랫폼 서버가 아닌 서버의 영역 서비스가 쓴다(플랫폼 서버에서는 입구가 터널을 맡는다). 입구와 같은 코드(gateway.egress_resources)다.

출력은 설정 하나이고 비밀은 없다. 같은 입력은 같은 출력이다.
"""

from __future__ import annotations

from typing import Any

from .area_gateway import MONITOR_PORT
from .gateway import (
    ADMIN_PORT,
    ANY_ADDRESS,
    Gateway,
    _access_log,
    _cluster,
    _slug,
    _typed,
    egress_resources,
)
from .settings import GATEWAY_NAME, REALM, PlatformSettings

EDGE_SERVICE = "area-edge"  # compose 서비스 이름. 영역 서비스의 나가는 터널 이름(별칭 gateway)도 이 컨테이너가 가진다
ACME_HTTP_PORT = 80
ACME_CHALLENGE_PREFIX = "/.well-known/acme-challenge/"  # RFC 8555 8.3


def gateway_service(area: str) -> str:
    """영역 게이트웨이의 compose 서비스 이름(deploy/compose.yaml)."""
    return f"{area}-gateway"


def _http_listener(name: str, port: int, hosts: dict[str, tuple[str, str]]) -> dict[str, Any]:
    """Host 로 가르는 평문 HTTP 리스너. hosts: 영역 -> (경로 접두어, 클러스터 이름)."""
    virtual_hosts = [
        {"name": _slug(area), "domains": [area, f"{area}:{port}"], "routes": [{"match": {"prefix": prefix}, "route": {"cluster": cluster, "timeout": "0s"}}]}
        for area, (prefix, cluster) in sorted(hosts.items())
    ]
    hcm = _typed(
        "filters/network/http_connection_manager/v3.HttpConnectionManager",
        {
            "stat_prefix": name,
            "codec_type": "AUTO",
            "access_log": _access_log(),
            "route_config": {"name": name, "virtual_hosts": virtual_hosts},
            "http_filters": [{"name": "envoy.filters.http.router", "typed_config": _typed("filters/http/router/v3.Router", {})}],
        },
    )
    return {
        "name": name,
        "address": {"socket_address": {"address": ANY_ADDRESS, "port_value": port}},
        "filter_chains": [{"filters": [{"name": "envoy.filters.network.http_connection_manager", "typed_config": hcm}]}],
    }


def build_edge(settings: PlatformSettings, plan: Gateway, *, areas: list[str], egress_services: list[str]) -> dict[str, Any]:
    """areas: 이 서버에서 도는 영역 게이트웨이를 가진 서비스들. egress_services: 이 서버에서 나가는 터널을 둘 서비스들(없으면 터널 없음)."""
    ordered = sorted(areas)
    tls_chains = [
        {
            "filter_chain_match": {"server_names": [area]},
            "filters": [
                {
                    "name": "envoy.filters.network.tcp_proxy",
                    "typed_config": _typed("filters/network/tcp_proxy/v3.TcpProxy", {"stat_prefix": f"tls_{_slug(area)}", "cluster": f"area_{_slug(area)}_tls"}),
                }
            ],
        }
        for area in ordered
    ]
    listeners: list[dict[str, Any]] = []
    clusters: list[dict[str, Any]] = []
    if ordered:
        listeners.append(
            {
                "name": "area_tls",
                "address": {"socket_address": {"address": ANY_ADDRESS, "port_value": settings.service_port}},
                # 왜 tls_inspector: ClientHello 의 SNI 를 읽어 filter_chain_match.server_names 로 가른다. TLS 는 끝내지 않는다
                "listener_filters": [{"name": "envoy.filters.listener.tls_inspector", "typed_config": _typed("filters/listener/tls_inspector/v3.TlsInspector", {})}],
                "filter_chains": tls_chains,
            }
        )
        listeners.append(_http_listener("area_acme", ACME_HTTP_PORT, {area: (ACME_CHALLENGE_PREFIX, f"area_{_slug(area)}_http") for area in ordered}))
        listeners.append(_http_listener("area_monitor", MONITOR_PORT, {area: ("/", f"area_{_slug(area)}_monitor") for area in ordered}))
        for area in ordered:
            host = gateway_service(area)
            clusters += [
                _cluster(f"area_{_slug(area)}_tls", host, settings.service_port),
                _cluster(f"area_{_slug(area)}_http", host, ACME_HTTP_PORT),
                _cluster(f"area_{_slug(area)}_monitor", host, MONITOR_PORT),
            ]
    egress_listeners, egress_clusters = egress_resources([spec for spec in plan.egress if spec.service in egress_services])
    listeners += egress_listeners
    clusters += egress_clusters
    return {
        "node": {"id": f"{GATEWAY_NAME}-{EDGE_SERVICE}", "cluster": REALM},
        "admin": {"address": {"socket_address": {"address": "127.0.0.1", "port_value": ADMIN_PORT}}},
        "static_resources": {"listeners": listeners, "clusters": clusters},
    }


__all__ = ["ACME_CHALLENGE_PREFIX", "ACME_HTTP_PORT", "EDGE_SERVICE", "build_edge", "gateway_service"]
