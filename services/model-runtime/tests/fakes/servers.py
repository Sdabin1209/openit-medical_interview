"""시험용 서버를 실제 TCP 포트(고정 포트 없음)에서 띄운다. 레지스트리 클라이언트(oras, requests)와 평가 도구는 실제
소켓으로 부른다."""

import asyncio
import ssl
import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn

from fakes.pki import Pki


class _SignalingServer(uvicorn.Server):
    """시작을 마치면 신호를 내는 uvicorn 서버. 왜: 간격을 두고 started 를 들여다보지 않고 시작 신호로 기다린다."""

    def __init__(self, config: uvicorn.Config) -> None:
        super().__init__(config)
        self.listening = threading.Event()

    async def startup(self, sockets: list[Any] | None = None) -> None:
        await super().startup(sockets)
        self.listening.set()


START_LIMIT_SECONDS = 30  # 측정하지 않았다. 시작이 멈춘 경우에만 닿는 상한


@dataclass(frozen=True)
class Running:
    url: str


@contextmanager
def run_server(app: Any, pki: Pki | None = None, require_client_cert: bool = False) -> Generator[Running]:  # noqa: ANN401
    """app 을 127.0.0.1 의 빈 포트에 띄운다. pki 가 있으면 TLS 로 띄운다."""
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=0,
        log_level="warning",
        ssl_certfile=str(pki.server_cert) if pki else None,
        ssl_keyfile=str(pki.server_key) if pki else None,
        ssl_ca_certs=str(pki.root) if pki and require_client_cert else None,
        ssl_cert_reqs=ssl.CERT_REQUIRED if pki and require_client_cert else ssl.CERT_NONE,
    )
    server = _SignalingServer(config)

    def serve() -> None:
        try:
            asyncio.run(server.serve())
        finally:
            server.listening.set()  # 시작에 실패해 스레드가 끝나도 기다림이 풀린다(아래에서 started 로 가른다)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    # 상한은 멈춘 서버를 영원히 기다리지 않기 위한 것이고 판정 시간이 아니다
    if not server.listening.wait(START_LIMIT_SECONDS) or not server.started:
        raise RuntimeError("시험 서버가 시작하지 않았다")
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield Running(f"{'https' if pki else 'http'}://localhost:{port}")
    finally:
        # 왜 force_exit: 클라이언트의 keep-alive 연결이 남아 있으면 정상 종료가 연결이 닫히기를 기다린다
        server.should_exit = server.force_exit = True
        thread.join(timeout=10)


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path
