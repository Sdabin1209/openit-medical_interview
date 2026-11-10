"""시험용 서버를 실제 TCP 포트(고정 포트 없음)에서 띄운다. 레지스트리 클라이언트(oras, requests)와 평가 도구는 실제
소켓으로 부른다."""

import asyncio
import contextlib
import socket
import socketserver
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


@dataclass(frozen=True)
class Tunnel:
    url: str
    targets: list[str]  # CONNECT 으로 요청받은 `이름:포트` 들(접속 이름이 그대로 오는지 본다)


@contextmanager
def connect_tunnel(destination_port: int) -> Generator[Tunnel]:
    """HTTP CONNECT 터널(RFC 9110 9.3.6). 어떤 `이름:포트` 요청도 127.0.0.1:destination_port 로 잇는다.

    왜 둔다: 점·콜론 없는 이름(`registry`)은 포트 없이 443 으로만 닿는데 시험이 443 을 열 수 없다.
    영역의 나가는 호출이 쓰는 표준 길(게이트웨이 CONNECT 터널, D128)로 접속하면 TLS 는 원래 이름으로 확인된다.
    """
    targets: list[str] = []

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            request_line = self.rfile.readline().decode("latin-1")
            while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                pass  # 머리글은 쓰지 않는다
            method, target, _ = request_line.split(" ", 2)
            if method != "CONNECT":
                self.wfile.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                return
            targets.append(target)
            upstream = socket.create_connection(("127.0.0.1", destination_port))
            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.wfile.flush()
            forward = threading.Thread(target=_pipe, args=(self.request, upstream), daemon=True)
            forward.start()
            _pipe(upstream, self.request)
            forward.join()
            upstream.close()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

    server = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Tunnel(f"http://127.0.0.1:{server.server_address[1]}", targets)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)


def _pipe(source: socket.socket, sink: socket.socket) -> None:
    """source 에서 읽은 바이트를 끝날 때까지 sink 로 보낸다."""
    try:
        while data := source.recv(65536):
            sink.sendall(data)
    except OSError:
        pass
    finally:
        with contextlib.suppress(OSError):
            sink.shutdown(socket.SHUT_WR)
