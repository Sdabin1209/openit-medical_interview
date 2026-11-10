# 화면 이미지(ADR 0004, 0010): 빌드한 정적 파일을 비root 웹 서버가 서빙한다. 빌드 컨텍스트는 이 폴더다.
# 기반 이미지는 digest 로 고정하고, 값은 모든 Dockerfile 이 같아야 한다(tools/checks image-pins).
ARG NODE_IMAGE=node:24-bookworm-slim@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9
ARG WEB_SERVER_IMAGE=nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03

FROM ${NODE_IMAGE} AS build
WORKDIR /src
# 왜 npm ci: 잠금 파일(package-lock.json)대로만 설치한다
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
RUN npx tsc --noEmit && npx vite build

FROM ${WEB_SERVER_IMAGE} AS runtime
ARG REVISION
ARG VERSION
ARG CONTRACTS_VERSION
ARG SOURCE_URL
ARG SERVICE
LABEL org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.version="${VERSION}" \
      io.openit.service="${SERVICE}" \
      io.openit.contracts="${CONTRACTS_VERSION}"
# 왜 apk upgrade: 기반 이미지(digest 고정)의 알파인 패키지에 수정판이 나온 취약점(CRITICAL·HIGH)이 있다(Trivy 로 확인, ADR 0016).
# 기반 이미지가 갱신되면 이 줄을 지운다. 감수: 이 줄은 빌드 시점의 패키지 저장소를 따라 같은 입력에서 같은 이미지가 나오지 않는다
# hadolint DL3017(apk upgrade 금지)은 위 이유로 .hadolint.yaml 에서 사유와 함께 무시한다
USER 0:0
RUN apk upgrade --no-cache
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
# 왜: 번들된 JavaScript 는 브라우저로 배포되므로 고지를 이미지 문서 폴더와 서버(/THIRD_PARTY_NOTICES.txt) 두 곳에 둔다(ADR 0018)
COPY THIRD_PARTY_NOTICES /usr/share/doc/openit/THIRD_PARTY_NOTICES
COPY THIRD_PARTY_NOTICES /usr/share/nginx/html/THIRD_PARTY_NOTICES.txt
# 이 기반 이미지의 기본 사용자는 비root(nginx, uid 101)다. 명시해 두면 기본값이 바뀌어도 root 로 돌지 않는다.
USER 101:101
EXPOSE 8080
# 왜 wget: alpine 에 busybox wget 이 있고 curl 은 없다
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
