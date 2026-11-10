"""입구 인증서 에이전트(ingress-acme, Caddy) 설정 생성(ADR 0014, platform ADR 0002).

에이전트는 ACME(RFC 8555) 클라이언트이고 인증서를 받고 갱신한다. 입구(Envoy)가 같은 인증서 폴더를 읽는다.
- private: 입구 이름의 인증서를 사설 CA(step-ca)에서 받는다.
- acme-public: 공인 ACME CA 에서 받는다(공개 도메인).
- organization: 조직이 준 인증서를 쓰므로 입구 이름은 받지 않는다.
어느 방식이든 입구가 영역 서비스에 보일 클라이언트 인증서(이름 gateway)는 사설 CA 에서 받는다(영역 사이 mTLS, 계약 securitySchemes area_mtls).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from .gateway import ACME_STORE, TRUST_LIST
from .settings import GATEWAY_NAME, PlatformSettings

DUMMY_HTTPS_PORT = 8444  # 왜: Caddy 는 인증서를 받으려면 사이트가 있어야 한다. 사이트는 아무것도 서비스하지 않는 자리이고 Envoy 의 포트와 겹치지 않게 둔다


def acme_issuer_key(directory_url: str) -> str:
    """Caddy(certmagic)가 인증서를 두는 폴더의 발급자 이름. 디렉터리 URL 에서 호스트와 경로를 이어 `/`·`:` 를 `-` 로 바꾼 값이다."""
    parts = urlsplit(directory_url)
    return f"{parts.netloc}{parts.path}".replace("/", "-").replace(":", "-")


def render_caddyfile(settings: PlatformSettings) -> str:
    internal = f"""\tissuer acme {{
\t\t\tdir {settings.internal_acme_directory_url}
\t\t\t# 신뢰 목록의 루트로 step-ca 의 서버 인증서를 검증한다(검증을 끄지 않는다)
\t\t\ttrusted_roots {TRUST_LIST}
\t\t\tdisable_tlsalpn_challenge
\t\t}}"""
    public = f"""\tissuer acme {{
\t\t\tdir {settings.acme_directory_url}
\t\t\tdisable_tlsalpn_challenge
\t\t}}"""
    blocks = []
    if settings.ingress_mode == "private":
        blocks.append((", ".join(settings.public_names), internal))
    elif settings.ingress_mode == "acme-public":
        blocks.append((", ".join(settings.public_names), public))
    blocks.append((GATEWAY_NAME, internal))
    sites = "\n\n".join(f"{names} {{\n\ttls {{\n\t{issuer}\n\t}}\n\trespond 404\n}}" for names, issuer in blocks)
    return f"""# 입구 인증서 에이전트(ingress-acme). ./deploy 가 platform/src/openit_platform/ingress.py 로 만든다. 손으로 고치지 않는다.
{{
	admin off
	# 왜 1m: 갱신 점검 주기의 기본은 10분이다. 실패한 갱신을 1분마다 다시 시도해 수명이 짧은 인증서의 여유(수명의 1/3)를 덜 쓰게 한다(ADR 0014). 측정하지 않았다
	renew_interval 1m
	skip_install_trust
	https_port {DUMMY_HTTPS_PORT}
	storage file_system {ACME_STORE}
}}

{sites}
"""
