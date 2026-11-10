# 0004. 사람 인증: Keycloak realm 과 oauth2-proxy

## 상태
승인(2026-11-10, platform 작업). 리포 ADR 0008의 최소 realm("oauth2-proxy 클라이언트 하나")을 대체한다.

## 맥락
계약은 사람의 접근 토큰을 RFC 9068 프로파일로 정한다(`typ at+jwt`, `iss`, `sub`, `aud`, `exp`, `iat`, `jti`, `client_id`, 역할은 `realm_access.roles`, 역할 이름은 `UserRole`). 기계 호출자의 역할은 `MachineRole` 이다.

## 결정
- **realm 은 파일로 가져온다:** `identity.render_realm` 이 realm `openit` 을 생성한다(`--import-realm`). 비밀은 `${이름}` 자리표시자이고 값은 Keycloak 시작 명령이 비밀 파일에서 그 프로세스 안에서만 환경 변수로 만든다(ADR 0008).
- **역할:** realm 역할은 계약 `UserRole` 7개와 `MachineRole` 4개뿐이다. Keycloak 의 기본 역할(`default-roles-openit`, `offline_access`, `uma_authorization`)은 새 계정마다 붙고 realm 파일로 비울 수 없다(시험에서 확인: 가져오기가 구성 역할 목록을 무시한다). 그래서 클라이언트의 Full Scope Allowed 를 끄고 realm 역할 범위 매핑(`scopeMappings`)을 계약의 역할(사람 클라이언트는 `UserRole`, 기계 클라이언트는 그 호출자의 `MachineRole`)로 제한한다. 접근 토큰의 `realm_access.roles` 에는 범위에 든 역할만 실린다. 서비스 쪽에서 모르는 역할을 버리지 않는다. 시험이 실제 Keycloak 의 사람 토큰의 역할이 계약 역할뿐임을 본다. 초기 `admin` 계정은 `admin` 역할과 임시 비밀번호(비밀 파일, 처음 로그인에 변경 요구)로 시작한다.
- **RFC 9068:** 클라이언트 속성 `access.token.header.type.rfc9068=true`(Keycloak 이 JOSE 헤더 `typ` 를 `at+jwt` 로 낸다), 접근 토큰 수명 300초(Keycloak 기본값, 측정하지 않았다), 클라이언트마다 고정 값 매퍼로 `client_id`(세션 노트 매퍼는 서비스 계정에만 값이 있다), 서비스별 audience 매퍼로 `aud`. 사람 토큰의 `aud` 는 사람 인증 경로가 있는 서비스들, 기계 토큰의 `aud` 는 그 역할을 요구하는 작업이 있는 서비스(계약 OpenAPI 에서)다. 시험이 로그인으로 받은 토큰의 헤더와 클레임을 계약 스키마(`AccessTokenHeader`, `UserIdentityClaims`, `TokenAudienceClaim`)로 검증한다.
- **기계 클라이언트:** `MachineTokenTable` 의 호출자마다 `machine-<이름>` 기밀 클라이언트(client credentials만, 서비스 계정이 표의 역할을 realm 역할로)를 만든다. 비밀은 `deploy/secrets/machine-clients/<이름>`(`./deploy secrets init`)이다(변경 요청 platform-002).
- **oauth2-proxy:** 입구의 ext_authz 가 세션을 묻는다(ADR 0003). `--code-challenge-method=S256`(PKCE), 쿠키 `secure`·`lax`, 발급자 인증서는 신뢰 목록으로 검증, `--oidc-email-claim=sub`(계정에 이메일이 없을 수 있다), 접근 토큰은 `X-Auth-Request-Access-Token` 으로 입구에 준다. 접근 토큰 수명의 4/5(240초)마다 갱신 토큰으로 새 토큰을 받고 세션 쿠키는 10시간(Keycloak SSO Session Max 기본값)이다(측정하지 않았다).
- **화면이 아는 사용자 역할(admin-console-001, 계약 9.0.0 '화면이 아는 사용자 역할'):** 화면은 oauth2-proxy 의 `/oauth2/userinfo` 의 `groups` 를 읽는다. oauth2-proxy 클라이언트에 Keycloak 표준 프로토콜 매퍼 User Realm Role(`oidc-usermodel-realm-role-mapper`, `claim.name=groups`, 다중값, 접근 토큰·ID 토큰·userinfo)을 더했다. oauth2-proxy 는 기본값(`--oidc-groups-claim=groups`)을 쓰므로 `deploy/compose.yaml` 의 명령은 바꾸지 않는다. 클라이언트 범위가 `UserRole` 로 제한되어 있어(위) `groups` 에도 `UserRole` 만 나온다. 단위 시험이 매퍼 설정을, 샌드박스가 실제 Keycloak·oauth2-proxy 로 `staff-1` → `["staff"]`, `clinician-1` → `["clinician"]`, 세션 없음 → 401 을 본다(`test_userinfo_groups_carry_only_the_users_contract_roles`). **제공자는 `--provider=oidc`:** `keycloak-oidc` 제공자는 `realm_access.roles` 를 `role:<이름>` 항목으로 groups 에 더 붙여(샌드박스에서 확인: `["staff", "role:staff"]`) 계약 `UserRole` 뿐이라는 결정과 어긋난다. 일반 `oidc` 제공자는 groups 클레임을 그대로 쓴다(헤드 결정 2026-11-11). 대신 `keycloak-oidc` 제공자의 Keycloak 전용 기능(`--allowed-role` 등)은 쓰지 않는다(이 구성은 쓰지 않았다). 확인하지 못한 것: 한 사람에게 역할이 둘 이상일 때의 `groups` 순서(순서에 기대지 않는다), 화면 이미지와의 종단.
- **realm 변경의 반영:** Keycloak 은 이미 있는 realm 을 다시 가져오지 않는다. 기계 호출자나 노출 선언이 바뀌어 realm 파일이 달라지면 `./deploy up` 이 알리고(`identity/openit-realm.json` 이 바뀌었다는 메시지) `./deploy identity sync` 가 반영한다(클라이언트는 덮어쓰고 역할은 없는 것만 만든다. 역할을 덮어쓰면 사람 계정의 역할 부여가 사라지는 것을 시험에서 확인했다).

