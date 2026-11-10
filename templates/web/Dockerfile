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
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
# 이 기반 이미지의 기본 사용자는 비root(nginx, uid 101)다. 명시해 두면 기본값이 바뀌어도 root 로 돌지 않는다.
USER 101:101
EXPOSE 8080
# 왜 wget: alpine 에 busybox wget 이 있고 curl 은 없다
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
