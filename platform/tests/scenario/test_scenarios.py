"""platform 종단 시험(샌드박스): 기기 인증서, XFCC, 영역 게이트웨이, 사람 OIDC, 기계 토큰, 나가는 터널, 감시, 인증서 갱신, 루트 교체.

끝 조건(브리프): 기기 인증서 있는 요청만 키오스크 경로 통과, 없는 요청 거부, XFCC 위조 헤더 제거, OIDC 토큰 없는 직원 경로 거부, 기계 토큰 역할별 허용·거부.
실행: `cd platform && uv run pytest -m sandbox tests/scenario` (docker 필요, 10분 안팎).
"""

from __future__ import annotations

import base64
import json
import re
import ssl
from typing import Any
from urllib.parse import urlencode

import pytest
import yaml
from jsonschema import Draft202012Validator

from openit_platform import area_gateway
from openit_platform.contract.models import UserRole

from .client import Client, Response, login_form
from .sandbox import ACME_URL, CLIENT_CERT_AREA, KC_PASSWORD, REPO, Sandbox

pytestmark = pytest.mark.sandbox

HOST = "openit.internal"
BASE = f"https://{HOST}:8443"
TOKEN_URL = f"{BASE}/realms/openit/protocol/openid-connect/token"
SERVICE_NAMES = ("survey-service", "model-runtime", "admin-console", "kiosk-frontend")
CONTRACT = yaml.safe_load((REPO / "contracts" / "components.yaml").read_text(encoding="utf-8"))


def contract_validator(name: str) -> Draft202012Validator:
    """계약의 스키마 하나로 검증한다(format 단언을 켠다: 계약 README '시각·식별자·검증기')."""
    return Draft202012Validator({"$ref": f"#/components/schemas/{name}", "components": CONTRACT["components"]}, format_checker=Draft202012Validator.FORMAT_CHECKER)


def decode_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    def part(text: str) -> dict[str, Any]:
        return json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)))

    header, payload, _ = token.split(".")
    return part(header), part(payload)


def client(box: Sandbox, cert: str | None = None) -> Client:
    return Client(port=box.published_port("ingress-acme", 8443), server_name=HOST, trust=box.deploy_dir / "pki" / "trust-bundle.pem", cert=box.device_files(cert) if cert else None)


