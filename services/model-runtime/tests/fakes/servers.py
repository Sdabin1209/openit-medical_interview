"""시험용 서버를 실제 TCP 포트(고정 포트 없음)에서 띄운다. 레지스트리 클라이언트(oras, requests)와 평가 도구는 실제
소켓으로 부른다."""

import asyncio
import ssl
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn

from fakes.pki import Pki


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
    server = uvicorn.Server(config)
    thread = threading.Thread(target=lambda: asyncio.run(server.serve()), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("시험 서버가 시작하지 않았다")
        time.sleep(0.02)
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
