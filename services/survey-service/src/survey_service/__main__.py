"""컨테이너 진입점: `python -m survey_service`. 포트는 환경 입력 OPENIT_LISTEN_PORT(SurveyServiceEnv)에서 읽는다."""

import os

import uvicorn

from survey_service.settings import load_env


def main() -> None:
    """환경 입력을 검증하고 앱 팩토리를 띄운다. 로그는 표준 출력(표준 오류)으로 낸다."""
    env = load_env(os.environ)
    level = env.OPENIT_LOG_LEVEL.value.lower() if env.OPENIT_LOG_LEVEL is not None else "info"
    # 호스트 노출은 compose 가 정한다(고정 포트 없음)
    uvicorn.run(
        "survey_service.main:build",
        factory=True,
        host="0.0.0.0",  # noqa: S104  (왜: 컨테이너 안에서 게이트웨이가 들어오는 인터페이스다)
        port=env.OPENIT_LISTEN_PORT.root,
        log_level=level,
    )


if __name__ == "__main__":
    main()
