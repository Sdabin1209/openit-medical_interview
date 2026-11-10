# platform

기성품 구성 영역이다. 입구(Envoy), 사람 인증(Keycloak, oauth2-proxy), 사설 CA(step-ca), 감시(Prometheus, Alertmanager, blackbox_exporter), 이미지·모델 패키지 레지스트리(Distribution + Caddy)를 한 묶음으로 구성한다. 코드보다 설정이 중심이고, 이 폴더의 코드는 설치 설정과 계약에서 그 설정 파일들을 만드는 생성기다. 컨테이너는 `deploy/compose.yaml` 이 띄우고 `./deploy` 가 이 생성기를 불러 `deploy/generated/` 에 파일을 만든다(git 제외).

영역 사이 값의 정본은 `contracts/` 다. 이 영역의 컴포넌트와 역할은 [설계 2절](../docs/design.md), 폴더는 [설계 5절](../docs/design.md), 어휘는 [설계 4절](../docs/design.md)이다.

## 1. 하는 일

- **gateway(Envoy):** 공개 TLS 를 끝낸다(인증서 방식: `private`, `organization`, `acme-public`). 키오스크 기기 인증서를 검증하고(mTLS, 조직 PKI 루트, 허용 목록) 서비스에 `X-Forwarded-Client-Cert` 로 넘기며 클라이언트가 보낸 같은 헤더는 지운다. 각 영역의 노출 선언(`Exposure`)과 계약 OpenAPI 의 작업 인증 요구에서 라우트를 만들고 대상(`ExposureAudience`)마다 인증을 건다. 나가는 호출은 `Exposure.egress` 에 선언한 상대에게만 CONNECT 터널로 이어 준다.
- **identity(Keycloak):** realm `openit` 을 파일로 가져온다. 사람 역할은 계약 `UserRole`, 기계 클라이언트는 `MachineRole`, 접근 토큰은 RFC 9068 프로파일이다.
- **identity_proxy(oauth2-proxy):** 화면 경로의 로그인 앞단. 입구가 세션을 묻는다.
- **ca(step-ca):** 사설 CA(ACME). 루트·중간 CA 교체 명령(`./deploy ca rotate`, `rotate-root`).
- **monitoring:** 인증서 만료 감시, 영역 `/metrics` 수집, 경보 수신(Watchdog 생존 신호 포함).
- **registry:** `deploy/compose.yaml` 의 `registry`·`registry-store`(ADR 0013).

## 2. 받는 계약·내는 계약

| | 계약 | 쪽 |
|---|---|---|
| 받는다 | `Exposure`(이미지 라벨 `io.openit.exposure`), `DeviceAllowlist`, `MachineTokenTable`, `PlatformEnv`(설치 설정), 계약 OpenAPI 의 작업 `security` | 영역·deploy |
| 낸다 | `X-Forwarded-Client-Cert`(`ForwardedClientCertValue`), 사람·기계 접근 토큰(`AccessTokenHeader`, `UserIdentityClaims`), 서비스 인증서(`OPENIT_TLS_*`, 이 영역은 CA 만 맡고 발급 방식은 ACME), `OPENIT_EGRESS_PROXY` 값(`deploy/generated/gateway/egress-proxies.json`) | 흐름 N12, N13 |

계약이 부족하거나 틀렸다고 본 것은 `docs/change-requests/platform-001.md`~`003` 에 있다.

## 3. 컴포넌트(생성기 모듈)

| 컴포넌트 | 모듈 | 입력 → 출력 |
|---|---|---|
| gateway | `gateway.py`(라우트·Envoy), `ingress.py`(입구 인증서 에이전트 Caddyfile) | 노출 선언, 허용 목록, 계약 OpenAPI, 설치 설정 → `envoy.yaml`, `Caddyfile`, `egress-proxies.json` |
| identity, identity_proxy | `identity.py` | 기계 호출자 표, 설치 설정 → `openit-realm.json` |
| ca | `pki.py` | 설치 설정 → `ca.json`, 신뢰 목록, 인증서 검증 |
| monitoring | `monitoring.py`, `monitoring/`(규칙·규칙 시험) | 노출 선언, 설치 설정 → 감시 대상·`alertmanager.yml` |
| (공통) | `settings.py`, `generate.py` | 설치 설정 해석·검증, 모든 생성 파일 |

