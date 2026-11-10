# 잡 이미지(ADR 0004, 0020). HTTP 서버가 없고 진입점이 잡 명령이다. 빌드 컨텍스트는 이 폴더다. `deploy/deploy build <잡 영역>` 로 빌드한다.
# 기반 이미지는 digest 로 고정한다. 값은 모든 Dockerfile 이 같아야 하며 tools/checks 가 점검한다(ADR 0006).
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.9.0@sha256:8f926a80debadba6f18442030df316c0e2b28d6af62d1292fb44b1c874173dc0

FROM ${UV_IMAGE} AS uv

# 왜: libs/ 의 공유 라이브러리를 경로 의존으로 쓰면 빌드에 들어가야 한다(ADR 0020). bake 가 `contexts = { libs = "libs" }` 로 이 단계를 libs/ 폴더로 바꾼다.
# 빌드 컨텍스트는 영역 폴더 그대로다(ADR 0006). 덮어쓰지 않고 직접 빌드하면 비어 있어 경로 의존을 설치하지 못하고 실패한다.
FROM scratch AS libs

FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
# 왜: 잠금 파일대로만 설치(--frozen)하고 시스템 파이썬을 쓴다(UV_PYTHON_DOWNLOADS=never)
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
# 왜 /work/services/<영역>: pyproject 의 경로 의존(../../libs/<이름>)이 개발 환경과 같은 상대 위치로 풀린다
COPY --from=libs / /work/libs
WORKDIR /work/services/__AREA__
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

FROM ${PYTHON_IMAGE} AS runtime
ARG REVISION
ARG VERSION
ARG CONTRACTS_VERSION
ARG SOURCE_URL
ARG SERVICE
# 왜 JOBS 인자: io.openit.jobs 라벨(계약 JobsDeclaration)의 원본은 jobs.json 하나다. bake 가 읽어 JSON 한 줄로 넣는다
ARG JOBS
LABEL org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.version="${VERSION}" \
      io.openit.service="${SERVICE}" \
      io.openit.contracts="${CONTRACTS_VERSION}" \
      io.openit.jobs="${JOBS}"
# 왜: 고정 uid/gid 는 읽기 전용 루트와 볼륨 권한을 예측 가능하게 한다
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /app/.venv /app/.venv
# 왜: 허용형 라이선스는 이미지에 저작권 표시와 라이선스 전문을 함께 주라고 요구한다. 잠금 파일에서 생성한 고지를 넣는다(ADR 0018)
COPY THIRD_PARTY_NOTICES /usr/share/doc/openit/THIRD_PARTY_NOTICES
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
# 왜 ENTRYPOINT: deploy 가 `<이미지> <잡 이름>` 으로 한 번 실행한다. 이미지가 스스로 서는 단위다(진입점 기본값을 이미지가 가진다)
ENTRYPOINT ["__PKG__"]
