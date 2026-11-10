# openit v7 계약

영역 사이 교환의 정본이다. 표준 형식만 쓴다.

- **HTTP 교환:** `openapi/<서비스>.yaml`(OpenAPI 3.1)
- **공유 값 정의:** `components.yaml` 한 곳(OpenAPI 3.1 components, 곧 JSON Schema 2020-12). HTTP 밖의 교환(환경 입력, 잡 입력·결과, 턴 기록)도 여기 정의를 쓴다.
- **값마다 갖추는 것:** 뜻(`description`), 범위(`maxLength`·`minimum`·`maximum`·`maxItems`·`enum`+`x-enum-descriptions`), 주인(`x-owner`, `areas.yaml`의 이름), 근거(`x-basis`: 결정 번호·표준·측정, 또는 `결정 대기: …`).
- **참조만:** 객체의 칸과 요청·응답 본문은 컴포넌트를 `$ref`로 참조만 한다.
- **흐름과의 대응:** `traceability.md`가 흐름 F01~F74 각각이 어느 작업·스키마로 구현되는지(또는 왜 구현하지 않는지) 적는다. 흐름의 정본은 `flows.md`, 충돌 정리는 `../docs/v7-flow-resolutions.md`(우선)다.

## 서비스 목록

서비스는 컨테이너 이미지가 하나인 단위다(ADR 0002). 사람 화면은 모두 admin-console 한 앱이다(C01). 추론 서버는 model-runtime 소유이며 활성 릴리스를 스스로 읽어 적재한다(C05). 모든 서비스는 `/healthz`, `/readyz`, `/metrics` 를 낸다(D111, F58).

| 서비스 | 소유 영역 | 하는 일 | 근거 흐름 |
|---|---|---|---|
| survey-service | survey-service | 문진 세션과 턴 진행, 일회용 시작 코드 발급·사용, 직원 알림·웹 푸시·개입, 문진 결과(의사 화면, 병원 시스템의 당겨 가기, FHIR R4 QuestionnaireResponse 조회), 외부 위험 신호 받기, 턴 기록 만들기 | F25, F29~F32, F37~F42, F44 |
| release-gate | release-gate | 후보 목록, 출고 제출과 자동 검사, 검토 보고서, 사람 승인, 릴리스 활성화·롤백, 활성 릴리스와 모델 패키지 읽기, 게이트 판정 읽기, 롤백 요청 | F05~F14, F47 |
| question-authoring | question-authoring | 문항 자료 올리기와 화면 입력, 초안 미리보기, 저자 확인, 선택적 임상 승인, 후보와 문항 정의 읽기, 개선 신호 읽기 | F01~F04, F15, F16, F22 |
| ops-feedback | ops-feedback | 턴 기록 수집(멱등), 실패 사례 읽기와 검토 결과 게시, 비식별 턴 기록, 문항별 실패 신호 | F19~F21, F36, F45, F46 |
| model-runtime | model-runtime | 활성 릴리스를 읽어 적재한 모델로 LoRA-A 추출과 LoRA-B 응답 생성, 모델 적재 상태 | F12, F33~F35 |
| model-lab | model-lab | 후보 모델 패키지(어댑터, 시스템 프롬프트, 계보, 평가 보고서)와 파일 읽기, 학습 서버의 학습 결과 게시 | F07, F66, F67 |
| synthetic-data | synthetic-data | 게시된 데이터셋 읽기, 데이터셋 담당의 최종 데이터 가져오기와 게시 | F17, F18 |
| platform | platform | 공개 입구, 사람 인증(OIDC, Keycloak), 사설 CA, 감시, 백업 저장소. 표준 프로토콜로 일하므로 이 계약의 HTTP 작업은 건강 상태뿐이다 | F28, F50~F53, F57, F58 |
| kiosk-frontend | kiosk-frontend | 환자가 쓰는 키오스크 화면(정적). 서버 작업 없음 | F23, F24, F26 |
| admin-console | admin-console | 직원·의사·저자·검수자·검토자·승인자·운영자의 모든 업무 화면(정적). 서버 작업 없음 | F43, F48, F49 |

서비스가 아닌 영역(head, boundary-contracts, link, deploy)은 HTTP 작업이 없다. deploy 는 잡 선언·환경 입력·이미지 선언·배치 설정만 `components.yaml` 에 정의한다(F54~F56, F60, F64).

