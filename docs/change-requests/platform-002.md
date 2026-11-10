# platform-002: 기계 토큰의 형태(MachineTokenTable 의 token_file 과 Keycloak 기계 클라이언트)

처리됨(계약 9.0.0(5f3c616, 848dbcb), platform a56d244): 기계 토큰은 client credentials JWT 로 확정, MachineTokenEntry.client_secret_file, MachineIdentityClaims.

상태: 요청(헤드 판단 필요). 대상 계약: `MachineTokenTable`, `MachineTokenEntry`, `securitySchemes.machine_token`, `OPENIT_MACHINE_TOKENS_FILE`.

## 문제

계약은 기계 호출자를 "토큰 값이 든 파일(`token_file`)"을 가진 표(`MachineTokenTable`)로 가른다고 쓴다(고정 bearer 토큰, 받는 쪽이 표로 호출자와 권한을 가른다). 브리프는 사람 인증(Keycloak)의 기계 클라이언트가 `MachineRole` 을 갖고 RFC 9068 접근 토큰을 내라고 한다. 둘은 같은 토큰이 될 수 없다.

- 입구(Envoy)는 파일의 고정 토큰과 요청의 토큰을 비교할 수 없다. 비교하려면 토큰 값이 Envoy 설정 파일에 들어가야 하는데(D84 위반), RBAC·헤더 일치 같은 표준 기능은 설정 안의 값만 비교한다. 파일을 읽어 비교하는 표준 필터가 없다.
- Keycloak 접근 토큰은 수명이 짧아(5분) 파일 하나에 고정해 둘 수 없다.

## platform 이 한 선택(임시)

기계 토큰 = Keycloak 의 client credentials 접근 토큰이다. `MachineTokenTable` 의 호출자(`client`)마다 기계 클라이언트 `machine-<client>` 가 만들어지고 서비스 계정이 표의 `roles` 를 realm 역할로 갖는다. 입구는 서명·`iss`·`aud`·`exp` 를 JWKS 로 검증하고 `realm_access.roles` 로 역할을 가른다. 클라이언트 비밀은 `deploy/secrets/machine-clients/<client>` 파일(`./deploy secrets init` 이 만든다)이고 호출자는 그것으로 토큰 엔드포인트에서 토큰을 받는다. `token_file` 은 쓰지 않는다.

## 헤드에게 묻는 것

1. 기계 토큰을 Keycloak 접근 토큰으로 확정하는가. 그렇다면 `MachineTokenEntry.token_file` 을 지우거나 "클라이언트 비밀 파일"로 뜻을 바꾸고, `securitySchemes.machine_token` 의 설명(받는 쪽이 `MachineTokenTable` 로 가른다)을 "JWT 접근 토큰의 `realm_access.roles` 로 가른다"로 바꾼다. 받는 영역(survey-service, model-runtime)도 같은 토큰 검증(`UserIdentityClaims` 와 같은 JWKS 검증)을 하게 된다.
2. 아니면 고정 토큰을 유지하되 입구가 비교하지 못하므로 `EXTERNAL_MACHINE_TOKEN` 경로의 토큰 대조는 받는 영역이 맡는다고 정한다(입구는 TLS 만 한다).
3. 기계 접근 토큰의 클레임에는 `UserIdentityClaims.realm_access.roles` 가 `UserRole` 만 허용하므로(열거) 기계 역할이 들어가면 그 스키마를 어긴다. 기계 토큰용 클레임 스키마가 따로 필요하다.