`contract/models.py` 는 `uv run --project tools/checks openit-gen-contract platform` 이 계약에서 생성한다(손으로 고치지 않는다).

## 4. 실행·시험 명령

```
cd platform
uv run pytest                    # 단위 시험(docker 없음)
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest -m sandbox tests/scenario   # 샌드박스 종단 시험(docker, 10분 안팎)
```

샌드박스 시험은 리포의 `deploy/`·`platform/`·`contracts/` 를 임시 폴더로 복사해 그 복사본의 `./deploy bootstrap` 으로 두 번째 설치를 띄운다(제품 compose·설정에 시험용 문이 없다, D123). 시험 서비스(에코 상류, 클라이언트)는 시험 폴더의 compose 조각으로만 더한다. 끝나면 그 프로젝트(`openit-pf-sbx-…`)만 내리고 남은 컨테이너·볼륨·네트워크가 0개인지 확인한다. 실패하면 먼저 로그를 `platform/.pytest_cache/` 에 남긴다.

배포 쪽 명령(관리 노드에서): `./deploy doctor`(생성한 설정을 제품의 검증 명령으로 본다), `./deploy bootstrap`, `./deploy up`, `./deploy ca status|rotate|rotate-root|bundle|csr|install`, `./deploy identity sync`. 절차는 [CA 운영](../deploy/docs/CA.md).

## 5. 시험 상태

시험 개수·결과를 이 문서에 복사하지 않는다(문서마다 시점이 어긋난다). 이 영역의 마지막 검증 결과는 아래 한 곳에 둔다.

2026-11-10, 이 작업 트리(브랜치 candidate-v7-platform)에서 확인했다. 단위 시험·ruff·pyright 와 샌드박스 종단 시험(기기 인증서, XFCC, 사람 OIDC 와 계약 역할만 담은 토큰, 기계 토큰 역할별 허용·거부, 나가는 터널, 영역 지표·Watchdog, 폐기 반영, 인증서 갱신과 Envoy 재적재, 루트 교체, `identity sync`)이 통과했다. 확인하지 못한 것: `acme-public` 과 `organization` 입구 인증서의 종단 간 시험, 경보 수신처로의 실제 전송, 루트 교체 2단계가 이전 루트 서명 인증서를 보고 거절하는 경우의 자동 시험(수명 5분 설치에서는 경주가 된다). 변경 요청 platform-001~003 은 헤드의 답을 기다린다.

## 6. ADR

- [0001 설정 폴더 이전과 계약 이름](docs/adr/0001-설정-폴더-이전과-계약-이름.md)
- [0002 입구 구성과 인증서 에이전트](docs/adr/0002-입구-구성과-인증서-에이전트.md)
- [0003 라우트 생성과 인증 요구](docs/adr/0003-라우트-생성과-인증-요구.md)
- [0004 사람 인증: Keycloak realm 과 oauth2-proxy](docs/adr/0004-사람-인증-keycloak-realm과-oauth2-proxy.md)
- [0005 감시: 경보 수신과 영역 지표](docs/adr/0005-감시-경보-수신과-영역-지표.md)
- [0006 루트 CA 교체 명령](docs/adr/0006-루트-ca-교체-명령.md)

리포 전체의 관련 ADR: [0008 기반 compose 서비스](../docs/adr/0008-기반-compose-서비스-구성.md), [0013 관리 노드와 부트스트랩](../docs/adr/0013-관리-노드와-부트스트랩-순서.md), [0014 인증서 수명과 자동 갱신](../docs/adr/0014-인증서-수명과-자동-갱신.md), [0015 신뢰 구성](../docs/adr/0015-신뢰-구성.md).
