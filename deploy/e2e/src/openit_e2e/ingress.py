"""입구(Envoy)로 요청하는 클라이언트들: 키오스크(기기 인증서, mTLS), 사람(OIDC 로그인 쿠키), 기계 호출자(client credentials).

D123: 드라이버는 운영자 PC 역할(호스트)에서 입구가 호스트에 게시한 포트로만 접속한다. 내부 서비스 포트를 직접 부르지 않는다.
발급자 주소(https://openit.internal:8443/...)는 호스트에서 풀리지 않으므로 전송 계층에서 접속 대상만 127.0.0.1:<게시된 포트>로 바꾸고,
TLS 이름(SNI)과 인증서 검증, Host 머리글은 입구의 공개 이름 그대로 둔다(검증을 끄지 않는다).
"""

from __future__ import annotations

import html
import re
import ssl
from pathlib import Path

import httpx

from .contract import StepFailure

PUBLIC_HOST = "openit.internal"  # deploy/env.example 의 OPENIT_PUBLIC_NAMES 기본값(첫 이름)
PUBLIC_PORT = 8443  # 발급자 주소의 포트(OPENIT_LISTEN_PORT 기본값). 호스트에 게시된 포트는 Docker 가 배정한다
# 왜 65초: 계약 KioskRequestLimitSeconds(60초, D125)는 키오스크가 실패로 보는 상한이다. 서버·게이트웨이의 상한(55+1초)이 먼저 끝나 상태 코드로 드러나게 클라이언트는 조금 더 기다린다
REQUEST_TIMEOUT = httpx.Timeout(65.0)
REALM_PATH = "/realms/openit"
TOKEN_PATH = f"{REALM_PATH}/protocol/openid-connect/token"


class _IngressTransport(httpx.BaseTransport):
    def __init__(self, port: int, context: ssl.SSLContext) -> None:
        self._port = port
        self._inner = httpx.HTTPTransport(verify=context)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        target = request.url.copy_with(host="127.0.0.1", port=self._port)
        extensions = {**request.extensions, "sni_hostname": request.url.host}
        forwarded = httpx.Request(request.method, target, headers=request.headers, stream=request.stream, extensions=extensions)
        return self._inner.handle_request(forwarded)

    def close(self) -> None:
        self._inner.close()


class Ingress:
    def __init__(self, port: int, trust_bundle: Path) -> None:
        self.port = port
        self.trust_bundle = trust_bundle

    def client(self, device: tuple[Path, Path] | None = None) -> httpx.Client:
        """입구에 요청하는 클라이언트. device 가 있으면 기기 인증서(mTLS)로 접속한다. 리디렉션은 따라가지 않는다(로그인에서만 명시한다)."""
        context = ssl.create_default_context(cafile=str(self.trust_bundle))
        if device:
            context.load_cert_chain(str(device[0]), str(device[1]))
        return httpx.Client(
            base_url=f"https://{PUBLIC_HOST}:{PUBLIC_PORT}",
            transport=_IngressTransport(self.port, context),
            timeout=REQUEST_TIMEOUT,
            follow_redirects=False,
        )

    def login(self, username: str, password: str) -> httpx.Client:
        """브라우저처럼 로그인한다: 화면 경로 -> oauth2-proxy -> Keycloak 로그인 양식 -> 되돌아옴. 쿠키 세션을 가진 클라이언트를 돌려준다(역할은 계정에 부여된 것)."""
        session = self.client()
        page = session.get("/console/", headers={"Accept": "text/html"}, follow_redirects=True)
        match = re.search(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"', page.text) or re.search(
            r'<form[^>]*action="([^"]+)"[^>]*id="kc-form-login"', page.text
        )
        if page.status_code != 200 or not match:
            raise StepFailure(f"{username}: 로그인 양식을 받지 못했다(상태 {page.status_code})")
        done = session.post(
            html.unescape(match.group(1)), data={"username": username, "password": password, "credentialId": ""}, follow_redirects=True
        )
        if done.status_code != 200 or "kc-form-login" in done.text:
            raise StepFailure(f"{username}: 로그인 뒤 화면 경로가 열리지 않았다(상태 {done.status_code})")
        return session

    def machine_token(self, caller: str, secret: str) -> str:
        """기계 호출자의 접근 토큰(OAuth 2.0 client credentials, RFC 6749 4.4). 클라이언트 ID 는 machine-<호출자>다(계약 MachineOidcClientId)."""
        with self.client() as anonymous:
            response = anonymous.post(
                TOKEN_PATH, data={"grant_type": "client_credentials", "client_id": f"machine-{caller}", "client_secret": secret}
            )
        if response.status_code != 200:
            raise StepFailure(f"기계 호출자 {caller}: 토큰을 받지 못했다(상태 {response.status_code})")
        return str(response.json()["access_token"])

    def machine_client(self, caller: str, secret: str) -> httpx.Client:
        client = self.client()
        client.headers["Authorization"] = f"Bearer {self.machine_token(caller, secret)}"
        return client
