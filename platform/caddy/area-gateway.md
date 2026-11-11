# 영역 게이트웨이(Caddy)

서비스 영역(survey-service, model-runtime, admin-console, kiosk-frontend)마다 컨테이너 하나가 서비스 앞에 선다. 결정과 근거는 [platform ADR 0007](../docs/adr/0007-영역-게이트웨이.md), 계약은 [계약 README 9.0.0](../../contracts/README.md)의 '인증'이다. 이 폴더의 `Caddyfile` 은 레지스트리 앞단(ADR 0013)이고 영역 게이트웨이는 `area-gateway.Caddyfile` 이다.

## 하는 일

| 번호 | 일 | 설정 |
|---|---|---|
| 1 | 서비스 이름으로 사설 CA(step-ca)에서 ACME(RFC 8555, http-01)로 인증서를 받고 갱신한다 | `tls { issuer acme }`, `storage file_system /area-certs` |
| 2 | 클라이언트 인증서를 요구하고 신뢰 목록으로 검증한다(계약 `area_mtls`) | `client_auth { mode require_and_verify }` |
| 3 | 서비스에 `X-Forwarded-Client-Cert` 를 입구(Envoy)의 클라이언트 인증서(SAN `gateway`)로 온 요청에서만 넘기고 그 밖에서는 지운다(계약 `device_mtls`) | `@not_ingress`, `request_header -X-Forwarded-Client-Cert` |
| 4 | 영역 안 감시용으로 `/healthz`·`/readyz`·`/metrics` 를 TLS 와 별개의 평문 포트 9100 으로 서비스에 이어 준다 | `http://:9100` |
| 5 | 건강 확인: 인증서와 키 파일이 생겼는지 본다 | 아래 |

TLS 를 이 컨테이너가 끝내므로 서비스 컨테이너는 영역 전용 내부 네트워크에서 평문 HTTP 로 `OPENIT_LISTEN_PORT` 를 듣고 게이트웨이만 닿는다.

## 환경 변수(템플릿이 읽는 것 전부)

| 이름 | 뜻 | 값의 출처 |
|---|---|---|
| `OPENIT_AREA_NAME` | 서비스 이름. 인증서의 이름이고 입구가 부르는 이름이다 | 이미지 라벨의 서비스 이름 |
| `OPENIT_AREA_UPSTREAM` | 영역 안 서비스 주소 `host:port`(평문) | 서비스 컨테이너의 영역 네트워크 전용 별칭(`<영역>-app`, 서비스 이름은 게이트웨이의 backend 별칭과 겹쳐 자기 자신으로 풀릴 수 있다)과 그 `OPENIT_LISTEN_PORT` |
| `OPENIT_SERVICE_PORT` | TLS 포트(컨테이너 안, 1024 이상). 입구가 이 포트로 접속한다 | 계약 `PlatformEnv.OPENIT_SERVICE_PORT`(`settings.service_port`) |
| `OPENIT_INTERNAL_ACME_DIRECTORY_URL` | 사설 CA 의 ACME 디렉터리 | 설치 설정(`deploy/env.example`) |

## 컨테이너가 갖추어야 할 것(deploy 의 compose)

- 이미지: digest 로 고정한 caddy(레지스트리·입구 에이전트와 같은 것). 마운트: 이 Caddyfile 을 `/etc/caddy/Caddyfile` 로, 신뢰 목록을 `/etc/openit/trust-list.pem` 으로(읽기 전용), 영역 안 공유 tmpfs 볼륨을 `/area-certs`(쓰기)로.
- `/area-certs` 볼륨은 서비스 컨테이너도 읽기 전용으로 마운트한다. 키 파일은 게이트웨이의 uid 가 0600 으로 쓰므로 서비스를 같은 uid 로 실행하거나 볼륨의 소유 uid 를 서비스와 맞춘다(입구와 입구 에이전트가 같은 uid 10001 인 것과 같은 이유).
- 사용자 `10001`, `read_only`, `cap_drop: [ALL]`. 80 번(http-01 검증)을 열려면 `cap_add: [NET_BIND_SERVICE]` 가 필요하다(ACME 서버가 서비스 이름의 80 번으로 접속한다). TLS 포트와 감시 포트는 1024 이상이라 권한이 필요 없다.
- `/data`·`/config` tmpfs(uid 10001). 네트워크: 영역 전용 내부 네트워크(서비스와 만난다)와 backend. 서비스 이름의 네트워크 별칭은 게이트웨이만 갖는다(서비스 컨테이너는 별칭이 없어 입구·감시·이웃이 게이트웨이로만 온다).
- 여러 서버 배치(서버별 가장자리 `area-edge` 가 있을 때): 인증서 발급의 http-01 검증이 가장자리를 지나므로 deploy 의 서버 덮개가 게이트웨이의 시작 명령을 '가장자리의 80 번에 연결되면 Caddy 시작'으로 바꾸고 가장자리를 게이트웨이 시작 뒤에 시작하게 한다([deploy ADR 0029](../../docs/adr/0029-게이트웨이는-가장자리가-열린-뒤-시작한다.md)). 서버 한 대 배치는 가장자리가 없고 이미지 기본 명령 그대로다.
- 감시: `backend` 에서 `<서비스 이름>:9100`. 입구(`Exposure`)는 이 포트로 라우트를 만들지 않는다.

## 건강 확인

`platform/src/openit_platform/area_gateway.py` 의 `healthcheck_command(서비스 이름, ACME 디렉터리)` 가 compose `healthcheck` 의 `CMD-SHELL` 값이다. 인증서(`.crt`)와 키(`.key`) 파일이 비어 있지 않은지 `test -s` 로 본다. 왜 TLS 를 두드리지 않나: 클라이언트 인증서가 없는 연결은 거절되고 검증을 끄고 두드리지 않는다(관리 API 는 `admin off`). 파일 경로는 입구 에이전트와 같은 certmagic 규칙(`ingress.acme_issuer_key`)이다: `/area-certs/certificates/<발급자>/<서비스 이름>/<서비스 이름>.crt`.

## 서비스가 읽는 인증서

서비스 `OPENIT_TLS_CERTIFICATE_FILE`·`OPENIT_TLS_PRIVATE_KEY_FILE` 은 위 `.crt`·`.key`(`certificate_paths`)를 가리킨다. 이 인증서는 서비스 이름의 서버·클라이언트 인증서이고 사설 CA 가 두 용도(serverAuth, clientAuth)로 발급한다. 갱신되면 같은 경로의 파일이 바뀐다.
