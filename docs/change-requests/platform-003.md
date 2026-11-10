# platform-003: 노출 선언(Exposure)에 요구 역할이 없다 / platform 자신의 익명 경로

처리됨(계약 9.0.0(5f3c616, 848dbcb), platform a56d244): 노출 선언 × 작업 security 가 정본(ExposureRoute 에 roles 없음), 로그인 경로는 계약 밖 내부 구현, aud 불일치는 서비스 401·입구 403 을 계약이 인정한다.

상태: 요청(헤드 판단 필요). 대상 계약: `Exposure`, `ExposureRoute`, `ExposureAudience`.

## 문제 1: 역할은 계약의 OpenAPI 에만 있다

입구가 "대상별로 인증을 건다"는 것은 사람·기기·외부 기계 호출자를 가르는 데까지다. 작업마다 어떤 역할(`UserRole`, `MachineRole`)이 필요한지는 `contracts/openapi/<영역>.yaml` 의 작업 `security` 에만 있고 `Exposure` 에는 없다. 외부 기계 호출자 둘(병원 시스템 `result-reader`, 위험 감지기 `risk-detector`)을 입구에서 가르려면 경로마다 역할이 필요하다.

platform 의 임시 처리: 입구 설정 생성기가 노출 선언의 경로 접두어에 드는 작업을 계약 OpenAPI 에서 찾아(읽기 전용) 작업마다 라우트를 만들고 그 작업의 `security` 가 허용하는 역할만 연다. 접두어에 드는 작업 중 그 대상(예: `DEVICE_MTLS`)을 허용하지 않는 작업은 그 대상에게 열지 않는다. 허용하는 작업이 하나도 없으면 시작하지 않는다. 작업이 없는 접두어(정적 화면)는 대상만 건다.

묻는 것: 이 방식(노출 선언 × 계약의 작업 인증 요구)을 정본으로 삼을지, 아니면 `ExposureRoute` 에 `roles`(`UserRole`·`MachineRole` 배열)를 더해 영역이 선언하게 할지. 앞의 방식은 platform 이 `contracts/openapi/` 의 구조(작업 경로·`security`)를 읽는다는 점에서 구조 규칙 1(영역은 서로의 구조를 모른다)과 긴장하지만 읽는 대상이 영역 코드가 아니라 헤드 소유의 계약이다.

## 문제 2: 로그인 경로는 어느 대상도 아니다

사람 로그인에 필요한 경로(`/realms/openit/…` Keycloak, `/oauth2/…` oauth2-proxy)는 로그인 전에 열려야 하므로 인증을 걸 수 없다. `ExposureAudience` 에는 "익명 공개"가 없다(`HUMAN_OIDC` 는 로그인 뒤). platform 은 자기 컴포넌트(identity, identity_proxy)의 경로라 입구 설정 생성기에 내장했고(`gateway.py` 의 `_builtin_routes`) Keycloak 관리 콘솔(`/admin`)과 `master` realm 은 열지 않는다.

묻는 것: platform 자신의 익명 경로를 계약에 선언해야 하는가(예: `ExposureAudience.PUBLIC`), 아니면 platform 내부 구현이라 계약 밖으로 둔다고 확인해 주는가.

## 문제 3: aud 불일치의 상태 코드

계약(RFC 9068 4, D58)은 aud 가 자기 서비스 이름이 아닌 토큰을 401 로 거절한다. 입구의 Envoy `jwt_authn` 은 aud 불일치를 403 으로 낸다(고정 동작이고 바꾸는 설정이 없다). 입구는 서비스의 검증을 대신하지 않으므로(서비스가 다시 검증한다) 열리지 않는 것은 같다. 입구 앞에서의 상태 코드만 다르다. 입구의 응답 코드를 401 로 맞춰야 한다면 알려 달라(Lua 로 aud 를 직접 보는 방법이 있으나 표준 필터를 쓰지 않게 된다).
