# 0031. 화면 웹 서버 기반 이미지는 nginx mainline 갈래로 한다

## 상태
승인(2026-11-23, 사용자 지시 "패치된 것을 쓰도록 바꾼다"). [ADR 0011](0011-정적-화면-이미지와-웹-서버.md)의 실행 단계 기반 이미지 갈래(`stable-alpine`)를 대체한다. 비root·digest 고정·설정·`apk upgrade` 규칙은 그대로다.

## 맥락
2026-11-23 화면 이미지 빌드가 Trivy 이미지 검사(ADR 0016)에서 실패했다. 기반 `nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed…` 의 nginx 1.30.6-r1 에 수정판(1.30.7)이 있는 CRITICAL 4건·HIGH 2건이 공개됐다(CVE-2026-113425, -121810, -123007, -123633, -118899, -123634).

- 같은 날 확인한 `stable-alpine` 태그는 아직 같은 digest(nginx 1.30.6)였다. 공식 이미지가 다시 빌드되지 않았다.
- Dockerfile 의 `apk upgrade` 로도 고쳐지지 않는다. 기반 이미지가 `/etc/apk/world` 에 `nginx=1.30.6-r1` 로 버전을 고정해(nginx.org 패키지) 업그레이드에서 빠진다. 다른 알파인 패키지(musl, libexpat 등 14건)는 `apk upgrade` 가 고친다.
- `mainline-alpine@sha256:b5047b9…`(nginx 1.31.7)에 `apk upgrade` 를 거친 이미지는 같은 Trivy 기준(CRITICAL·HIGH, 수정판 있는 것)에서 0건이었다.

## 결정
화면 이미지의 실행 단계 기반을 `nginxinc/nginx-unprivileged:mainline-alpine`(digest 고정)으로 바꾼다. 모든 화면 Dockerfile 과 템플릿이 같은 값을 쓴다(tools/checks image-pins).

## 왜
- nginx 는 mainline 갈래를 일반적인 사용에 권하고, 보안 수정이 mainline 에 먼저 들어간다(nginx 의 갈래 설명: stable 은 중요한 수정만 받는 갈래이고 새 기능과 수정은 mainline 에 먼저 들어간다. 이 ADR 을 쓸 때 원문을 다시 열어 확인하지 않았다. 이번 사례의 사실 근거는 위 맥락의 Trivy 결과다). 이 이미지는 정적 파일만 내주고 `listen 8080` 외 기능(HTTP/2·3, TLS, 메일, resolver)을 쓰지 않아 mainline 의 기능 변화에 닿는 면이 작다.
- 취약점을 무시 목록(`.trivyignore`)으로 넘기는 것보다 고쳐진 판을 쓰는 것이 ADR 0016 의 원칙(수정판이 있으면 막는다)에 맞다.

## 검토한 대안과 버리는 이유
- **stable 을 유지하고 무시 목록에 기한을 두고 기다린다:** 쓰지 않는 기능의 취약점이라 실제 위험은 낮지만, 공식 이미지가 언제 다시 나올지 모르고 그동안 수정판을 두고 무시를 유지한다.
- **알파인의 nginx 패키지로 바꿔 넣는다:** nginx.org 패키지와 모듈 구성이 달라 공식 비root 이미지의 전제가 깨진다.

## 결과
- **얻는 것:** 화면 이미지 빌드가 Trivy 를 통과한다(0건).
- **감수하는 것:** mainline 은 stable 보다 바뀜이 잦다. 기반 digest 를 올릴 때 스모크와 화면 시험으로 확인한다.

## 되돌리는 조건
mainline 에서 이 이미지가 쓰는 기능의 동작이 바뀌어 문제가 생기거나, stable 이 수정판을 빠르게 받는 것으로 확인되면 stable 로 돌아간다.
