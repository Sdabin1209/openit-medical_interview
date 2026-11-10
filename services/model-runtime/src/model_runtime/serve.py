"""서버 진입점: 영역 안 평문 HTTP 서버(ADR 0005).

TLS 는 영역 게이트웨이가 끝낸다(계약 9.0.0, survey-service-006·model-runtime-003 7). 이 서비스는 영역 전용 내부 네트워크에서
`OPENIT_LISTEN_PORT` 를 평문으로 듣고 게이트웨이만 닿는다. 컨테이너 HEALTHCHECK 도 같은 포트의 /healthz 를 본다.
"""

import logging
import sys

import uvicorn

from model_runtime.main import Settings, create_app


def main() -> int:
    """환경 변수로 설정을 읽어 서버를 띄운다."""
    settings = Settings()  # pyright: ignore[reportCallIssue]
    logging.basicConfig(
        stream=sys.stdout, level=settings.log_level.value, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    uvicorn.run(
        create_app(settings),
        host="0.0.0.0",  # noqa: S104 - 컨테이너 안에서 영역 내부 네트워크로 받는다. 그 네트워크에는 영역 게이트웨이만 닿는다
        port=settings.listen_port,
        log_config=None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
