"""인증서 갱신과 루트 교체: 우리가 만드는 설정이 갱신을 가능하게 하는지 생성물로 본다(platform ADR 0008).

step-ca·Caddy·Envoy 가 실제로 갱신하는 시간은 재지 않는다(외부 제품의 동작이고 실제 시간에 기대 시험이 시스템 부하에 흔들린다).
여기서는 그 제품들이 갱신하도록 우리가 건네는 값(수명, 갱신 점검 주기, SDS 파일 감시, 신뢰 목록)만 본다.
"""

import re
from pathlib import Path

import pytest
import yaml
from cryptography import x509

from openit_platform import gateway, ingress, pki
from openit_platform.contract.models import DeviceAllowlist

from .helpers import exposure, platform_settings, route
from .test_pki import _make, write

# 왜 1/3: Caddy(certmagic)는 수명의 1/3 이 남으면 갱신한다(RenewalWindowRatio 기본값, 리포 ADR 0014 가 채택)
RENEWAL_WINDOW_RATIO = 1 / 3
CA_MIN_LEAF_SECONDS = 5 * 60  # step-ca 의 minTLSCertDuration 하한(제품의 제약). 설정 생성기가 같은 값을 건넨다(아래에서 확인)


def _renew_interval_seconds(caddyfile: str) -> int:
    match = re.search(r"^\s*renew_interval (\d+)([sm])$", caddyfile, re.MULTILINE)
    assert match, "renew_interval 이 분·초 단위로 있어야 한다"
    return int(match.group(1)) * (60 if match.group(2) == "m" else 1)


def _caddyfiles(repo: Path) -> dict[str, str]:
    return {
        "ingress-acme": ingress.render_caddyfile(platform_settings(repo)),
        "area-gateway": (repo / "platform" / "caddy" / "area-gateway.Caddyfile").read_text(encoding="utf-8"),
    }


def test_leaf_lifetime_is_never_shorter_than_the_ca_minimum_and_the_ca_is_told_so(repo: Path) -> None:
    env = pki.parse_env_file(repo / "deploy" / "env.example")
    claims = pki.render_ca_json(pki.ca_settings({**env, "OPENIT_LEAF_LIFETIME": "5m"}))["authority"]["provisioners"][0]["claims"]
    assert claims == {"minTLSCertDuration": "5m", "maxTLSCertDuration": "5m", "defaultTLSCertDuration": "5m"} and pki.MIN_LEAF_MINUTES * 60 == CA_MIN_LEAF_SECONDS
    with pytest.raises(pki.ConfigError, match="OPENIT_LEAF_LIFETIME"):  # step-ca 가 거부할 수명은 설정 단계에서 막는다
        pki.ca_settings({**env, "OPENIT_LEAF_LIFETIME": "4m"})


def test_renewal_check_runs_inside_the_renewal_window_of_the_shortest_allowed_leaf(repo: Path) -> None:
    """가장 짧은 리프(5분)의 갱신 구간(수명의 1/3 = 100초) 안에 점검이 적어도 한 번 들어간다. 입구 에이전트와 영역 게이트웨이 둘 다."""
    window = CA_MIN_LEAF_SECONDS * RENEWAL_WINDOW_RATIO
    for name, text in _caddyfiles(repo).items():
        assert _renew_interval_seconds(text) <= window, name


def test_both_envoy_certificates_are_sds_files_that_watch_their_own_folder(repo: Path) -> None:
    """입구 인증서와 영역 사이 클라이언트 인증서 둘 다 파일 SDS 이고, 갱신된 파일이 들어오는 폴더를 감시한다. 인라인 인증서는 없다."""
    sds = gateway.build_sds(platform_settings(repo), "ik", "ik2")
    for name, body in sds.items():
        certificate = yaml.safe_load(body)["resources"][0]["tls_certificate"]
        folder = Path(certificate["certificate_chain"]["filename"]).parent.as_posix()
        assert certificate["watched_directory"]["path"] == folder == Path(certificate["private_key"]["filename"]).parent.as_posix(), name
    settings = platform_settings(repo)
    config = gateway.build_envoy(settings, gateway.plan(settings, {}, repo / "contracts", True), DeviceAllowlist(devices=[]), "ik", "ik2")
    text = gateway.render(config)
    assert "tls_certificates:" not in text
    assert text.count("tls_certificate_sds_secret_configs") >= 1


def test_trust_list_is_the_one_file_renewal_and_upstream_checks_read_roots_from(repo: Path) -> None:
    """Caddy 가 step-ca 를, Envoy 가 영역 서비스를 검증할 때 같은 신뢰 목록 파일을 읽는다(그 파일에 두 루트가 들어가는 것은 아래 시험이 본다)."""
    assert f"trusted_roots {gateway.TRUST_LIST}" in _caddyfiles(repo)["ingress-acme"]
    settings = platform_settings(repo)
    plan = gateway.plan(settings, {"survey-service": exposure([route("/v1/results", "HUMAN_OIDC")])}, repo / "contracts", True)
    config = gateway.build_envoy(settings, plan, DeviceAllowlist(devices=[]), "ik", "ik2")
    clusters = [c for c in config["static_resources"]["clusters"] if c["name"].startswith("service_")]
    assert clusters
    for cluster in clusters:
        context = cluster["transport_socket"]["typed_config"]["common_tls_context"]["validation_context"]
        assert context["trusted_ca"] == {"filename": gateway.TRUST_LIST}


def test_root_rotation_bundle_keeps_both_roots_until_the_old_one_is_removed(tmp_path: Path) -> None:
    new_root, _ = _make("New Root", None, ca=True, days=100)
    old_root, _ = _make("Old Root", None, ca=True, days=100)
    own = write(tmp_path, "pki/root_ca.crt", pki.pem_text([new_root]))
    write(tmp_path, "pki/trust.d/old-root-0a1b2c3d.crt", pki.pem_text([old_root]))  # rotate-root 1단계가 두는 파일 이름
    both = x509.load_pem_x509_certificates(pki.build_bundle([own], tmp_path / "pki" / "trust.d").encode())
    assert {c.subject.rfc4514_string() for c in both} == {"CN=New Root", "CN=Old Root"}
    (tmp_path / "pki" / "trust.d" / "old-root-0a1b2c3d.crt").unlink()  # 2단계가 이전 루트를 뺀다
    only = x509.load_pem_x509_certificates(pki.build_bundle([own], tmp_path / "pki" / "trust.d").encode())
    assert [c.subject.rfc4514_string() for c in only] == ["CN=New Root"]