def machine_token(box: Sandbox, caller: str) -> str:
    body = urlencode({"grant_type": "client_credentials", "client_id": f"machine-{caller}", "client_secret": box.machine_secret(caller)})
    response = client(box).request("POST", TOKEN_URL, body=body)
    assert response.status == 200, response.body[:300]
    return json.loads(response.body)["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(box: Sandbox, user: str) -> tuple[Client, Response]:
    """브라우저처럼 로그인한다: 화면 경로 -> oauth2-proxy -> Keycloak 로그인 -> 되돌아옴. 로그인 뒤의 응답(에코 상류)을 함께 준다."""
    session = client(box)
    first = session.request("GET", f"{BASE}/console/", headers={"Accept": "text/html"})
    assert first.status == 302, f"로그인으로 보내지 않았다: {first.status}"
    page = session.follow(first, f"{BASE}/console/")
    assert page.status == 200 and "kc-form-login" in page.body
    action, _ = login_form(page.body)
    posted = session.request("POST", action, body=urlencode({"username": user, "password": KC_PASSWORD, "credentialId": ""}))
    final = session.follow(posted, action)
    assert final.status == 200, f"로그인 뒤 화면 경로가 열리지 않았다: {final.status} {final.body[:200]}"
    return session, final


# ---------------------------------------------------------------- 기기 인증서(mTLS)와 XFCC


def test_device_certificate_on_allowlist_passes_and_service_sees_xfcc(box: Sandbox) -> None:
    response = client(box, "kiosk-01").get("/v1/sessions/s1/state")
    assert response.status == 200, response.body
    echo = response.lines()
    assert echo["service"] == "survey-service" and echo["path"] == "/v1/sessions/s1/state"
    assert 'Subject="CN=kiosk-01"' in echo["xfcc"] and echo["xfcc"].startswith("Hash=")  # 계약 ForwardedClientCertValue: 기기 ID 는 Subject 의 CN
    contract_validator("ForwardedClientCertValue").validate(echo["xfcc"])
    # 입구가 영역 게이트웨이에 사설 CA 의 클라이언트 인증서(SAN gateway)를 보였고(영역 사이 mTLS) 게이트웨이가 XFCC 를 평문 상류에 넘겼다
    assert client(box, "kiosk-01").get("/kiosk/index.html").status == 200  # 키오스크 화면 경로도 기기 인증서로 열린다


def test_request_without_certificate_is_denied_on_device_paths(box: Sandbox) -> None:
    anonymous = client(box)
    assert anonymous.get("/v1/sessions/s1/state").status == 403
    assert anonymous.get("/kiosk/index.html").status == 403
    assert anonymous.request("POST", f"{BASE}/v1/sessions", body="{}", headers={"Content-Type": "application/json"}).status == 403


def test_certificate_not_on_allowlist_is_denied(box: Sandbox) -> None:
    for name in ("kiosk-02", "kiosk-01-other-serial"):  # 조직 CA 가 발급했지만 허용 목록(기기 ID 와 일련번호)에 없다
        response = client(box, name).get("/v1/sessions/s1/state")
        assert response.status == 403 and "not allowed" in response.body, name


def test_certificate_from_unknown_ca_fails_the_handshake(box: Sandbox) -> None:
    with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
        client(box, "rogue").get("/v1/sessions/s1/state")


def test_forged_xfcc_is_replaced_by_the_verified_certificate(box: Sandbox) -> None:
    forged = {"X-Forwarded-Client-Cert": 'Hash=00;Subject="CN=kiosk-99"'}
    echo = client(box, "kiosk-01").get("/v1/sessions/s1/state", headers=forged).lines()
    assert "kiosk-99" not in echo["xfcc"] and 'Subject="CN=kiosk-01"' in echo["xfcc"]


def test_forged_xfcc_is_removed_when_no_certificate_was_presented(box: Sandbox) -> None:
    forged = {"X-Forwarded-Client-Cert": 'Hash=00;Subject="CN=kiosk-01"', **bearer(machine_token(box, "detector"))}
    response = client(box).request("POST", f"{BASE}/v1/risk-signals", headers=forged, body="{}")
    assert response.status == 200 and response.lines()["xfcc"] == ""  # 서비스가 위조된 기기 신원을 받지 않는다


# ---------------------------------------------------------------- 사람(OIDC)


def test_staff_path_without_token_is_denied(box: Sandbox) -> None:
    anonymous = client(box)
    assert anonymous.get("/v1/results").status == 401
    assert anonymous.request("POST", f"{BASE}/v1/start-codes", body="{}").status == 401
    assert anonymous.get("/v1/results", headers=bearer("not-a-jwt")).status == 401
    assert anonymous.get("/v1/results", headers=bearer(machine_token(box, "hospital")[:-6] + "AAAAAA")).status == 401  # 서명이 틀린 토큰


def test_login_gives_services_an_rfc9068_token_with_contract_claims(box: Sandbox) -> None:
    _, final = login(box, "staff-1")
    token = final.lines()["authorization"].removeprefix("Bearer ")
    header, claims = decode_jwt(token)
    assert header["typ"] == "at+jwt"  # RFC 9068 2.1
    contract_validator("AccessTokenHeader").validate(header)
    contract_validator("UserIdentityClaims").validate(claims)  # iss·sub·aud·exp·iat·jti·client_id·realm_access.roles(UserRole 만)
    # 실제 Keycloak 이 낸 사람 접근 토큰의 역할은 계약 UserRole 만 담는다(기본 역할 offline_access·uma_authorization·default-roles-openit 이 없다)
    assert claims["realm_access"]["roles"] == ["staff"]
    assert set(claims["realm_access"]["roles"]) <= {role.value for role in UserRole}
    assert claims["client_id"] == "oauth2-proxy"
    assert claims["iss"] == f"{BASE}/realms/openit"
    assert {"survey-service", "model-runtime", "admin-console"} <= set(claims["aud"])


def test_userinfo_groups_carry_only_the_users_contract_roles(box: Sandbox) -> None:
    """admin-console-001: 화면이 읽는 oauth2-proxy 의 /oauth2/userinfo 의 groups 가 사람의 realm 역할(UserRole)만 준다."""
    allowed = {role.value for role in UserRole}
    for user, role in (("staff-1", "staff"), ("clinician-1", "clinician")):
        session, _ = login(box, user)
        response = session.get("/oauth2/userinfo")
        assert response.status == 200, response.body[:200]
        info = json.loads(response.body)
        # --provider=oidc 는 groups 클레임을 그대로 준다(keycloak-oidc 제공자는 `role:<이름>` 항목을 더 붙여서 바꿨다, platform ADR 0004)
        assert info["groups"] == [role] and set(info["groups"]) <= allowed, info  # offline_access·default-roles-openit 같은 Keycloak 기본 역할이 없다
        assert info["preferredUsername"] == user
    assert client(box).get("/oauth2/userinfo").status == 401  # 세션이 없으면 열리지 않는다


def test_roles_decide_the_staff_paths(box: Sandbox) -> None:
    staff, _ = login(box, "staff-1")
    assert staff.request("POST", f"{BASE}/v1/start-codes", body="{}").status == 200  # staff 역할이 요구된다
    assert staff.get("/v1/results").status == 403  # clinician 이 요구된다
    clinician, _ = login(box, "clinician-1")
    assert clinician.get("/v1/results").status == 200
    assert clinician.request("POST", f"{BASE}/v1/start-codes", body="{}").status == 403
    # 로그인 뒤에는 같은 토큰을 Bearer 로 직접 보내도 같은 결과다(쿠키 없이)
    token = clinician.get("/console/").lines()["authorization"].removeprefix("Bearer ")
    assert client(box).get("/v1/results", headers=bearer(token)).status == 200
    assert client(box).request("POST", f"{BASE}/v1/start-codes", body="{}", headers=bearer(token)).status == 403


def test_human_token_does_not_open_machine_or_device_paths(box: Sandbox) -> None:
    staff, _ = login(box, "staff-1")
    token = staff.get("/console/").lines()["authorization"].removeprefix("Bearer ")
    assert client(box).request("POST", f"{BASE}/v1/risk-signals", body="{}", headers=bearer(token)).status == 403  # risk-detector 가 요구된다
    assert client(box).get("/v1/sessions/s1/state", headers=bearer(token)).status == 403  # 기기 경로는 기기 인증서만


# ---------------------------------------------------------------- 기계 토큰


def test_machine_token_roles_allow_and_deny(box: Sandbox) -> None:
    hospital = bearer(machine_token(box, "hospital"))
    detector = bearer(machine_token(box, "detector"))
    lab = bearer(machine_token(box, "lab"))
    web = client(box)
    assert web.get("/v1/results", headers=hospital).status == 200  # result-reader
    assert web.request("POST", f"{BASE}/v1/risk-signals", headers=hospital, body="{}").status == 403
    assert web.request("POST", f"{BASE}/v1/risk-signals", headers=detector, body="{}").status == 200  # risk-detector
    assert web.get("/v1/results", headers=detector).status == 403
    assert web.get("/v1/results", headers=lab).status == 403  # case-reader 는 결과를 읽지 못한다
    assert web.get("/v1/case-exports", headers=lab).status == 404  # 같은 서버 안의 호출(MACHINE_TOKEN)은 입구로 내보내지 않는다
    assert web.request("POST", f"{BASE}/v1/risk-signals", body="{}").status == 401  # 토큰 없음


def test_machine_token_claims_follow_rfc9068(box: Sandbox) -> None:
    header, claims = decode_jwt(machine_token(box, "hospital"))
    assert header["typ"] == "at+jwt" and claims["client_id"] == "machine-hospital" and claims["aud"] == "survey-service"
    assert claims["realm_access"]["roles"] == ["result-reader"]
    contract_validator("TokenAudienceClaim").validate(claims["aud"])
    contract_validator("MachineIdentityClaims").validate(claims)  # 계약 9.0.0: 기계 접근 토큰의 필수 클레임과 MachineRole 만 담긴 realm_access
    assert claims["sub"] and claims["iss"] == f"{BASE}/realms/openit"


def test_token_for_another_audience_is_not_accepted(box: Sandbox) -> None:
    hospital = bearer(machine_token(box, "hospital"))  # aud 는 survey-service 뿐이다
    status = client(box).get("/v1/model-status", headers=hospital).status
    assert status in (401, 403)  # 왜 둘: Envoy jwt_authn 은 aud 불일치를 403 으로 낸다(platform ADR 0003). 열리지 않는 것이 요점이다


# ---------------------------------------------------------------- 입구가 열지 않는 것

NOT_EXPOSED = ["/healthz", "/readyz", "/metrics", "/realms/master/protocol/openid-connect/certs", "/admin/master/console/", "/v1/case-exports", "/unknown"]


@pytest.mark.parametrize("path", NOT_EXPOSED)
def test_paths_that_are_not_exposed_are_404(box: Sandbox, path: str) -> None:
    assert client(box).get(path).status == 404


def test_login_endpoints_of_the_realm_are_public(box: Sandbox) -> None:
    assert client(box).get("/realms/openit/.well-known/openid-configuration").status == 200


# ---------------------------------------------------------------- 나가는 터널(CONNECT)


def curl_in_client(box: Sandbox, *args: str, stdin: str | None = None) -> tuple[int, str]:
    result = box.exec("sandbox-client", "curl", "-sS", "--max-time", "15", "--cacert", "/etc/openit/trust-list.pem", *args, check=False, stdin=stdin)
    return result.returncode, result.stdout + result.stderr


def own_certificate(area: str = CLIENT_CERT_AREA) -> list[str]:
    """영역 게이트웨이가 받아 영역 안 공유 폴더에 둔 클라이언트 인증서와 키(서비스가 읽기 전용으로 보는 것과 같다)."""
    cert, key = area_gateway.certificate_paths(area, ACME_URL)
    return ["--cert", cert, "--key", key]


def egress_proxy(box: Sandbox) -> str:
    return json.loads((box.deploy_dir / "generated" / "gateway" / "egress-proxies.json").read_text(encoding="utf-8"))["survey-service"]


def connect(box: Sandbox, target: str) -> tuple[int, str]:
    return curl_in_client(box, *own_certificate(), "--proxytunnel", "-x", egress_proxy(box), "-o", "/dev/null", "-w", "%{http_code}", f"https://{target}/")


def test_egress_goes_only_to_declared_targets(box: Sandbox) -> None:
    code, out = connect(box, "model-runtime:8443")
    assert code == 0 and out.strip().endswith("200"), out  # 선언한 상대(Exposure.egress). 이웃의 영역 게이트웨이에 자기 클라이언트 인증서를 보인다
    for target in ("survey-service:8443", "admin-console:8443", "example.org:443"):
        code, out = connect(box, target)
        assert code != 0 and "CONNECT tunnel failed, response 403" in out, (target, out)


def test_service_reaches_the_token_endpoint_and_jwks_through_the_egress_tunnel(box: Sandbox) -> None:
    """Exposure.egress 의 platform: 발급자의 호스트·포트로 CONNECT 가 열린다. 디스커버리 -> 토큰 엔드포인트(client credentials) -> JWKS 가 그 길을 쓴다."""
    proxy = ["--proxytunnel", "-x", egress_proxy(box)]
    code, out = curl_in_client(box, *proxy, f"{BASE}/realms/openit/.well-known/openid-configuration")
    assert code == 0, out
    discovery = json.loads(out)
    assert discovery["issuer"] == f"{BASE}/realms/openit"
    body = urlencode({"grant_type": "client_credentials", "client_id": "machine-hospital", "client_secret": box.machine_secret("hospital")})
    code, out = curl_in_client(box, *proxy, "--data-binary", "@-", "-H", "Content-Type: application/x-www-form-urlencoded", discovery["token_endpoint"], stdin=body)
    assert code == 0, out[:300]
    token = json.loads(out)["access_token"]
    _, claims = decode_jwt(token)
    contract_validator("MachineIdentityClaims").validate(claims)
    code, out = curl_in_client(box, *proxy, discovery["jwks_uri"])
    assert code == 0 and json.loads(out)["keys"], out[:200]
    # 받은 토큰은 입구의 기계 경로에서 역할대로 통한다
    assert client(box).get("/v1/results", headers=bearer(token)).status == 200
    # 같은 터널로 발급자가 아닌 호스트·포트는 열리지 않는다
    code, out = curl_in_client(box, *proxy, "--connect-timeout", "5", f"https://{HOST}:9999/")
    assert code != 0 and "CONNECT tunnel failed, response 403" in out, out


# ---------------------------------------------------------------- 영역 게이트웨이(platform ADR 0007)


def echo_via_gateway(box: Sandbox, area: str, *args: str, path: str = "/v1/sessions/s1/state") -> tuple[int, dict[str, str], str]:
    code, out = curl_in_client(box, *args, f"https://{area}:8443{path}")
    echo = dict(line.split("=", 1) for line in out.splitlines() if "=" in line) if code == 0 else {}
    return code, echo, out


def test_area_gateway_refuses_calls_without_a_client_certificate(box: Sandbox) -> None:
    for area in SERVICE_NAMES:
        code, _, out = echo_via_gateway(box, area)
        assert code != 0, (area, out)  # 클라이언트 인증서가 없으면 TLS 핸드셰이크에서 거절된다(require_and_verify)
        assert "service=" not in out


def test_area_gateway_accepts_a_neighbor_certificate_but_drops_a_forged_xfcc(box: Sandbox) -> None:
    forged = ["-H", 'X-Forwarded-Client-Cert: Hash=00;Subject="CN=kiosk-99"']
    code, echo, out = echo_via_gateway(box, "model-runtime", *own_certificate(), *forged)
    assert code == 0 and echo["service"] == "model-runtime", out  # 사설 CA 가 발급한 이웃(survey-service)의 인증서로 영역 사이 mTLS 가 통한다
    assert echo["xfcc"] == ""  # 입구(SAN gateway)가 아닌 호출이 보낸 신원 머리글은 서비스에 닿지 않는다
    other = echo_via_gateway(box, "kiosk-frontend", *own_certificate(), *forged)
    assert other[0] == 0 and other[1]["xfcc"] == ""


def test_area_gateway_forwards_xfcc_only_from_the_ingress_certificate(box: Sandbox) -> None:
    through_ingress = client(box, "kiosk-01").get("/v1/sessions/s1/state", headers={"X-Forwarded-Client-Cert": 'Hash=00;Subject="CN=kiosk-99"'}).lines()
    assert 'Subject="CN=kiosk-01"' in through_ingress["xfcc"] and "kiosk-99" not in through_ingress["xfcc"]  # 입구가 검증한 기기만 서비스에 보인다


def test_area_gateway_does_not_serve_a_service_host_on_a_mismatching_sni(box: Sandbox) -> None:
    """SNI 와 Host 가 다른 요청은 클라이언트 인증이 걸리지 않은 연결 정책으로 들어올 수 있다. strict_sni_host 가 닫는다."""
    code, out = curl_in_client(box, "--connect-to", "survey-service:8443:model-runtime:8443", "https://survey-service:8443/v1/results")
    assert code != 0 or "service=" not in out, out
    code, out = curl_in_client(box, *own_certificate(), "-H", "Host: survey-service", "https://model-runtime:8443/v1/results")
    assert "service=survey-service" not in out, out  # 인증서가 있어도 SNI(model-runtime)와 다른 Host 는 받지 않는다


def test_area_gateway_serves_health_and_metrics_on_the_plain_monitor_port_only(box: Sandbox) -> None:
    port = area_gateway.MONITOR_PORT
    for path, status in (("/metrics", "200"), ("/healthz", "200"), ("/readyz", "200"), ("/v1/results", "404")):
        code, out = curl_in_client(box, "-o", "/dev/null", "-w", "%{http_code}", f"http://survey-service:{port}{path}")
        assert code == 0 and out.strip() == status, (path, out)
    code, out = curl_in_client(box, f"http://survey-service:{port}/metrics")
    assert "sandbox_up 1" in out
    code, out = curl_in_client(box, "-H", 'X-Forwarded-Client-Cert: Hash=00;Subject="CN=kiosk-99"', f"http://survey-service:{port}/healthz")
    assert code == 0 and "kiosk-99" not in out and "xfcc=" in out  # 감시 포트에서도 위조 머리글은 지운다(본문의 xfcc 가 비어 있다)
    # 입구는 이 포트를 열지 않는다(밖에서 상태 경로는 404)
    assert client(box).get("/metrics").status == 404


# ---------------------------------------------------------------- 감시


def test_area_metrics_are_scraped_and_watchdog_fires(box: Sandbox) -> None:
    def up() -> bool:
        out = box.exec("prometheus", "wget", "-qO-", "http://127.0.0.1:9090/api/v1/query?query=up%7Bjob%3D%22openit-areas%22%7D").stdout
        values = {row["metric"]["instance"]: row["value"][1] for row in json.loads(out)["data"]["result"]}
        return all(values.get(f"{name}:{area_gateway.MONITOR_PORT}") == "1" for name in ("survey-service", "model-runtime", "admin-console"))

    box.wait("Prometheus 가 영역 게이트웨이의 평문 감시 포트로 영역 /metrics 를 읽", up, seconds=240)

    def watchdog() -> bool:
        alerts = json.loads(box.exec("alertmanager", "wget", "-qO-", "http://127.0.0.1:9093/api/v2/alerts").stdout)
        return any(alert["labels"]["alertname"] == "Watchdog" for alert in alerts)

    box.wait("Alertmanager 가 Watchdog 를 받", watchdog, seconds=240)


# ---------------------------------------------------------------- 배포 명령


def test_bootstrap_twice_changes_nothing(box: Sandbox) -> None:
    before = {service: box.compose("ps", "-q", service).stdout.strip() for service in ("envoy", "ingress-acme", "keycloak", "oauth2-proxy", "step-ca")}
    assert all(before.values())
    box.deploy("bootstrap")
    after = {service: box.compose("ps", "-q", service).stdout.strip() for service in before}
    assert after == before  # 멱등: 같은 입력이면 컨테이너를 다시 만들지 않는다
    status = box.deploy("ca", "status", check=False)
    assert status.returncode == 0, status.stdout[-1500:]


def test_revoking_a_device_takes_effect_after_up(box: Sandbox) -> None:
    assert client(box, "kiosk-01").get("/v1/sessions/s1/state").status == 200
    box.write_allowlist(["kiosk-02"])  # 등록·회전·폐기는 허용 목록을 바꾸는 것이다
    box.deploy("up")
    box.wait("폐기가 입구에 반영", lambda: client(box, "kiosk-01").get("/v1/sessions/s1/state").status == 403, seconds=60, interval=2)
    assert client(box, "kiosk-02").get("/v1/sessions/s1/state").status == 200
    box.write_allowlist(["kiosk-01"])
    box.deploy("up")
    box.wait("복구가 입구에 반영", lambda: client(box, "kiosk-01").get("/v1/sessions/s1/state").status == 200, seconds=60, interval=2)


def test_new_machine_caller_is_added_by_identity_sync(box: Sandbox) -> None:
    """realm 은 처음 기동 때만 가져오므로, 호출자를 더한 뒤에는 `./deploy identity sync` 가 반영한다. 사람 토큰의 역할 제한은 그대로다."""
    path = box.state / "machine-callers.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    table["tokens"].append({"client": "lab2", "roles": ["case-reader"], "client_secret_file": "/run/secrets/unused-lab2"})
    path.write_text(json.dumps(table), encoding="utf-8")
    up = box.deploy("up")
    assert "identity sync" in up.stdout
    box.deploy("identity", "sync")
    header, claims = decode_jwt(machine_token(box, "lab2"))
    assert header["typ"] == "at+jwt" and claims["realm_access"]["roles"] == ["case-reader"]
    _, final = login(box, "staff-1")
    _, human = decode_jwt(final.lines()["authorization"].removeprefix("Bearer "))
    assert human["realm_access"]["roles"] == ["staff"]  # 동기화 뒤에도 기본 역할이 토큰에 실리지 않는다


def leaf_serial(box: Sandbox) -> str:
    context = ssl.create_default_context(cafile=str(box.deploy_dir / "pki" / "trust-bundle.pem"))
    import socket

    with socket.create_connection(("127.0.0.1", box.published_port("ingress-acme", 8443)), timeout=10) as raw, context.wrap_socket(raw, server_hostname=HOST) as tls:
        der = tls.getpeercert(binary_form=True)
    assert der
    from cryptography import x509

    return format(x509.load_der_x509_certificate(der).serial_number, "x")


def started_at(box: Sandbox, service: str) -> str:
    container = box.compose("ps", "-q", service).stdout.strip()
    return box.docker(["inspect", "--format", "{{.State.StartedAt}}", container]).stdout.strip()


def test_ingress_certificate_is_renewed_and_envoy_reloads_it_without_restart(box: Sandbox) -> None:
    first, envoy_started = leaf_serial(box), started_at(box, "envoy")
    box.wait("입구 인증서가 갱신", lambda: leaf_serial(box) != first, seconds=420, interval=10)  # 수명 5분, 수명의 1/3 이 남으면 갱신(ADR 0014)
    assert started_at(box, "envoy") == envoy_started  # 다시 시작하지 않았다
    assert client(box, "kiosk-01").get("/v1/sessions/s1/state").status == 200  # 갱신된 입구·영역 사이 클라이언트 인증서로 계속 통한다


def test_root_rotation_keeps_both_roots_until_leaves_are_renewed(box: Sandbox) -> None:
    bundle = box.deploy_dir / "pki" / "trust-bundle.pem"
    assert bundle.read_text(encoding="utf-8").count("BEGIN CERTIFICATE") == 1
    box.deploy("ca", "rotate-root")
    assert bundle.read_text(encoding="utf-8").count("BEGIN CERTIFICATE") == 2  # 새 루트와 이전 루트를 함께 믿는다
    assert list((box.deploy_dir / "pki" / "trust.d").glob("old-root-*.crt"))
    # 영역 게이트웨이도 새 신뢰 목록을 읽게 다시 만든다(신뢰 목록을 시작할 때 읽는 것과 같다)
    box.recreate_gateways()
    # 왜 '이른 2단계가 거절되는가'를 단언하지 않나: 수명 5분 설치에서는 입구 에이전트가 다시 만들어지며 곧바로 새 루트의 인증서로 갱신해 경주가 된다(platform ADR 0006)
    assert box.deploy("ca", "rotate-root", "--finish", check=False).returncode == 2  # 배포 확인 없이는 빼지 않는다

    def finished() -> bool:
        return box.deploy("ca", "rotate-root", "--finish", "--distributed", check=False).returncode == 0

    box.wait("이전 루트를 뺄 수 있", finished, seconds=600, interval=20)
    assert bundle.read_text(encoding="utf-8").count("BEGIN CERTIFICATE") == 1
    box.recreate_gateways()
    box.wait("교체 뒤에도 입구가 영역 서비스에 닿", lambda: client(box, "kiosk-01").get("/v1/sessions/s1/state").status == 200, seconds=120, interval=5)
    status = box.deploy("ca", "status", check=False)
    assert status.returncode == 0, status.stdout[-1500:]


def test_platform_files_hold_no_secret_values(box: Sandbox) -> None:
    """생성 파일과 설정에 비밀 값이 없다(D84). 비밀 파일의 내용이 생성 파일에 한 줄도 나오지 않는다."""
    secrets_dir = box.deploy_dir / "secrets"
    values = [p.read_text(encoding="utf-8").strip() for p in secrets_dir.rglob("*") if p.is_file()]
    assert values and all(len(value) >= 16 for value in values)
    generated = [p for p in (box.deploy_dir / "generated").rglob("*") if p.is_file()]
    assert generated
    for path in generated:
        text = path.read_text(encoding="utf-8")
        assert not [value for value in values if value in text], path.name
    assert re.search(r"\$\{[A-Z_]+\}", (box.deploy_dir / "generated" / "identity" / "openit-realm.json").read_text(encoding="utf-8"))
