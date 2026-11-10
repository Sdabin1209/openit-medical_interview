"""감시 설정: 인증서 만료 대상, 영역 지표 대상, 경보 수신처(주소는 설정 파일에 적지 않는다)."""

from pathlib import Path

import yaml

from openit_platform import area_gateway, generate, ingress, monitoring

from .helpers import exposure, platform_settings


def test_tls_targets_label_renewal_kind(repo: Path) -> None:
    rows = yaml.safe_load(monitoring.tls_targets(platform_settings(repo), registry_local=True))
    by_target = {row["targets"][0]: row["labels"]["renewal"] for row in rows}
    assert by_target == {"step-ca:9000": "ca-self", "openit.internal:8443": "acme", "registry:443": "acme"}


def test_organization_certificate_is_labeled_for_the_manual_rule(repo: Path, tmp_path: Path) -> None:
    cfg = platform_settings(
        repo, OPENIT_INGRESS_CERTIFICATE_MODE="organization", OPENIT_INGRESS_CERTIFICATE_FILE=str(tmp_path / "c"), OPENIT_INGRESS_PRIVATE_KEY_FILE=str(tmp_path / "k")
    )
    rows = yaml.safe_load(monitoring.tls_targets(cfg, registry_local=False))
    assert {"targets": ["openit.internal:8443"], "labels": {"renewal": "organization"}} in rows


def test_area_targets_follow_exposures(repo: Path) -> None:
    text = monitoring.area_targets(platform_settings(repo), {"survey-service": exposure([]), "model-runtime": exposure([])})
    assert [row["targets"][0] for row in yaml.safe_load(text)] == ["model-runtime:9100", "survey-service:9100"]  # 영역 게이트웨이의 평문 감시 포트
    assert monitoring.area_targets(platform_settings(repo), {}) == "[]\n"


def test_areas_are_scraped_on_the_plain_monitor_port_not_the_tls_port(repo: Path) -> None:
    """영역 /metrics 는 영역 게이트웨이의 평문 감시 포트(TLS 포트와 별개)로 긁는다. prometheus.yml 의 scheme 도 http 다."""
    cfg = platform_settings(repo)
    rows = yaml.safe_load(monitoring.area_targets(cfg, {"survey-service": exposure([])}))
    assert rows[0]["targets"] == [f"survey-service:{area_gateway.MONITOR_PORT}"] and str(cfg.service_port) not in rows[0]["targets"][0]
    prometheus = yaml.safe_load((repo / "platform" / "monitoring" / "prometheus.yml").read_text(encoding="utf-8"))
    job = next(item for item in prometheus["scrape_configs"] if item["job_name"] == "openit-areas")
    assert job["scheme"] == "http" and "tls_config" not in job


def test_webhook_url_goes_to_a_file_not_the_config(repo: Path) -> None:
    cfg = platform_settings(repo, OPENIT_ALERT_RECEIVER_URL="https://hooks.example.org/secret-token")
    config = monitoring.alertmanager_config(cfg)
    assert "secret-token" not in config and "url_file" in config
    assert monitoring.receiver_target(cfg) == "https://hooks.example.org/secret-token\n"
    parsed = yaml.safe_load(config)
    heartbeat = parsed["route"]["routes"][0]
    assert heartbeat["matchers"] == ['alertname="Watchdog"'] and heartbeat["repeat_interval"] == "1m"


def test_mailto_receiver_needs_smarthost_and_sets_from(repo: Path) -> None:
    cfg = platform_settings(repo, OPENIT_ALERT_RECEIVER_URL="mailto:ops@example.org", OPENIT_ALERT_SMTP_SMARTHOST="smtp.example.org:25")
    parsed = yaml.safe_load(monitoring.alertmanager_config(cfg))
    assert parsed["global"] == {"smtp_smarthost": "smtp.example.org:25", "smtp_from": "openit-alerts@openit.internal"}
    assert parsed["receivers"][0]["email_configs"][0]["to"] == "ops@example.org"


def test_no_receiver_sends_nowhere(repo: Path) -> None:
    parsed = yaml.safe_load(monitoring.alertmanager_config(platform_settings(repo)))
    assert all(len(receiver) == 1 for receiver in parsed["receivers"])  # 이름만 있고 보낼 곳이 없다


def test_acme_issuer_key_follows_certmagic_layout() -> None:
    assert ingress.acme_issuer_key("https://acme-v02.api.letsencrypt.org/directory") == "acme-v02.api.letsencrypt.org-directory"
    assert ingress.acme_issuer_key("https://step-ca:9000/acme/acme/directory") == "step-ca-9000-acme-acme-directory"


def test_caddyfile_uses_private_ca_for_gateway_even_with_public_ingress(repo: Path) -> None:
    cfg = platform_settings(repo, OPENIT_INGRESS_CERTIFICATE_MODE="acme-public")
    text = ingress.render_caddyfile(cfg)
    public_block, gateway_block = text.split("\ngateway {")[0], text.split("\ngateway {")[1]
    assert "acme-v02.api.letsencrypt.org" in public_block and "trusted_roots" not in public_block.split("openit.internal {")[1]
    assert "step-ca:9000" in gateway_block and "trusted_roots" in gateway_block
    organization = platform_settings(repo, OPENIT_INGRESS_CERTIFICATE_MODE="organization", OPENIT_INGRESS_CERTIFICATE_FILE="/x/c", OPENIT_INGRESS_PRIVATE_KEY_FILE="/x/k")
    assert "openit.internal {" not in ingress.render_caddyfile(organization)  # 조직 인증서는 받지 않는다


def test_generate_is_deterministic_and_writes_expected_files(repo: Path, tmp_path: Path) -> None:
    from openit_platform import pki

    env = pki.parse_env_file(repo / "deploy" / "env.example")  # 왜 env.example 만: 설치처의 .env 에 흔들리지 않는다
    env.update(
        OPENIT_EXPOSURES_DIR=str(tmp_path / "exposures"), OPENIT_DEVICE_ALLOWLIST_FILE=str(tmp_path / "allow.json"), OPENIT_MACHINE_TOKENS_FILE=str(tmp_path / "callers.json")
    )
    first = generate.generate(env, repo / "deploy", repo, registry_local=True)
    second = generate.generate(env, repo / "deploy", repo, registry_local=True)
    assert first.files == second.files
    assert set(first.files) == {
        "gateway/envoy.yaml",
        "gateway/sds/ingress_cert.yaml",
        "gateway/sds/gateway_client.yaml",
        "gateway/egress-proxies.json",
        "ingress/Caddyfile",
        "identity/openit-realm.json",
        "monitoring/tls-targets.yml",
        "monitoring/area-targets.yml",
        "monitoring/alertmanager.yml",
        "monitoring/receiver-url",
        "platform.env",
        "compose.platform.yaml",
    }
