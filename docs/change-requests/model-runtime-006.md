# 변경 요청 model-runtime-006: MachineRealmAccessClaim 이 Keycloak 의 기본 역할이 든 토큰을 거절할 수 있다

처리됨(platform a56d244, 영역 55b6689): 기계 클라이언트의 범위를 계약 MachineRole 로 제한한다(Full Scope Allowed 끔, 범위 매핑). 서비스는 계약 모델로 그대로 검증한다. 실제 Keycloak 으로 platform 샌드박스(2f2ab60)가 확인한다.

- 영역: model-runtime
- 대상 계약: `MachineRealmAccessClaim`, `MachineIdentityClaims`(`components.yaml`)
- 상태: 헤드 결정 대기. 영역은 `realm_access.roles` 에서 계약이 아는 `MachineRole` 만 남기고 `MachineIdentityClaims` 로 검증하는 것으로 구현했다(ADR services/model-runtime 0005).

## 문제
`MachineRealmAccessClaim.roles` 의 항목은 `MachineRole` 열거만 허용하고 `additionalProperties: false` 다. Keycloak 의 접근 토큰은 `realm_access.roles` 에 서비스 계정의 역할 말고도 기본 역할(`default-roles-<realm>`, `offline_access`, `uma_authorization` 등)을 싣는 것으로 알려져 있다(Keycloak 문서. **이 작업에서 실제 Keycloak 으로 확인하지는 못했다**). 계약 모델로 토큰 클레임을 그대로 검증하면 정상 토큰이 거절될 수 있다. `UserIdentityClaims` 의 `RealmAccessClaim` 도 같은 모양이다.

## 요청 (제안)
(1) 역할 배열을 열린 문자열 배열로 하고 서비스가 아는 역할만 쓴다고 설명에 적는다. 또는 (2) 기본 역할을 토큰에서 빼는 Keycloak 설정(클라이언트 스코프의 역할 매퍼)을 platform 의 identity 가 보장한다고 정한다. (2)면 계약은 그대로이고 영역의 거르는 코드는 불필요해진다.
