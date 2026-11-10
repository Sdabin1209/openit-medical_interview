# 변경 요청 admin-console-001: 로그인한 사용자의 역할을 화면이 알 방법이 계약에 없다

- 영역: admin-console
- 대상 계약: `contracts/openapi/survey-service.yaml`, `contracts/components.yaml`(`UserRole`, `UserIdentityClaims`)
- 상태: 헤드 결정 대기. 그동안 화면은 oauth2-proxy 의 표준 엔드포인트 `/oauth2/userinfo` 의 `groups` 를 쓴다(ADR admin-console 0002).

## 문제
브리프는 "역할에 따라 화면을 보인다"를 요구한다. 화면은 토큰을 직접 다루지 않으므로(oauth2-proxy 가 쿠키 세션을 토큰으로 바꿔 서버에 싣는다) 자기 역할을 서버나 프록시에게 물어야 한다. 계약에는 사람 역할을 돌려주는 작업이 없다.

## 지금 화면이 하는 일(확인한 것과 못 한 것)
- 화면은 `GET /oauth2/userinfo`(oauth2-proxy 문서의 엔드포인트, 응답 칸 `user`, `email`, `preferredUsername`, `groups`)를 읽고 `groups` 에서 `UserRole` 값만 남긴다.
- 확인하지 못함: Keycloak 의 `realm_access.roles` 가 oauth2-proxy 의 `groups` 로 나오게 하는 설정(`--oidc-groups-claim` 에 중첩 클레임을 줄 수 있는지)은 이 작업에서 시험하지 않았다. platform 이 이 설정을 한다는 약속은 어느 문서에도 없다. 시험은 가짜 `/oauth2/userinfo` 로 했다.

## 요청(둘 중 하나)
1. 계약에 "내 신원과 역할" 작업(예: survey-service `GET /v1/me`, 응답 `UserIdentityClaims` 의 `sub` 와 역할 목록)을 둔다. 화면은 서버가 검증한 토큰에서 나온 값을 받는다. 서버가 역할을 매 요청에서 검사하므로 화면 쪽 표시는 편의일 뿐이다.
2. 또는 platform 의 oauth2-proxy 가 역할을 `groups` 로 내는 것을 platform 계약(환경 입력·구성)에 적는다.

## 덧붙임: `UserRole` 이 생성 타입에 없다
어떤 작업도 `UserRole` 을 스키마로 참조하지 않고 `security` 요구에 이름으로만 적어서 `openapi-typescript` 가 `src/contract` 에 이 타입을 만들지 않는다. 화면은 값을 `src/link/session.ts` 에 한 번 적고 `tests/contract/contract.test.ts` 가 계약의 enum 과 같은지 본다. 역할 목록을 돌려주는 작업(위 1)이 생기면 이 문제도 사라진다.
