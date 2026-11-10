# survey-service-006: Env 의 TLS 입력과 서비스 틀의 평문 HTTP, 기기 헤더를 믿는 근거가 서로 맞지 않는다

처리됨(계약 9.0.0(5f3c616, 848dbcb), ADR 0021): TLS 는 영역 게이트웨이(Caddy)가 끝내고 서비스는 영역 전용 네트워크에서 평문 HTTP 다. OPENIT_TLS_*_FILE 은 이웃을 부를 때의 클라이언트 인증서다. 영역 e47d70e, 게이트웨이 a56d244, compose 91cdb3a.

## 상태
요청(2026-11-10, survey-service 작업자). 대상: 헤드.

## 무엇이 어긋나나(읽어서 확인한 것)
- 계약 `SurveyServiceEnv` 는 `OPENIT_TLS_CERTIFICATE_FILE`, `OPENIT_TLS_PRIVATE_KEY_FILE`, `OPENIT_ROOT_CERTIFICATE_FILE`, `OPENIT_LISTEN_PORT` 를 required 로 정하고 설명은 '영역 사이 mTLS 의 서버·클라이언트 인증서'다. 서비스 틀의 Dockerfile 과 스모크, 루트 ADR 0006 은 컨테이너 안 평문 HTTP 8080 이다(게이트웨이가 TLS 를 끝낸다고 읽었다).
- 계약 `device_mtls` 는 '서비스는 게이트웨이와의 mTLS 연결로 온 요청의 X-Forwarded-Client-Cert 만 믿는다'고 정한다. 서비스가 그 연결이 게이트웨이의 것인지 확인하는 방법(클라이언트 인증서 검증 등)은 계약에 없다.

## 영역이 지금 한 것
서비스는 평문 HTTP 로 `OPENIT_LISTEN_PORT` 를 듣고, TLS 인증서·키 입력은 받아 검증만 하고 쓰지 않는다. 루트 인증서는 나가는 호출(model-runtime, IdP)의 신뢰 앵커로 쓴다. 헤더는 '게이트웨이만 서비스에 닿는다'는 네트워크 구성에 기대고 서비스 안에서 확인하지 못한다.

## 요청
(1) TLS 를 서비스가 끝내는지 게이트웨이가 끝내는지 정하고, 서비스가 끝낸다면 틀(Dockerfile, 스모크, HEALTHCHECK)을 TLS 로 바꾸고 클라이언트 인증서 검증(게이트웨이의 서비스 인증서)을 서비스가 하게 계약에 적어 달라. (2) 게이트웨이가 끝낸다면 Env 에서 서비스가 쓰지 않는 TLS 입력을 지워 달라.

## 하지 않은 것
계약과 생성물을 영역에서 고치지 않았다(계약은 동결이고 계약 타입은 생성 명령으로만 만든다).
