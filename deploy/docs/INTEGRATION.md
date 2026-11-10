# 배포 통합 확인 결과

`./deploy build`(전 영역)와 `./deploy up` 으로 추론 엔진(vLLM)을 뺀 구성이 뜨는 것과 각 서비스의 건강 확인을 본 결과다. 이 문서는 **배포 통합의 결과 한 곳**이다. 영역의 시험 상태는 각 영역 README 5절, E2E 결과는 `E2E_RESULTS.md`(아직 없음)를 본다. 구성의 결정과 근거는 [ADR 0021](../../docs/adr/0021-서비스-TLS-종단은-영역-게이트웨이가-한다.md), [0022](../../docs/adr/0022-영역-이미지-선언-라벨의-원본과-bake-경로.md), [0023](../../docs/adr/0023-통합-배치-영역-네트워크와-추론-엔진-프로파일.md)이다.

## 환경과 설치 값(2026-11-11)

- 한 대의 개발 서버(WSL2, Docker Engine 28.5.1, containerd 이미지 저장소). compose 프로젝트 이름 `openit-int`(`deploy/.env`, git 제외).
- 이 서버에는 GPU 가 보이지만(`nvidia-smi` 가 GPU 하나를 보임) 추론 엔진은 띄우지 않았다. 서빙 GPU 서버 배치(design.md 6절)이므로 설치 설정 `OPENIT_INFERENCE_ENGINE_LOCAL=false` 로 compose 프로파일 `inference-engine` 을 켜지 않았다. 제품 compose 에 시험용 줄은 없다.
- 기기 인증서를 검증할 조직 PKI 루트(`OPENIT_DEVICE_CA_CERTIFICATE_FILE`)가 없으면 입구가 키오스크 경로를 열 수 없어 시작하지 않는다. 이 확인에서는 이 서버에서 만든 사용 후 버릴 루트(`deploy/pki/verification-device-ca.pem`, git 제외)를 설치 값으로 주었다. 기기 허용 목록은 비어 있다.
- 경보 수신처(`OPENIT_ALERT_RECEIVER_URL`)는 비워 두었다(doctor 가 알린다).

## 명령과 결과

| 명령 | 결과 |
|---|---|
| `./deploy doctor` | rc=0. 입구 라우트 32개(admin-console 1 HUMAN_OIDC, kiosk-frontend 1 DEVICE_MTLS, model-runtime 5 HUMAN_OIDC, survey-service 25), 나가는 터널 2개, 기계 호출자 1명 |
| `./deploy build` | rc=0. 대상 7개(_example, _example-job, web-example, model-runtime, survey-service, web-admin-console, web-kiosk-frontend). Trivy(config·image)·고지 점검 통과 |
| `./deploy bootstrap` → `./deploy up` | `up` rc=0. 컨테이너 20개 모두 running(oauth2-proxy 는 셸이 없는 distroless 라 health 가 없다, ADR 0008) |
| `./deploy status` | rc=0 |

## 건강 확인(영역 안 감시 포트 9100, `backend` 에서)

| 서비스 | /healthz | /readyz | /metrics |
|---|---|---|---|
| survey-service | 200 | 200(`database` 통과) | 200 |
| model-runtime | 200 | **503**(`준비되지 않은 점검: engine`) | 200 |
| admin-console | 200 | 200 | 200 |
| kiosk-frontend | 200 | 200 | 200 |

model-runtime 의 `/readyz` 503 은 추론 엔진이 없는 배치에서 나오는 정상 결과다(엔진이 준비되어야 200). Prometheus 가 `<서비스>:9100/metrics` 를 긁는다.

## 입구와 영역 사이 호출(관찰한 것)

- 입구(공개 TLS, 신뢰 목록으로 검증): `/console/` 302(로그인 화면), `/kiosk/` 403(기기 인증서 없음), `/v1/questionnaires`·`/v1/model-status` 401(토큰 없음), `/healthz` 404(입구로 내보내지 않음), `/realms/openit/.well-known/openid-configuration` 200.
- survey-service 컨테이너 안에서 실제 호출: Keycloak 에서 `machine-survey-service` 기계 토큰을 받고(client credentials, 터널 경유) 영역 게이트웨이의 클라이언트 인증서로 mTLS 를 한 뒤 model-runtime 의 `GET /v1/model-status` 를 불러 200 `{"state":"NOT_LOADED"}` 를 받았다. 토큰 없이는 401.
- 이 호출에서 만난 결함 둘을 고쳤다: 영역 게이트웨이가 상류 이름을 자기 자신으로 풀 수 있던 것(상류에 영역 네트워크 전용 별칭 `<영역>-app`), model-runtime 이 Keycloak JWKS 의 암호화용(`use: enc`) 키 때문에 서명 키 갱신에 실패하던 것.

## 확인하지 못한 것

- 추론 엔진(vLLM) 컨테이너의 기동과 어댑터 적재, 그래서 model-runtime `/readyz` 200 과 추출·응답 호출. GPU 서버 배치에서 확인한다.
- 키오스크 기기 인증서로 `/kiosk/`·`/v1/sessions` 를 여는 종단 경로(이 서버의 기기 CA 는 사용 후 버릴 루트이고 기기 인증서를 발급해 보지 않았다). platform 샌드박스 시험이 기기 경로를 컨테이너에서 확인한다(platform README 5절).
- 사람 로그인(브라우저 OIDC)의 종단 경로와 웹 푸시 전송, 레지스트리 인증(로컬 레지스트리에는 인증이 없다, ADR 0013), 서버 여러 대 배치.
- 이 확인은 이 서버 한 곳에서 한 번 했다(두 번째 환경 확인 없음).

## 정리(2026-11-11)

확인 뒤 이 프로젝트(`openit-int`)만 프로파일 포함 `down -v --remove-orphans` 로 내렸다. 컨테이너와 볼륨은 0개다. 네트워크 `openit-int_kiosk-frontend-area` 하나가 남았다: 컨테이너가 없는데 엔진이 끝점(`openit-int-kiosk-frontend-gateway-1`)이 남아 있다고 보고해 지워지지 않는다(`network disconnect -f` 도 '끝점 없음', 재시도 후에도 같다). 이 엔진은 다른 사용자의 컨테이너도 돌리고 있어 엔진을 다시 시작하지 않았다. 엔진이 다시 시작될 때 사라지는 빈 네트워크로 추정하며 확인하지 않았다.