## 계약이 정하는 규칙

- **오류:** 모든 오류 응답은 RFC 9457 Problem Details(`application/problem+json`, `ProblemDetails`)이다. 상태 코드는 RFC 9110 의 뜻을 따르고, 상태 코드로 가를 수 없는 사유는 `reason`(`ProblemReason`)이다. 재시도 가능한 오류는 `Retry-After`(초)를 낸다.
- **시각:** RFC 3339 date-time(`Timestamp`). **식별자:** 서버가 발급하는 것은 UUID(RFC 9562), 사람이 정하는 것은 `pattern` 과 길이가 있는 문자열이다.
- **목록:** 커서 쪽 나누기(`limit` 기본 30 최대 100, `cursor`). 최대값의 근거는 `PageLimit` 의 `x-basis` 에 있다.
- **인증(`securitySchemes`):** 키오스크 기기는 mTLS(`device_mtls`), 사람은 OIDC(`oidc`, Keycloak, 요구 값은 `UserRole` 역할 이름), 영역 사이는 bearer 기계 토큰(`machine_token`, 요구 값은 `MachineRole` 권한 이름)이다. 서비스 주소는 `https://<영역 이름>` 이다(D129).
- **쓰기의 멱등:** 같은 `turn_id` 재전송, 같은 세션·턴의 기록 전달, 같은 검토 내용, 같은 파일 올리기는 같은 결과를 낸다.
- **컴포넌트가 낸 값은 받는 쪽이 다시 검증하지 않는다**(`ActionExtraction` 은 추론 서버가 보증, R7).
- **결과의 조회:** 병원 시스템은 당겨 가기만 한다(밀어 보내기 없음, C10). FHIR 조회는 HL7 FHIR R4 `QuestionnaireResponse` 를 참조하고 다시 정의하지 않는다.
- **계약 밖의 표준 프로토콜:** 웹 푸시(RFC 8030·8291·8292), 서비스 인증서 발급(ACME RFC 8555, step-ca), 백업 저장소(restic REST), 컨테이너 이미지 배포(OCI Distribution), 가입 신청과 역할 부여(Keycloak). 이들은 표준이 정본이라 이 계약이 작업으로 다시 만들지 않고, 오가는 우리 쪽 값(`PushSubscription`, `WebPushPayload`, `MachineTokenTable`, `BackupSnapshotId` 등)만 정의한다.

## 길이·개수 규칙

표준이나 측정에서 값이 나오지 않는 문자열 길이와 목록 개수는 아래 단계로 통일한다. 이 단계 자체는 측정·표준 근거가 없는 계약의 구분 규칙이다(근거 없음 목록에 올림). 값마다 표준이나 결정이 있으면 `x-basis` 에 그것을 적었다.

| 규칙 | 값 | 쓰임 |
|---|---|---|
| L1 | 문자열 64자 | 식별 이름·코드 |
| L2 | 문자열 200자 | 제목·짧은 이름 |
| L3 | 문자열 1000자 | 문장·URI 한 줄 설명 |
| L4 | 문자열 4000자 | 사유·설명 본문 |
| L5 | 문자열 20000자 | 사람이 읽는 미리보기 |
| N1 | 목록 32개 | 작은 목록 |
| N2 | 목록 100개 | 쪽 나누기 한 쪽(`PageLimit` 최대값과 같다) |
| N3 | 목록 1000개 | 문항·칸 같은 큰 목록 |

## 점검

```
npx spectral lint -r lint/ruleset.yaml components.yaml openapi/*.yaml   # 계약 린트(표준 spectral:oas + openit 규칙)
node --test lint/tests/*.test.mjs                                              # 규칙이 위반을 실제로 잡는지
```

린트 경고 중 `oas3-unused-component` 는 `components.yaml` 의 값을 다른 문서(서비스 openapi)가 참조하는 구조에서 나오고, `oas3-operation-security-defined` 는 보안 요구 값에 역할 이름을 적는 OpenAPI 허용 방식(oauth2 가 아닌 체계의 role 이름 배열)에서 나온다. 둘 다 규칙 위반이 아니다.

코드 타입은 표준 생성기로 만든다: Python `datamodel-code-generator`, TypeScript `openapi-typescript`. 생성물은 고치지 않는다.
