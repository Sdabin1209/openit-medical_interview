"""입구(Envoy) 설정: 노출 선언과 계약의 인증 요구에서 라우트가 나오고, 맞지 않으면 시작하지 않는다."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from openit_platform import gateway, pki
from openit_platform.contract.models import DeviceAllowlist, ExposureAudience

from .helpers import exposure, platform_settings, route

KEYS = ("ik", "ik2")


def _plan(repo: Path, exposures: dict[str, Any], *, device_ca: bool = True) -> gateway.Gateway:
    return gateway.plan(platform_settings(repo), exposures, repo / "contracts", device_ca)


def _routes(config: dict[str, Any]) -> list[dict[str, Any]]:
    listener = config["static_resources"]["listeners"][0]
    hcm = listener["filter_chains"][0]["filters"][0]["typed_config"]
    return hcm["route_config"]["virtual_hosts"][0]["routes"]


def _config(repo: Path, exposures: dict[str, Any], allowlist: DeviceAllowlist | None = None) -> dict[str, Any]:
    plan = _plan(repo, exposures)
    return gateway.build_envoy(platform_settings(repo), plan, allowlist or DeviceAllowlist(devices=[]), *KEYS)


def test_routes_come_from_exposure_and_contract_security(repo: Path) -> None:
    exposures = {
        "survey-service": exposure(
            [
                route("/v1/sessions", "DEVICE_MTLS", ("GET", "POST")),
                route("/v1/results", "HUMAN_OIDC", ("GET", "POST")),
                route("/v1/risk-signals", "EXTERNAL_MACHINE_TOKEN", ("POST",)),
            ]
        )
    }
    plan = _plan(repo, exposures)
    by_regex = {spec.regex: spec for spec in plan.routes}
    # 장치 경로: 세션 시작은 기기 인증서만 허용한다
    start = by_regex[r"/v1/sessions"]
    assert start.audiences == {ExposureAudience.DEVICE_MTLS} and start.method == "POST"
    # /v1/sessions 접두어에 든 직원 개입(/intervention)은 oidc 요구라 기기에게는 열리지 않는다(최소 권한)
    assert all("intervention" not in (spec.regex or "") for spec in plan.routes)
    # 사람 경로는 계약이 적은 역할만
    assert by_regex[r"/v1/results"].roles[ExposureAudience.HUMAN_OIDC] == ("clinician",) or "clinician" in by_regex[r"/v1/results"].roles[ExposureAudience.HUMAN_OIDC]
    # 외부 기계 호출자는 위험 신호만 열고 역할은 risk-detector
    risk = by_regex[r"/v1/risk\-signals"]
    assert risk.roles[ExposureAudience.EXTERNAL_MACHINE_TOKEN] == ("risk-detector",)


def test_mixed_audiences_share_one_route_with_both_policies(repo: Path) -> None:
    exposures = {"survey-service": exposure([route("/v1/questionnaires", "DEVICE_MTLS"), route("/v1/questionnaires", "HUMAN_OIDC")])}
    config = _config(repo, exposures)
    entry = next(r for r in _routes(config) if r.get("match", {}).get("safe_regex", {}).get("regex") == "/v1/questionnaires")
    policies = entry["typed_per_filter_config"]["envoy.filters.http.rbac"]["rbac"]["rules"]["policies"]
    assert set(policies) == {"device", "role:staff"}
    # 기기가 올 수 있으니 토큰이 없어도 jwt 검사를 통과시키되(allow_missing) 잘못된 토큰은 거절한다
    assert entry["typed_per_filter_config"]["envoy.filters.http.jwt_authn"]["requirement_name"].endswith("_or_none")


def test_audience_not_allowed_by_contract_stops_start(repo: Path) -> None:
    with pytest.raises(pki.ConfigError, match="계약의 인증 요구와 맞지 않는다"):
        _plan(repo, {"survey-service": exposure([route("/v1/start-codes", "DEVICE_MTLS", ("POST",))])})


def test_two_areas_cannot_open_the_same_public_path(repo: Path) -> None:
    exposures = {
        "survey-service": exposure([route("/static", "HUMAN_OIDC")]),
        "admin-console": exposure([route("/static", "HUMAN_OIDC")]),
    }
    with pytest.raises(pki.ConfigError, match="같은 공개 경로"):
        _plan(repo, exposures)


def test_machine_token_and_denied_are_not_exposed(repo: Path) -> None:
    exposures = {"model-runtime": exposure([route("/v1/extractions", "MACHINE_TOKEN", ("POST",)), route("/v1/model-status", "DENIED")])}
    assert _plan(repo, exposures).routes == []


def test_device_routes_need_device_ca(repo: Path) -> None:
    with pytest.raises(pki.ConfigError, match="OPENIT_DEVICE_CA_CERTIFICATE_FILE"):
        _plan(repo, {"survey-service": exposure([route("/v1/sessions", "DEVICE_MTLS", ("POST",))])}, device_ca=False)


def test_health_paths_are_never_exposed(repo: Path) -> None:
    routes = _routes(_config(repo, {"admin-console": exposure([route("/", "HUMAN_OIDC")])}))
    denied = {r["match"]["path"]: r["direct_response"]["status"] for r in routes if "path" in r.get("match", {})}
    assert denied == {"/healthz": 404, "/readyz": 404, "/metrics": 404}
    # 가려지는 순서: 상태 경로 거부가 접두어 '/' 보다 앞이다
    positions = [i for i, r in enumerate(routes) if r.get("match", {}).get("path") in denied]
    root = next(i for i, r in enumerate(routes) if r.get("match", {}).get("prefix") == "/" and "route" in r)
    assert max(positions) < root


def test_xfcc_is_sanitized_and_set(repo: Path) -> None:
    hcm = _config(repo, {})["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]
    assert hcm["forward_client_cert_details"] == "SANITIZE_SET"
    assert hcm["set_current_client_cert_details"]["subject"] is True
    assert hcm["common_http_protocol_options"]["headers_with_underscores_action"] == "REJECT_REQUEST"


def test_device_allowlist_is_embedded_in_lua(repo: Path) -> None:
    allowlist = DeviceAllowlist.model_validate({"devices": [{"device_id": "kiosk-01", "serial_number": "0a1b"}]})
    source = gateway._lua_device_check(allowlist, True)
    assert '["kiosk-01/a1b"] = true' in source  # 앞의 0 은 뗀 정규형으로 비교한다
    closed = gateway._lua_device_check(allowlist, False)
    assert "if true or cn == nil" in closed  # 기기 CA 가 없으면 인증서를 낸 요청을 모두 거절한다


def test_egress_is_limited_to_declared_targets(repo: Path) -> None:
    exposures = {"survey-service": exposure([], ["model-runtime", {"host": "push.example.org", "port": 443}])}
    plan = _plan(repo, exposures)
    assert plan.egress[0].targets == (("model-runtime", 8443), ("push.example.org", 443))
    assert gateway.egress_manifest(platform_settings(repo), plan) == {"survey-service": "http://gateway:3128"}
    config = gateway.build_envoy(platform_settings(repo), plan, DeviceAllowlist(devices=[]), *KEYS)
    egress = next(item for item in config["static_resources"]["listeners"] if item["name"].startswith("egress_"))
    routes = egress["filter_chains"][0]["filters"][0]["typed_config"]["route_config"]["virtual_hosts"][0]["routes"]
    allowed = [r["match"]["headers"][0]["string_match"]["exact"] for r in routes if "connect_matcher" in r["match"] and "headers" in r["match"]]
    assert allowed == ["model-runtime:8443", "push.example.org:443"]
    assert routes[-1]["direct_response"]["status"] == 403  # 선언하지 않은 상대는 거절


def test_upstream_host_is_the_service_name(repo: Path) -> None:
    routes = _routes(_config(repo, {"survey-service": exposure([route("/v1/results", "HUMAN_OIDC")])}))
    action = next(r for r in routes if r.get("match", {}).get("safe_regex", {}).get("regex") == "/v1/results")["route"]
    assert action["host_rewrite_literal"] == "survey-service" and action["append_x_forwarded_host"] is True


def test_streaming_route_has_no_overall_timeout(repo: Path) -> None:
    routes = _routes(_config(repo, {"survey-service": exposure([route("/v1/staff-alerts", "HUMAN_OIDC")])}))
    stream = next(r for r in routes if r.get("match", {}).get("safe_regex", {}).get("regex") == "/v1/staff\\-alerts/stream")
    assert stream["route"]["timeout"] == "0s" and stream["route"]["idle_timeout"] == "45s"
    plain = next(r for r in routes if r.get("match", {}).get("safe_regex", {}).get("regex") == "/v1/staff\\-alerts")
    assert plain["route"]["timeout"] == "55s"  # 계약 GatewayPatientRouteLimitSeconds


def test_same_input_same_output(repo: Path) -> None:
    exposures = {"survey-service": exposure([route("/v1/results", "HUMAN_OIDC")])}
    assert gateway.render(_config(repo, exposures)) == gateway.render(_config(repo, exposures))


def test_exposure_files_are_validated_against_contract(tmp_path: Path) -> None:
    (tmp_path / "survey-service.json").write_text('{"routes":[{"path_prefix":"no-slash","methods":["GET"],"audience":"HUMAN_OIDC"}],"egress":[]}', encoding="utf-8")
    with pytest.raises(pki.ConfigError, match="계약을 어겼다"):
        gateway.load_exposures(tmp_path)
    (tmp_path / "survey-service.json").unlink()
    (tmp_path / "unknown.json").write_text('{"routes":[],"egress":[]}', encoding="utf-8")
    with pytest.raises(pki.ConfigError, match="ServiceName"):
        gateway.load_exposures(tmp_path)


def test_certificates_are_read_through_file_sds_that_watches_the_folder(repo: Path) -> None:
    """인라인 tls_certificates 는 갱신된 파일을 다시 읽지 않았다(샌드박스에서 확인). 파일 기반 SDS 와 watched_directory 를 쓴다."""
    config = _config(repo, {})
    text = gateway.render(config)
    assert "tls_certificates:" not in text and config["node"]["id"] == "gateway"
    sds = gateway.build_sds(platform_settings(repo), *KEYS)
    assert set(sds) == {"ingress_cert.yaml", "gateway_client.yaml"}
    body = yaml.safe_load(sds["ingress_cert.yaml"])["resources"][0]["tls_certificate"]
    assert body["watched_directory"]["path"] == "/ingress-certs/certificates/ik/openit.internal"
    assert body["private_key"]["filename"].endswith("/openit.internal.key")


def test_platform_in_egress_opens_the_issuer_host_and_port(repo: Path) -> None:
    """계약 EgressTarget: 서비스 이름 platform 은 OIDC 발급자 주소의 호스트와 포트로 나가는 터널이다(토큰 엔드포인트와 JWKS)."""
    cfg = platform_settings(repo)
    plan = _plan(repo, {"survey-service": exposure([], ["model-runtime", "platform"])})
    assert plan.egress[0].targets == (("model-runtime", 8443), (cfg.public_host, cfg.public_port))
    config = gateway.build_envoy(cfg, plan, DeviceAllowlist(devices=[]), *KEYS)
    egress = next(item for item in config["static_resources"]["listeners"] if item["name"].startswith("egress_"))
    routes = egress["filter_chains"][0]["filters"][0]["typed_config"]["route_config"]["virtual_hosts"][0]["routes"]
    allowed = [r["match"]["headers"][0]["string_match"]["exact"] for r in routes if "connect_matcher" in r["match"] and "headers" in r["match"]]
    assert allowed == ["model-runtime:8443", f"{cfg.public_host}:{cfg.public_port}"]
    clusters = {c["name"]: c for c in config["static_resources"]["clusters"]}
    issuer_cluster = clusters["egress_survey_service_openit_internal_8443"]
    assert issuer_cluster["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"]["socket_address"] == {
        "address": cfg.public_host,
        "port_value": cfg.public_port,
    }


def test_platform_in_egress_follows_a_different_issuer_port(repo: Path) -> None:
    cfg = platform_settings(repo, OPENIT_OIDC_ISSUER_URL="https://openit.internal/realms/openit")
    plan = gateway.plan(cfg, {"model-runtime": exposure([], ["platform"])}, repo / "contracts", True)
    assert plan.egress[0].targets == (("openit.internal", 443),)


# ---------------------------------------------------------------- 브라우저의 한 출처(admin-console-005, 계약 9.0.0)

ONE_ORIGIN = {
    "admin-console": exposure([route("/console/", "HUMAN_OIDC")]),
    "survey-service": exposure([route("/v1/results", "HUMAN_OIDC"), route("/v1/start-codes", "HUMAN_OIDC", ("POST",)), route("/v1/staff-alerts", "HUMAN_OIDC")]),
    "model-runtime": exposure([route("/v1/model-status", "HUMAN_OIDC"), route("/v1/model-packages", "HUMAN_OIDC", ("GET",))]),
}


def test_screen_path_and_both_services_v1_paths_merge_on_one_origin(repo: Path) -> None:
    """화면 접근 경로(admin-console 의 /console/)와 두 서비스의 /v1/ 경로가 한 출처의 한 라우트 표로 합쳐지고 모두 사람 인증(세션 확인)을 지난다."""
    routes = _routes(_config(repo, ONE_ORIGIN))
    served = {}
    for entry in routes:
        if "route" not in entry or "cluster" not in entry["route"] or not entry["route"]["cluster"].startswith("service_"):
            continue
        match = entry["match"]
        served[match.get("safe_regex", {}).get("regex") or match["prefix"]] = entry
    clusters = {key: entry["route"]["cluster"] for key, entry in served.items()}
    assert clusters["/console/"] == "service_admin_console"
    assert clusters["/v1/results"] == "service_survey_service" and clusters["/v1/start\\-codes"] == "service_survey_service"
    assert clusters["/v1/model\\-status"] == "service_model_runtime" and clusters["/v1/model\\-packages"] == "service_model_runtime"
    # 사람 인증 경로는 세션 확인(ext_authz)을 끄지 않는다. 화면 경로도 같다(oauth2-proxy 가 로그인으로 보낸다)
    for key in ("/console/", "/v1/results", "/v1/model\\-status"):
        assert "envoy.filters.http.ext_authz" not in served[key]["typed_per_filter_config"], key
    # 한 출처의 한 가상 호스트에 모두 있다(경로로만 나뉜다)
    config = _config(repo, ONE_ORIGIN)
    hosts = config["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]["route_config"]["virtual_hosts"]
    assert len(hosts) == 1 and hosts[0]["domains"] == ["*"]
    # 알림 스트림 경로는 전체 시간 제한을 끈다(admin-console-005 덧붙임)
    stream = served["/v1/staff\\-alerts/stream"]
    assert stream["route"]["timeout"] == "0s" and stream["route"]["idle_timeout"] == "45s"


def test_the_same_path_opened_by_two_services_stops_start(repo: Path) -> None:
    exposures = {"survey-service": exposure([route("/v1/results", "HUMAN_OIDC")]), "model-runtime": exposure([route("/v1/results", "HUMAN_OIDC")])}
    with pytest.raises(pki.ConfigError, match="같은 공개 경로를 두 영역이 연다: GET /v1/results"):
        _plan(repo, exposures)
    clash = {"admin-console": exposure([route("/v1/results", "HUMAN_OIDC")]), "survey-service": exposure([route("/v1/results", "HUMAN_OIDC")])}
    with pytest.raises(pki.ConfigError, match="같은 공개 경로"):
        _plan(repo, clash)


def test_services_with_disjoint_v1_prefixes_do_not_clash(repo: Path) -> None:
    plan = _plan(repo, ONE_ORIGIN)
    assert {spec.service for spec in plan.routes} == {"admin-console", "survey-service", "model-runtime"}
