"""영역 게이트웨이(Caddy) 템플릿: 환경 변수 이름과 고정 값이 코드의 값과 같고, 규칙(mTLS, XFCC, 평문 감시 포트)이 파일에 있다."""

import re
from pathlib import Path

from openit_platform import area_gateway, gateway, ingress

TEMPLATE = Path(__file__).resolve().parents[2] / "caddy" / area_gateway.CADDYFILE


def _text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_template_reads_exactly_the_documented_environment() -> None:
    assert set(re.findall(r"\{\$([A-Z_]+)\}", _text())) == set(area_gateway.ENV_NAMES)


def test_template_uses_the_shared_constants() -> None:
    text = _text()
    assert f"storage file_system {area_gateway.AREA_CERTS}" in text
    assert f"pem_file {gateway.TRUST_LIST}" in text and f"trusted_roots {gateway.TRUST_LIST}" in text
    assert f"http://:{area_gateway.MONITOR_PORT} {{" in text
    assert f'== "{area_gateway.INGRESS_CLIENT_NAME}"' in text and f"-{area_gateway.FORWARDED_HEADER}" in text
    assert f"@monitor path {' '.join(area_gateway.MONITOR_PATHS)}" in text


def test_clients_must_present_a_certificate_and_xfcc_is_dropped_unless_from_ingress() -> None:
    text = _text()
    assert "mode require_and_verify" in text and "verify_if_given" not in text
    # 입구의 인증서가 아닌 요청은 XFCC 를 지운다(조건 부정). 감시 포트에서도 지운다
    assert text.count(f"request_header @not_ingress -{area_gateway.FORWARDED_HEADER}") == 1
    assert text.count(f"request_header -{area_gateway.FORWARDED_HEADER}") == 1
    assert "insecure" not in text and "tls internal" not in text  # 검증을 끄지 않고 사설 CA 의 ACME 로만 받는다


def test_certificate_paths_follow_the_ingress_agent_layout() -> None:
    url = "https://step-ca:9000/acme/acme/directory"
    cert, key = area_gateway.certificate_paths("survey-service", url)
    assert cert == f"/area-certs/certificates/{ingress.acme_issuer_key(url)}/survey-service/survey-service.crt" and key.endswith("/survey-service.key")
    command = area_gateway.healthcheck_command("survey-service", url)
    assert command == f"test -s {cert} && test -s {key}"
