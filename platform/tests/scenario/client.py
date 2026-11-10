"""시험용 HTTPS 클라이언트. 입구가 게시한 호스트 포트로 접속하되 이름(SNI)은 입구의 공개 이름으로 보낸다.

왜 직접 만든 작은 클라이언트인가: 발급자 주소(https://<이름>:8443/...)로 오는 리디렉션을 따라가면서도 접속은 게시된 포트로 해야 하고,
클라이언트 인증서와 쿠키와 리디렉션을 한 줄씩 보고 싶다. 표준 라이브러리(ssl, http.client)만 쓴다.
"""

from __future__ import annotations

import html
import http.client
import re
import ssl
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urljoin, urlsplit


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: str
    location: str | None = None

    def lines(self) -> dict[str, str]:
        """에코 상류의 본문(key=value 줄)을 사전으로."""
        return dict(line.split("=", 1) for line in self.body.splitlines() if "=" in line)


class _Connection(http.client.HTTPSConnection):
    def __init__(self, port: int, context: ssl.SSLContext, server_name: str) -> None:
        super().__init__("127.0.0.1", port, timeout=20, context=context)
        self._server_name = server_name

    def connect(self) -> None:
        http.client.HTTPConnection.connect(self)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self._server_name)  # type: ignore[attr-defined]


@dataclass
class Client:
    port: int
    server_name: str
    trust: Path
    cert: tuple[Path, Path] | None = None
    cookies: dict[str, str] = field(default_factory=dict)

    def _context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(cafile=str(self.trust))
        if self.cert:
            context.load_cert_chain(str(self.cert[0]), str(self.cert[1]))
        return context

    def request(self, method: str, url: str, *, headers: dict[str, str] | None = None, body: str | None = None) -> Response:
        parts = urlsplit(url)
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        sent = {"Host": f"{self.server_name}:8443", "Connection": "close", **(headers or {})}
        if self.cookies:
            sent["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        if body is not None:
            sent.setdefault("Content-Type", "application/x-www-form-urlencoded")
        connection = _Connection(self.port, self._context(), self.server_name)
        try:
            connection.request(method, path or "/", body=body, headers=sent)
            raw = connection.getresponse()
            text = raw.read().decode("utf-8", errors="replace")
            response = Response(raw.status, {k.lower(): v for k, v in raw.getheaders()}, text, raw.getheader("location"))
            for header in raw.msg.get_all("set-cookie") or []:
                jar: SimpleCookie = SimpleCookie()
                jar.load(header)
                for name, morsel in jar.items():
                    if morsel.value == "" or morsel["max-age"] == "0":
                        self.cookies.pop(name, None)
                    else:
                        self.cookies[name] = morsel.value
            return response
        finally:
            connection.close()

    def get(self, path: str, **kwargs: object) -> Response:
        return self.request("GET", path, **kwargs)  # type: ignore[arg-type]

    def follow(self, response: Response, url: str, limit: int = 12) -> Response:
        """리디렉션을 따라간다(접속은 항상 게시된 포트로). 마지막 응답."""
        for _ in range(limit):
            if response.status not in (301, 302, 303, 307) or not response.location:
                return response
            url = urljoin(url, response.location)
            response = self.request("GET", url)
        raise AssertionError("리디렉션이 너무 많다")


def login_form(page: str) -> tuple[str, str]:
    """Keycloak 로그인 화면(HTML)에서 입력 양식의 주소를 읽는다."""
    match = re.search(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"', page) or re.search(r'<form[^>]*action="([^"]+)"[^>]*id="kc-form-login"', page)
    assert match, "로그인 양식이 없다"
    return html.unescape(match.group(1)), page
