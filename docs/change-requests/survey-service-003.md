# survey-service-003: 계약의 UserIdentityClaims 가 realm_access.roles 를 UserRole 로만 받아 실제 Keycloak 토큰이 거절된다

처리됨(계약 8.0.0, bb16c28): platform 이 토큰에 계약 역할만 싣게 설정한다. 영역은 모르는 역할을 버리는 코드를 지우고 계약 모델로 그대로 검증한다(영역 ADR 0006 수정).

## 상태
요청(2026-11-10, survey-service 작업자). 대상: 헤드.

## 무엇이 어긋나나(읽어서 확인한 것)
- `UserIdentityClaims.realm_access.roles` 는 `UserRole`(7개) 열거의 배열이다(`RealmAccessClaim`, maxItems 7).
- Keycloak 은 `offline_access`, `uma_authorization`, `default-roles-<realm>` 같은 기본 역할도 같은 배열에 넣는다. 계약대로 엄격히 검증하면 이 토큰은 모두 401 이다.

## 영역이 지금 한 것
영역은 검증 전에 `UserRole` 에 없는 역할을 버린다(영역 ADR 0006). 버려도 권한은 늘지 않는다.

## 요청
`realm_access.roles` 를 열린 문자열 배열로 바꾸거나(요구 역할은 작업의 security 가 `UserRole` 로 적는다), 계약에 '`UserRole` 밖의 값은 무시한다'를 적어 달라.

## 하지 않은 것
계약과 생성물을 영역에서 고치지 않았다(계약은 동결이고 계약 타입은 생성 명령으로만 만든다).
