"""영역 게이트웨이(Caddy)의 고정 값과 건강 확인(platform ADR 0007, 계약 9.0.0 의 결정 (a)).

게이트웨이 설정 자체는 `platform/caddy/area-gateway.Caddyfile` 한 파일이다(환경 변수로 파라미터화한 템플릿이라 생성하지 않는다).
이 모듈은 그 파일과 감시·deploy 가 같은 값을 쓰게 하는 이름과 경로를 한 곳에 둔다. 시험이 템플릿 안의 값과 이 값이 같은지 본다.
"""

from __future__ import annotations

from .gateway import TRUST_LIST
from .ingress import acme_issuer_key

AREA_CERTS = "/area-certs"  # 영역 안 공유 tmpfs 볼륨의 마운트 경로. 게이트웨이가 쓰고 서비스는 읽기 전용으로 마운트한다
# 왜 9100: 영역 안 감시용 평문 포트다. 계약에 없는 platform 내부 값이라 환경 입력으로 받지 않고 고정한다(영역 사이 값이 아니다).
# Prometheus 계열 exporter 가 쓰는 포트 대역(9100~)이고 TLS 포트(OPENIT_SERVICE_PORT 기본 8443)·ACME 의 80 번과 겹치지 않는다. 측정한 값이 아니다(platform ADR 0007)
MONITOR_PORT = 9100
MONITOR_PATHS = ("/healthz", "/readyz", "/metrics")  # 영역 안에서만 닿는 경로(계약 platform.yaml 의 설명, D129)와 같다
INGRESS_CLIENT_NAME = "gateway"  # 입구(Envoy)의 클라이언트 인증서 SAN. 이 이름으로 온 요청에서만 XFCC 를 서비스에 넘긴다(계약 device_mtls)
FORWARDED_HEADER = "X-Forwarded-Client-Cert"
CADDYFILE = "area-gateway.Caddyfile"
ENV_NAMES = ("OPENIT_AREA_NAME", "OPENIT_AREA_UPSTREAM", "OPENIT_SERVICE_PORT", "OPENIT_INTERNAL_ACME_DIRECTORY_URL")  # 템플릿이 읽는 환경 변수 전부


def certificate_paths(area: str, internal_acme_directory_url: str) -> tuple[str, str]:
    """게이트웨이가 받은 인증서와 키의 컨테이너 안 경로(certmagic 의 저장 규칙, 입구 에이전트와 같은 규칙이다). 서비스의 OPENIT_TLS_*_FILE 이 가리킨다."""
    base = f"{AREA_CERTS}/certificates/{acme_issuer_key(internal_acme_directory_url)}/{area}/{area}"
    return f"{base}.crt", f"{base}.key"


def healthcheck_command(area: str, internal_acme_directory_url: str) -> str:
    """게이트웨이의 건강 확인(compose healthcheck 의 CMD-SHELL). 인증서와 키 파일이 생겼는지 본다.

    왜 파일: TLS 를 두드리면 클라이언트 인증서 없는 연결이 거절되고 검증을 끄고 두드릴 수도 없다. 관리 API 는 꺼 둔다(admin off).
    파일이 있다는 것은 사설 CA 에서 ACME 로 인증서를 받았다는 뜻이다. 갱신은 파일이 바뀌는 것으로 이어진다(감시: 입구 인증서와 같은 규칙).
    """
    cert, key = certificate_paths(area, internal_acme_directory_url)
    return f"test -s {cert} && test -s {key}"


__all__ = ["AREA_CERTS", "TRUST_LIST", "certificate_paths", "healthcheck_command"]
