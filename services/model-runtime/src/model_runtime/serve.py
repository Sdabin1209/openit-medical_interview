"""서버 진입점: 영역 사이 mTLS 서버(계약 area_mtls)와 컨테이너 건강 확인용 루프백 서버를 한 프로세스에서 띄운다.

- 영역 사이: `OPENIT_LISTEN_PORT` 에서 TLS 로 받고 클라이언트 인증서를 요구한다(사설 루트가 신뢰 앵커, RFC 8705).
- 컨테이너 안: `127.0.0.1:18081` 에서 건강 확인(/healthz, /readyz, /metrics)만 평문으로 받는다. 컨테이너 밖에서는 닿지
않는다.
"""

import asyncio
import logging
import ssl
import sys

import uvicorn
from fastapi import FastAPI

from model_runtime.link.health import health_router
from model_runtime.main import Settings, create_app

# 왜 18081: 컨테이너 HEALTHCHECK 가 mTLS 인증서 없이 /healthz 를 보게 하는 루프백 포트다. 관례 포트와 겹치지 않게 골랐고
# 측정한 값이 아니다
LOOPBACK_HEALTH_PORT = 18081


async def serve(settings: Settings) -> None:
    """두 서버를 함께 돌린다. 하나가 끝나면 다른 하나도 끝낸다(컨테이너 종료 신호 SIGTERM 에 함께 멈추게)."""
    app = create_app(settings)
    service, checks, registry = app.state.health
    health_app = FastAPI(title=f"{service.value}-health")
    health_app.include_router(health_router(service, checks, registry))
    main_server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="0.0.0.0",  # noqa: S104 - 컨테이너 안에서 영역 네트워크로 받는다. 접근은 mTLS 와 토큰이 막는다
            port=settings.listen_port,
            ssl_certfile=str(settings.tls_certificate_file),
            ssl_keyfile=str(settings.tls_private_key_file),
            ssl_ca_certs=str(settings.root_certificate_file),
            ssl_cert_reqs=ssl.CERT_REQUIRED,
            log_config=None,
        )
    )
    health_server = uvicorn.Server(
        uvicorn.Config(health_app, host="127.0.0.1", port=LOOPBACK_HEALTH_PORT, log_config=None)
    )
    tasks = [asyncio.ensure_future(main_server.serve()), asyncio.ensure_future(health_server.serve())]

    def stop_both(_: object) -> None:
        main_server.should_exit = health_server.should_exit = True

    for task in tasks:
        task.add_done_callback(stop_both)
    await asyncio.gather(*tasks)


def main() -> int:
    """환경 변수로 설정을 읽어 서버를 띄운다."""
    settings = Settings()  # pyright: ignore[reportCallIssue]
    logging.basicConfig(
        stream=sys.stdout, level=settings.log_level.value, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    if settings.listen_port == LOOPBACK_HEALTH_PORT:
        logging.getLogger("model_runtime").error("OPENIT_LISTEN_PORT 가 루프백 건강 확인 포트와 같다")
        return 2
    asyncio.run(serve(settings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
