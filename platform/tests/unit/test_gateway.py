"""입구(Envoy) 설정: 노출 선언과 계약의 인증 요구에서 라우트가 나오고, 맞지 않으면 시작하지 않는다."""

from pathlib import Path
from typing import Any

import pytest

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
    allowed = [r["match"]["headers"][0]["string_match"]["exact"] for r in routes if "connect_matcher" in r["match"]]
    assert allowed == ["model-runtime:8443", "push.example.org:443"]
    assert routes[-1]["direct_response"]["status"] == 403  # 선언하지 않은 상대는 거절


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
