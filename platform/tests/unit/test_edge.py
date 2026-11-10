"""서버별 가장자리(area-edge) 설정: SNI·Host 로 서버 안 영역 게이트웨이에 잇고, 나가는 터널은 입구와 같은 코드로 만든다(ADR 0026)."""

from pathlib import Path
from typing import Any

from openit_platform import edge, gateway
from openit_platform.contract.models import ServiceName

from .helpers import exposure, platform_settings, route


def _plan(repo: Path) -> gateway.Gateway:
    exposures = {
        "survey-service": exposure([route("/v1/sessions", "DEVICE_MTLS", ("GET", "POST"))], egress=["model-runtime"]),
        "model-runtime": exposure([route("/v1/model-status", "HUMAN_OIDC")], egress=["platform", {"host": "registry", "port": 443}]),
    }
    return gateway.plan(platform_settings(repo), exposures, repo / "contracts", True)


def _listeners(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in config["static_resources"]["listeners"]}


def test_tls_is_passed_through_by_sni_to_the_gateway_of_each_area(repo: Path) -> None:
    settings = platform_settings(repo)
    config = edge.build_edge(settings, _plan(repo), areas=["model-runtime", "survey-service"], egress_services=[])
    tls = _listeners(config)["area_tls"]
    assert tls["address"]["socket_address"]["port_value"] == settings.service_port
    assert [f["filter_chain_match"]["server_names"] for f in tls["filter_chains"]] == [["model-runtime"], ["survey-service"]]
    # TLS 를 끝내지 않는다: 어떤 필터 체인에도 transport_socket 이 없다(mTLS 는 영역 게이트웨이가 끝낸다)
    assert all("transport_socket" not in f for f in tls["filter_chains"])
    clusters = {c["name"]: c["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"]["socket_address"] for c in config["static_resources"]["clusters"]}
    assert clusters["area_survey_service_tls"] == {"address": "survey-service-gateway", "port_value": settings.service_port}


def test_acme_listener_only_passes_the_challenge_path(repo: Path) -> None:
    config = edge.build_edge(platform_settings(repo), _plan(repo), areas=["model-runtime"], egress_services=[])
    acme = _listeners(config)["area_acme"]
    assert acme["address"]["socket_address"]["port_value"] == 80
    hcm = acme["filter_chains"][0]["filters"][0]["typed_config"]
    host = hcm["route_config"]["virtual_hosts"][0]
    assert host["domains"] == ["model-runtime", "model-runtime:80"]
    assert [r["match"] for r in host["routes"]] == [{"prefix": "/.well-known/acme-challenge/"}]  # RFC 8555 8.3 의 검증 경로만 열린다


def test_monitor_listener_routes_by_host_to_the_gateway_monitor_port(repo: Path) -> None:
    config = edge.build_edge(platform_settings(repo), _plan(repo), areas=["survey-service"], egress_services=[])
    hcm = _listeners(config)["area_monitor"]["filter_chains"][0]["filters"][0]["typed_config"]
    assert hcm["route_config"]["virtual_hosts"][0]["domains"] == ["survey-service", "survey-service:9100"]
    cluster = next(c for c in config["static_resources"]["clusters"] if c["name"] == "area_survey_service_monitor")
    assert cluster["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"]["socket_address"] == {"address": "survey-service-gateway", "port_value": 9100}


def test_egress_tunnels_exist_only_for_requested_services_and_match_the_ingress_ports(repo: Path) -> None:
    plan = _plan(repo)
    config = edge.build_edge(platform_settings(repo), plan, areas=["model-runtime"], egress_services=["model-runtime"])
    names = _listeners(config)
    assert "egress_model_runtime" in names
    assert "egress_survey_service" not in names
    wanted = next(s.port for s in plan.egress if s.service == "model-runtime")
    assert names["egress_model_runtime"]["address"]["socket_address"]["port_value"] == wanted  # OPENIT_EGRESS_PROXY 가 가리키는 포트와 같다


def test_without_areas_only_the_requested_tunnels_remain(repo: Path) -> None:
    config = edge.build_edge(platform_settings(repo), _plan(repo), areas=[], egress_services=["survey-service"])
    assert set(_listeners(config)) == {"egress_survey_service"}


def test_same_input_same_output(repo: Path) -> None:
    plan = _plan(repo)
    first = gateway.render(edge.build_edge(platform_settings(repo), plan, areas=["model-runtime"], egress_services=["model-runtime"]))
    second = gateway.render(edge.build_edge(platform_settings(repo), plan, areas=["model-runtime"], egress_services=["model-runtime"]))
    assert first == second


def test_areas_are_contract_service_names() -> None:
    assert edge.gateway_service(ServiceName.model_runtime.value) == "model-runtime-gateway"
