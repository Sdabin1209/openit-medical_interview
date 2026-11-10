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
- **인증(`securitySchemes`):** 키오스크 기기는 mTLS(`device_mtls`), 사람은 OIDC(`oidc`, Keycloak이 발급한 JWT bearer, 필요한 `UserRole` 은 `x-required-roles.oidc`), 영역 사이는 bearer 기계 토큰(`machine_token`, 필요한 `MachineRole` 은 `x-required-roles.machine_token`)이다. OIDC 발급자 주소는 설치처마다 달라 계약에 적지 않고 platform 환경 입력(`OPENIT_OIDC_ISSUER_URL`)으로 받는다. 서비스 주소는 `https://<영역 이름>` 이다(D129).
- **쓰기의 멱등:** 같은 `turn_id` 재전송, 같은 세션·턴의 기록 전달, 같은 검토 내용, 같은 파일 올리기는 같은 결과를 낸다.
- **컴포넌트가 낸 값은 받는 쪽이 다시 검증하지 않는다**(`ActionExtraction` 은 추론 서버가 보증, R7).
- **결과의 조회:** 병원 시스템은 당겨 가기만 한다(밀어 보내기 없음, C10). FHIR 조회는 HL7 FHIR R4 `QuestionnaireResponse` 를 참조하고 다시 정의하지 않는다.
- **계약 밖의 표준 프로토콜:** 웹 푸시(RFC 8030·8291·8292), 서비스 인증서 발급(ACME RFC 8555, step-ca), 백업 저장소(restic REST), 컨테이너 이미지 배포(OCI Distribution), 가입 신청과 역할 부여(Keycloak). 이들은 표준이 정본이라 이 계약이 작업으로 다시 만들지 않고, 오가는 우리 쪽 값(`PushSubscription`, `WebPushPayload`, `MachineTokenTable`, `BackupSnapshotId` 등)만 정의한다.

## 범위의 근거

값의 범위(길이, 개수, 최솟값, 최댓값)는 `x-basis` 에 근거를 적는다. 근거는 다음 순서로 찾았다.

1. **표준**(예: 식별 이름 63자는 RFC 1035 레이블, 샘플링 온도 0~2는 OpenAI API 허용 범위, 시작 코드는 RFC 4226·NIST SP 800-63B).
2. **측정**: 데이터셋 정본(학습 서버의 `labels.py`, `SQL.md`, 학습 파일 `lora_a_train.jsonl`·`lora_b_train.jsonl`, 어댑터 파일 크기)에서 잰 최대값. 상한은 사용자 결정(발화 한 턴 300자: 관측 최대 140자의 약 2배)과 같은 방식으로 관측 최대의 2배로 했다.
3. **결정 기록**의 결정 번호.

셋 다 없는 값은 `user-decisions-needed.md` 에 올렸다. 린트가 상한을 요구하므로 그 값은 권고값으로 넣었고 `x-basis` 가 해당 UD 번호를 가리킨다. 데이터셋에 없는 v7 신규 값(확인 중 상태, MEANING_ASKED, REASK_LIMIT, 직원 도움 안내)은 계약에 넣고 `dataset-change-requests.md` 에 "데이터셋에 필요한 변경"으로 적었다.

## 점검

```
npx spectral lint -r lint/ruleset.yaml components.yaml openapi/*.yaml   # 계약 린트(표준 spectral:oas + openit 규칙)
node --test lint/tests/*.test.mjs                                              # 규칙이 위반을 실제로 잡는지
```

린트는 오류 0, 경고 0 이다. `lint/ruleset.yaml` 의 `overrides` 가 `components.yaml` 에만 두 표준 규칙(`oas3-unused-component`, `oas3-api-servers`)을 끈다. 이 파일은 서비스 문서가 아니라 공유 값 라이브러리라서 같은 문서 안의 참조 수와 서버 주소가 없기 때문이다(사유는 규칙 파일 주석). 작업의 필요한 역할은 `security` 가 아니라 확장 필드 `x-required-roles` 에 적는다.

코드 타입은 표준 생성기로 만든다: Python `datamodel-code-generator`, TypeScript `openapi-typescript`. 생성물은 고치지 않는다.
