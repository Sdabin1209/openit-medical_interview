"""link_model_client 의 기계 토큰 받기: OAuth 2.0 client credentials(RFC 6749 4.4)로 JWT 접근 토큰(RFC 9068)을 받는다.

클라이언트 ID 는 machine-<호출자 이름>, 비밀은 파일(NAME_FILE, D84)이다. 토큰 엔드포인트는 발급자 디스커버리 문서
(OpenID Connect Discovery 1.0 4)의 token_endpoint 에서 얻는다. 호출은 호출한 쪽이 넘긴 httpx 클라이언트로 하며
운영에서는 영역 게이트웨이의 CONNECT 터널(OPENIT_EGRESS_PROXY)을 지난다(D128).
"""

import asyncio
import base64
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote_plus

import httpx

# 왜 5초: JWKS 호출과 같은 선택이다. 발급자 한 곳에 오래 매이지 않으려는 것이며 측정하지 않았다(ADR 0006)
TOKEN_TIMEOUT_SECONDS = 5.0
# 왜 30초: 만료 직전 토큰을 보내 거절당하지 않게 하는 여유다. 측정하지 않았고 수명이 짧으면 수명의 절반으로 줄인다
RENEW_BEFORE_SECONDS = 30


class TokenError(RuntimeError):
    """토큰을 받지 못했다. 메시지에 비밀과 토큰 값을 넣지 않는다."""


class MachineTokenSource:
    """기계 토큰을 받아 만료 전까지 쓰고, 만료가 가까워지면 다시 받는다."""

    def __init__(
        self,
        issuer: str,
        client_id: str,
        secret_file: str,
        *,
        client: httpx.AsyncClient,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._client_id = client_id
        self._secret_file = secret_file
        self._client = client
        self._clock = clock
        self._endpoint: str | None = None
        self._token: str | None = None
        self._renew_at = 0.0
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        """받은 토큰을 버린다(받는 쪽이 401 로 거절했을 때). 다음 호출이 새로 받는다."""
        self._token = None

    async def token(self) -> str:
        """쓸 수 있는 토큰. 왜 잠그나: 만료 때 동시 호출이 발급자를 여러 번 두드리지 않게 한다."""
        async with self._lock:
            if self._token is None or self._clock() >= self._renew_at:
                await self._fetch()
            assert self._token is not None  # noqa: S101  (_fetch 가 성공하면 채운다)
            return self._token

    async def _token_endpoint(self) -> str:
        if self._endpoint is None:
            response = await self._client.get(
                f"{self._issuer}/.well-known/openid-configuration", timeout=TOKEN_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            self._endpoint = str(response.json()["token_endpoint"])
        return self._endpoint

    async def _fetch(self) -> None:
        try:
            # 왜 매번 읽나: 비밀 파일이 바뀌어도(회전) 다시 시작하지 않고 따른다
            secret = Path(self._secret_file).read_text(encoding="utf-8").rstrip("\r\n")
            # 왜 이 인코딩: RFC 6749 2.3.1 은 기본 인증을 서버가 지원하게 하고 ID·비밀을 먼저 폼 인코딩하라고 정한다
            basic = base64.b64encode(f"{quote_plus(self._client_id)}:{quote_plus(secret)}".encode()).decode()
            response = await self._client.post(
                await self._token_endpoint(),
                data={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {basic}"},
                timeout=TOKEN_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
            token = str(body["access_token"])
            lifetime = float(body["expires_in"])
        except (httpx.HTTPError, OSError, KeyError, ValueError, TypeError) as error:
            self._token = None
            raise TokenError("기계 토큰을 받지 못했다") from error
        self._token = token
        self._renew_at = self._clock() + lifetime - min(RENEW_BEFORE_SECONDS, lifetime / 2)