## 왜
- RFC 9068 은 JWT 접근 토큰의 프로파일이고 Keycloak 이 지원한다(속성). 계약이 같은 프로파일을 요구하므로 별도 변환 계층이 필요 없다.
- 기본 역할을 비우는 것은 토큰의 역할이 계약 열거와 정확히 같게 하려는 것이다.
- 접근 토큰을 짧게 두고 갱신하는 것은 RFC 6819 의 권고이고, 갱신하지 않으면 5분마다 다시 로그인한다.

## 검토한 대안과 버리는 이유
- **realm 파일 손으로 쓰기(옛 방식):** 노출 선언·기계 호출자가 바뀔 때마다 어긋난다.
- **keycloak-config-cli:** 선언한 realm 을 반복 적용하는 표준 도구지만 컨테이너 하나가 더 필요하고 관리자 비밀번호를 환경 변수로 받는다(D84 와 어긋난다). 대신 `identity sync` 가 Keycloak 의 partialImport(표준 관리 API)와 범위 매핑·서비스 계정 역할 부여(kcadm)를 쓴다.
- **사람 로그인을 화면이 직접(oidc-client):** 브리프가 화면 앞단 로그인(oauth2-proxy)을 정했다.
- **기본 역할을 비우기:** 가져오기가 무시한다(위).

## 결과
- **얻는 것:** realm 이 계약의 역할 이름과 RFC 9068 설정으로 만들어진다. 로그인부터 서비스가 받는 토큰까지를 시험한다.
- **감수하는 것:** 관리자가 사람에게 계약 밖 realm 역할을 주어도 범위 매핑 때문에 토큰에 실리지 않는다. 역할을 더하려면 realm 파일(생성기)을 바꾼다. 기계 토큰은 계약 9.0.0 이 client credentials 의 JWT(RFC 9068)로 확정했고(`MachineIdentityClaims`) 시험이 실제 Keycloak 의 기계 토큰을 이 스키마로 검증한다. `MachineTokenEntry.token_file` 은 `client_secret_file` 로 바뀌었고 platform 은 이 칸의 경로를 읽지 않는다(비밀 파일은 deploy 가 호출자 이름으로 `deploy/secrets/machine-clients/<이름>` 에 만든다).

## 되돌리는 조건
Keycloak 이 RFC 9068 속성을 없애거나 계약의 클레임이 바뀌면 realm 생성기를 고친다.
