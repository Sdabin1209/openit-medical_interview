# openit v7 계약

영역 사이 교환의 정본이다. 표준 형식만 쓴다.

- **HTTP 교환:** `openapi/<서비스>.yaml`(OpenAPI 3.1)
- **공유 값 정의:** `components.yaml` 한 곳(OpenAPI 3.1 components, 곧 JSON Schema 2020-12). HTTP 밖의 교환(환경 입력, 잡 입력·결과, 턴 기록)도 여기 정의를 쓴다.
- **값마다 갖추는 것:** 뜻(`description`), 범위(`maxLength`·`minimum`·`maximum`·`maxItems`·`enum`+`x-enum-descriptions`), 주인(`x-owner`, `areas.yaml`의 이름), 근거(`x-basis`: 결정 번호·표준·측정).
- **참조만:** 객체의 칸과 요청·응답 본문은 컴포넌트를 `$ref`로 참조만 한다.
- **흐름과의 대응:** `flows.md` 가 영역 사이 흐름 N01~N14(정본은 `../docs/design.md` 3절)에 계약의 작업과 스키마 이름을 연결하고, `traceability.md` 가 흐름마다 참조하는 스키마 전체를 적는다. 옛 흐름 번호 F01~F74 의 행방은 `flows.md` 마지막 표다. 충돌 정리는 `../docs/v7-flow-resolutions.md`(우선)다.

## 영역과 서비스

영역은 7개와 계약의 주인 head 다(`areas.yaml`, ADR 0019). 서비스는 컨테이너 이미지가 하나인 상시 서버의 단위다. 사람 화면은 모두 admin-console 한 앱이다(C01). 상시 서비스의 계약 작업은 아래이고 모든 서비스는 `/healthz`, `/readyz`, `/metrics` 를 낸다(D111).

| 영역 | 종류 | 계약의 HTTP 작업 | 흐름 |
|---|---|---|---|
| survey-service | 상시 서비스 | 문진 세션과 턴, 시작 코드, 직원 알림·웹 푸시·개입, 문진 결과(의사 화면, 병원 시스템의 당겨 가기, FHIR R4 QuestionnaireResponse), 외부 위험 신호 받기, 문항 세트 올리기와 활성화, 실패 사례 검토와 비식별 내보내기 | N01, N02, N05, N06, N08, N09, N14 |
| model-runtime | 상시 서비스 | LoRA-A 추출, LoRA-B 응답 문장, 적재 상태, 모델 패키지 읽기·활성화 승인·롤백 | N03, N04, N07 |
| platform | 상시 서비스 | 표준 프로토콜로 일하므로 건강 상태와 지표뿐이다(사람 인증 OIDC, 사설 CA, 감시, 레지스트리) | N12 |
| model-lab | 학습 파이프라인(잡) | 없다(HTTP 서버가 없다). 잡 입력 환경(`ModelLabEnv`), 모델 패키지(`ModelPackageManifest`, `EvaluationReport`), 데이터셋(`DatasetManifest`)만 정의한다 | N09, N10, N11 |
| kiosk-frontend | 화면 | 건강 상태와 지표뿐이다 | N01, N02 |
| admin-console | 화면 | 건강 상태와 지표뿐이다 | N05, N06, N07 |
| deploy | 도구 | 없다. 잡 선언·환경 입력·이미지 선언·배치 설정만 `components.yaml` 에 정의한다 | N13 |

head 는 영역 사이 값(`x-owner: head`)의 주인이다. boundary-contracts 와 link 는 값의 주인이 아니어서 영역 목록에 없다.

## 계약이 정하는 규칙

- **오류:** 모든 오류 응답은 RFC 9457 Problem Details(`application/problem+json`, `ProblemDetails`)이다. 상태 코드는 RFC 9110 의 뜻을 따르고, 상태 코드로 가를 수 없는 사유는 `reason`(`ProblemReason`)이다. 각 사유 값의 설명에 그 값을 내는 작업이 적혀 있다. 재시도 가능한 오류는 `Retry-After`(초)를, 401 은 `WWW-Authenticate` 를 낸다. FHIR 조회의 오류만 `OperationOutcome` 이다.
- **시각·식별자·검증기:** 시각은 RFC 3339 date-time(`Timestamp`). 서버가 발급하는 식별자는 UUID(RFC 9562), 모델 패키지와 그 파일은 OCI digest(`OciDigest`, OCI Image Spec 1.1 의 `sha256:<소문자 16진수 64자>`)다. JSON Schema 2020-12 에서 `format` 은 기본이 주석이므로 모든 검증기는 format 단언을 켠다(`jsonschema` 의 format checker). 그래서 UUID 에는 `pattern` 과 `maxLength` 를 함께 둔다.
- **목록:** 커서 쪽 나누기(`limit` 기본 30 최대 100, `cursor`).
- **인증(`securitySchemes`는 `components.yaml` 한 곳에 있다):**
  - 사람: OIDC(Keycloak)로 로그인한 JWT 접근 토큰(RFC 9068)이다. 서비스가 서명을 IdP 의 공개 키 집합(JWKS)으로 검증하고 `iss`, `aud`, `exp` 를 확인한다. 읽는 클레임은 `UserIdentityClaims` 이고 그 밖의 클레임은 허용한다. 발급자 주소는 설치처마다 달라 platform 환경 입력(`OPENIT_OIDC_ISSUER_URL`)으로 받는다.
  - 키오스크 기기: mTLS(RFC 8705)다. 영역 게이트웨이가 기기 인증서를 허용 목록으로 검증하고 Envoy 표준 헤더 `X-Forwarded-Client-Cert` 로 서비스에 넘긴다. 게이트웨이는 클라이언트가 보낸 같은 헤더를 지우고 다시 쓰며, 서비스는 게이트웨이와의 mTLS 연결에서 온 요청의 이 헤더만 믿는다. 기기 ID 는 헤더의 Subject CN 이다.
  - 영역 사이: 사설 CA 가 발급한 인증서의 mTLS(`area_mtls`)와 bearer 기계 토큰(`machine_token`)이다. 다른 서버나 설치처 밖의 외부 기계 호출자는 TLS 와 기계 토큰으로 받는 영역의 게이트웨이로 직접 온다(`ExposureAudience.EXTERNAL_MACHINE_TOKEN`).
  - 필요한 역할은 OpenAPI 3.1 의 표준 자리인 작업의 `security` 요구에 역할 이름으로 적는다(`UserRole`, `MachineRole`).
  - 서비스 주소는 `https://<영역 이름>` 이다(D129).
- **세션의 접근:** 세션은 시작한 기기의 ID 로만 접근할 수 있고 다른 기기에는 404 로 존재를 숨긴다(D88 U8).
- **쓰기의 멱등:** 같은 `turn_id`, 같은 기기와 같은 시작 코드, 같은 검토 내용, 이미 활성인 모델 패키지 digest 의 활성화, 같은 세션·분류·감지 시각의 위험 신호는 같은 결과를 낸다. 그 밖의 만들기 작업(시작 코드 발급, 문항 세트 올리기)은 `Idempotency-Key` 헤더(draft-ietf-httpapi-idempotency-key-header)로 재전송을 가린다.
- **시간 상한:** 영역 사이 시간 상한과 폴링·heartbeat 간격은 `TimeBudgetTable` 이 정한다(D125). 값은 목표(SLO)가 아니라 실패 판정 상한이다.
- **컴포넌트가 낸 값은 받는 쪽이 다시 검증하지 않는다**(`ActionExtraction` 은 추론 서버가 `ActionExtractionRules` 의 조건으로 보증, R7).
- **결과의 조회:** 설치처의 의료 정보 시스템은 당겨 가기만 한다(밀어 보내기 없음, C10). FHIR 조회는 HL7 FHIR R4 `QuestionnaireResponse` 를 참조하고, 우리 값과의 대응은 `FhirMapping` 이 정한다.
- **학습 영역에 나가는 사례:** model-lab 은 환자 발화 원문과 모델 출력이 없는 `FailureCaseExport` 만 당겨 간다(N09). 원문(`FailureCase.utterance`)은 검토자 역할에만 나간다(D15, L12).
- **계약 밖의 표준 프로토콜:** 웹 푸시(RFC 8030·8291·8292), 서비스 인증서 발급(ACME RFC 8555, step-ca), 백업 저장소(restic REST), 컨테이너 이미지 배포(OCI Distribution), 가입 신청과 역할 부여(Keycloak). 이들은 표준이 정본이라 이 계약이 작업으로 다시 만들지 않고, 오가는 우리 쪽 값(`PushSubscription`, `WebPushPayload`, `MachineTokenTable`, `BackupSnapshotId` 등)만 정의한다.

## 영역 사이 어휘와 입력

표준이나 데이터셋 정본에 목록이 없는 열거 값(세션 상태, 알림 종류, 기계 역할, 잡 이름 등)은 `../docs/design.md` 4절이 정본이고 스키마의 `x-basis` 가 그 절을 가리킨다. 환경 입력(`*Env`)은 입력마다 필요한 2절 컴포넌트를 description 에 적고, 어느 컴포넌트도 필요로 하지 않는 입력은 두지 않는다. 백업·복구·서버 밖 동기화·복원 시험은 deploy 가 도는 잡이라 그 입력은 영역 Env 가 아니라 deploy 의 배치 설정(`DeploymentLayout.backup`, `DeployBackupConfig`)에 있다. 컨테이너 주입 선언 `ContainerInputs` 는 D134 의 항목(실행 사용자, 환경 입력, 쓰는 경로의 유지 여부와 사용자, 추가 권한, sysctls, 절대 경로 argv)을 모두 담는다. 평가 지표의 시간 단위는 Prometheus 명명 관례의 초다(`MetricUnit`, `length_p95_seconds`).

## 모델 패키지(OCI 아티팩트)

모델 패키지는 레지스트리에 OCI 이미지 매니페스트로 게시한다(OCI Image Spec 1.1, ADR 0019). 게시용 HTTP 작업은 없고 전송은 OCI Distribution 표준이 맡는다. 계약이 정하는 것은 이름과 모양이다.

| 칸 | 값 | 스키마 |
|---|---|---|
| `artifactType` | `application/vnd.openit.model.package.v1` | `ModelPackageArtifactType` |
| config 의 `mediaType` | `application/vnd.openit.model.package.config.v1+json`(내용은 `ModelPackageManifest`) | `ModelPackageBlobMediaType` |
| layer 의 `mediaType` | `application/vnd.openit.model.adapter.weights.v1`(어댑터 가중치), `application/vnd.openit.model.adapter.system-prompt.v1`(시스템 프롬프트) | `ModelPackageBlobMediaType` |
| 패키지의 식별자 | 매니페스트의 digest | `OciDigest` |

매니페스트 전체는 `ModelPackageOciManifest` 이다. 이름은 RFC 6838 3.2 의 공급자 트리(`vnd.`)를 따른 이 계약의 정의다. model-runtime 은 `artifactType` 이 맞지 않는 아티팩트를 모델 패키지로 받지 않고 파일의 digest 를 목록표와 대조한다(422 `PACKAGE_INVALID`).

## 모델 출력의 합격 조건

LoRA-A 출력의 합격 조건은 조건 하나에 위반 코드 하나다(`ViolationCode`). 출력 형식은 `ActionExtraction` 스키마(`OUTPUT_SCHEMA`), 저장 규칙·targets·next_item·현재 문항은 `ActionExtractionRules`(`SAVE_RULE`, `TARGET_NOT_IN_VALUES`, `NEXT_ITEM_MISMATCH`, `OUT_OF_CURRENT_ITEM`), 문항·칸·자료형·선택지·범위는 요청의 순서표와 칸 규격(`UNKNOWN_ITEM`, `UNKNOWN_SLOT`, `VALUE_TYPE_MISMATCH`, `VALUE_NOT_IN_OPTIONS`, `VALUE_OUT_OF_RANGE`)이 정한다. model-runtime 의 출력 검증이 한 번 검사하고 받는 쪽은 다시 검증하지 않는다(R7). 의미 위반율은 값 고쳐 쓰기(D115) 전의 모델 출력으로 센다.

## 모델 입력의 글은 model-runtime 이 만든다

`extractAction` 과 `generateResponse` 의 요청(`ExtractionRequest`, `ResponseGenerationRequest`)은 구조화된 값만 싣는다(ADR 0019 의 책임선, 헤드 결정 2026-11-10, 변경 요청 survey-service-002 의 2안). 데이터셋 정본(`inputs/labels.py`, `IO_SPEC.md`)의 표와 규칙으로 만드는 글은 요청에 없고 model-runtime 의 `prompt` 가 만든다.

| 구분 | 서비스가 보내는 값 | model-runtime 이 만드는 것 |
|---|---|---|
| LoRA-A 입력 | 지금 묻는 문항(`question_id`), 직전에 물은 문항(`previous_question_id`), 화면에 보인 직전 문장(`current_question`), 환자 발화(`user_utterance`), 저장된 칸 값(`slots`) | 입력 객체와 state(지금 문항, 직전에 물은 문항, 참조 원천 문항 REF_SOURCE 의 저장 값을 `slots` 에서 골라 놓는다) |
| LoRA-B 입력 | 행동·사유, A 출력의 `values`·`targets`·`note`, 지금 묻던 문항, 직전에 물은 문항, 발화, 저장된 칸 값, 서비스가 정한 다음 자리(`next` 의 종류와 문항) | `topic`, `known`, `ask`, `previous`, `current`, `hold`, `next.text` |

- 서비스가 보내는 글은 화면에 보인 직전 문장과 환자 발화뿐이다. 둘 다 서비스가 화면에서 이미 아는 글이다.
- **`slots`(저장된 칸 값):** 이번 턴을 반영하기 전에 세션에 저장된 모든 칸 값과 다시 묻는 중인 칸(MISSING·UNCLEAR, 값 null)이다. 서비스는 참조 원천 표(`taxonomy.REF_SOURCE`)를 모르므로 필요한 범위를 고르지 않고 전체를 보낸다. 상한 136은 문항 은행의 칸 수 68(SQL.md 5.2 의 칸 52개 중 술 칸 4개가 술 5종)의 2배이고(`StoredSlots` 의 x-basis), 요청 전체의 크기는 측정하지 않았다. 배열의 순서가 모델 입력 state 의 칸 순서다(D77).
- **저장 값의 정밀도(precision)는 보내지 않는다.** 정본에서 state 의 항목은 값과 상태뿐이고 이전 값(`previous`)은 항상 `exact` 로 쓴다(`labels.py` `a_state`, `previous_text`). 이번 턴에 정해진 값의 정밀도는 A 출력의 `values` 에 있다.
- **지운 스키마:** `ActionExtractionInput`, `CollectedState`, `StateEntry`, `StateStatus`, `StateKeyOrder`, `CurrentQuestionText`, `ResponseRequest`, `TopicText`, `KnownText`, `AskText`, `PreviousValueText`, `CurrentValueText`, `HoldText`. 모델 입력 객체와 글 조각은 영역 사이에 오가지 않고 model-runtime 안에서만 만들어져 쓰인다. 구조 규칙 5 에 따라 영역 안 값은 그 영역의 `types` 가 정의하고, model-runtime 과 model-lab 이 같은 규칙을 쓰는 공유 라이브러리 `libs/model-io` 가 가진다(D97). `CurrentQuestionText` 는 `ResponseSentence` 와 같은 뜻의 같은 상한(344)이라 하나로 합쳤다(D117).
- **계약에 남긴 `ModelInputSerialization`:** 모델 입력의 글자 규칙(키 정렬, 비 ASCII 이스케이프 없음, state 칸 순서)은 model-lab 의 학습 데이터와 model-runtime 의 서빙이 글자까지 같아야 하는 두 영역 사이의 값이라 계약에 둔다(구조 규칙 6). 모델 입력 객체의 칸과 글은 데이터셋 정본이 정한다.
- **정본에 없어 정하지 못한 것:** (1) 참조 원천 표 `taxonomy.REF_SOURCE` 의 내용(정본 입력에는 예 `Q10 -> Q9_1` 하나뿐이다). (2) `next.text` 를 찾을 문항 문장 표(SQL.md 7.3 의 `data/question_bank.json`)를 model-runtime 이 받는 길(계약에는 모델 패키지 목록표나 요청 어디에도 없다). (3) state 의 칸 순서 규칙(OPEN_GAPS G13: `prev_state.py` 의 시나리오 원래 값이 먼저라는 규칙은 서비스가 모른다). 지금은 `slots` 배열의 순서를 그대로 쓴다.

## 모델 입출력의 버전

LoRA-A·LoRA-B 의 입력과 출력은 학습 데이터셋 정의(D74)가 정본이다. 계약에 있는 사본은 LoRA-A 의 출력(`ActionExtraction`과 그 조각)과 모델 입력의 글자 규칙(`ModelInputSerialization`)이고 정본과 글자까지 같다. 모델 입력 객체와 그 글 조각은 계약에 없다(다음 절). 지금의 사본은 **모델 입출력 v2**(`ModelIoVersion` 의 `model-io-v2`, 데이터셋 `dataset_10_29` 와 `labels.py`)다. 모델 패키지(`ModelPackageManifest`)가 이 버전을 싣는다. 확인 중 상태(`confirming`), 질문의 뜻을 묻는 분류(`MEANING_ASKED`) 같은 v2 에 없는 것은 v2 에 넣지 않고 `model-io-v3-proposal.md`(활성이 아님)와 `dataset-change-requests.md` 에만 둔다.

서비스는 적재한 모델 패키지의 모델 입출력 버전에 맞는 모델 통신 컴포넌트로만 모델과 이야기하고, 나머지 컴포넌트는 서비스 내부 타입만 안다. 그 버전을 아는 통신 컴포넌트가 없는 패키지는 적재하지 않는다.

## JWT 접근 토큰 검증 프로파일 (RFC 9068)

사람 호출을 받는 서비스(survey-service, model-runtime)는 아래를 모두 확인하고 하나라도 어기면 401 로 거절한다. 설정은 그 서비스 Env 의 `OPENIT_OIDC_ISSUER_URL`, `OPENIT_OIDC_JWKS_URL`(없으면 발급자의 디스커버리 문서의 `jwks_uri`), `OPENIT_OIDC_AUDIENCE` 로 받는다.

| 확인 | 값 | 근거 |
|---|---|---|
| JOSE 헤더 `typ` | `at+jwt` 또는 `application/at+jwt`(`AccessTokenType`, `AccessTokenHeader`) | RFC 9068 2.1, 4 |
| JOSE 헤더 `alg` | `none` 이 아니다 | RFC 9068 4 |
| 서명 | 발급자의 공개 키 집합(JWKS)으로 검증 | RFC 9068 4, RFC 7517 |
| `iss` | `OPENIT_OIDC_ISSUER_URL` 과 같다 | RFC 9068 4 |
| `aud` | 문자열 또는 배열에 자기 서비스 이름(`OPENIT_OIDC_AUDIENCE`)이 있다. 서비스 이름만 받는 것은 이 프로젝트의 로컬 프로파일이다 | RFC 9068 2.2, 4 |
| `exp`, `iat` | 만료되지 않았고 발급 시각이 있다(`NumericDate`) | RFC 9068 2.2, RFC 7519 |
| `sub`, `client_id`, `jti` | 있다(`UserIdentityClaims`) | RFC 9068 2.2 |
| 역할 | `realm_access.roles` 에 작업이 요구한 `UserRole` 이 있다 | Keycloak, U82 |

서비스가 읽는 클레임은 `UserIdentityClaims` 이고 그 밖의 클레임(scope, azp 등)은 허용한다.

## 모델 입출력 v3 에 의존하는 기능

확인 중 상태의 전달, 질문의 뜻·대상을 묻는 말의 되묻기 한도 면제, 설명 요청이 한 문항에서 3번 이어진 뒤의 직원 도움 안내는 모델 입출력 v3(데이터셋 반영과 재학습)에 의존한다. 모델 입출력 v2 모델로는 서비스가 뜻 묻기를 구분할 수 없으므로 **데이터셋 v3 를 반영하기 전까지 비활성**이다. 활성 조건은 적재한 모델 패키지의 `model_io_version` 이 `model-io-v3` 이상인 것이며 `ModelIoFeatureRequirements` 가 기능마다 정의한다. v3 가 활성이 되기 전의 동작은 되묻기 한도(처음 질문 1회와 되묻기 2회)를 REASK 와 CONFIRM 의 연속으로 세어 서비스가 건너뛰는 것이다.

## 범위의 근거

값의 범위(길이, 개수, 최솟값, 최댓값)는 `x-basis` 에 근거를 적는다. 근거는 다음 순서로 찾았다.

1. **표준**(예: 샘플링 온도 0~2는 OpenAI API 허용 범위, 시작 코드는 RFC 4226 과 NIST SP 800-63B, 기반 모델 이름은 Hugging Face 저장소 이름 규칙).
2. **측정**: 데이터셋 정본(`contracts/inputs` 의 `labels.py`, `SQL.md`, `IO_SPEC.md` 와 학습 서버 final·finaltest 93,429행 재측정)에서 잰 최대값. 상한은 사용자 결정(발화 한 턴 300자: 관측 최대 140자의 약 2배)과 같은 방식으로 관측 최대의 2배로 했다.
3. **사용자 결정**: 표준 조항이 범위를 직접 정하지 않는 값(예를 들어 URI 8000, 시각 35자, 안전한 수 범위)은 사용자 결정(UD-n, `user-decisions-needed.md`)을 근거로 한다.
4. **구조에서 나오는 값**: 열거 값의 수, 칸 수 같은 계약 안의 개수.
5. **결정 기록**의 결정 번호.

위 어느 것에서도 값이 나오지 않은 것은 `user-decisions-needed.md` 에 올려 사용자가 정했고, `x-basis` 는 "사용자 결정 2026-11-10(UD-n)"을 가리킨다.

## 계약의 판과 변경 기록

계약의 판은 Semantic Versioning 2.0.0(MAJOR.MINOR.PATCH)을 따른다. 요청·응답의 모양이 바뀌어 기존 호출자가 깨지면 MAJOR, 하위 호환이 되는 칸·작업·값의 추가는 MINOR, 뜻과 모양이 같은 설명·근거·시험의 고침은 PATCH 를 올린다(SemVer 2.0.0 항목 6~8). 판은 `components.yaml` 과 `openapi/*.yaml` 의 `info.version` 6곳이 같은 값을 갖고, 이미지 라벨 `io.openit.contracts` 의 형식(`ContractsVersionLabel`)이 그 MAJOR 를 가리킨다. 판마다 git 태그 `contracts-vMAJOR.MINOR.PATCH` 를 단다. `package.json` 의 `version` 은 린트·시험 도구 묶음의 값이라 계약의 판과 다르고 올리지 않는다.

### 8.0.0 (2026-11-10, 깨지는 변경)

survey-service-002 의 2안: 모델 입력의 글을 만드는 책임을 model-runtime 으로 옮겼다. 요청 모양이 바뀌어 7.0.0 호출자는 깨진다.

- `ExtractionRequest`: `input`, `state_key_order` 를 지우고 `question_id`, `previous_question_id`(선택), `current_question`, `user_utterance`, `slots` 를 더했다. `runtime_contract_version`, `flow`, `fields` 는 그대로다.
- `ResponseGenerationRequest`: `input`(`ResponseRequest`)을 지우고 `action`, `reason`, `question_id`, `previous_question_id`, `user_utterance`, `slots`, `values`, `targets`, `note`, `next` 를 본문 칸으로 올렸다(START 에는 `action` 과 `next` 만). `topic`, `known`, `ask`, `previous`, `current`, `hold` 가 없어졌다.
- `ResponseNext`: `text` 를 지웠다(질문 문장은 model-runtime 이 `question_id` 로 찾는다).
- 더한 스키마: `StoredSlotStatus`, `StoredSlot`, `StoredSlots`(저장된 칸 값, 상한 136).
- 지운 스키마: 위 '모델 입력의 글은 model-runtime 이 만든다' 절의 목록 13개.
- `ModelInputSerialization`, `InsertionOrder` 의 설명을 요청 `slots` 배열의 순서로 고쳤다. `ContractsVersionLabel` 의 형식을 8.x.y 로 바꿨다. `JsonPointer` 의 예를 새 요청의 위치(`/user_utterance`)로 고쳤다.
- 영향: survey-service 의 `link_model_client`·`turn`, model-runtime 의 `link_api`·`prompt`, `libs/model-io`(`ActionExtractionInput` 을 생성해 쓰던 설정), 그 계약 타입 생성물, 배포의 계약 태그.

### 7.0.0

ADR 0019 의 영역 7개 구성으로 만든 판. 태그 `contracts-v7.0.0`.

## 점검

```
npx spectral lint -r lint/ruleset.yaml components.yaml openapi/*.yaml   # 계약 린트(표준 spectral:oas + openit 규칙 + 예시 검증)
node --test lint/tests/*.test.mjs                                              # 규칙이 위반을 잡는지, 거부해야 할 값을 실제로 거부하는지(ajv)
```

린트는 오류 0, 경고 0 이다. `lint/ruleset.yaml` 의 `overrides` 가 두 곳에서 표준 규칙을 끈다(사유는 규칙 파일 주석). `components.yaml` 에는 `oas3-unused-component` 와 `oas3-api-servers` 를 끈다. 이 파일은 서비스 문서가 아니라 공유 값 라이브러리라서 같은 문서 안의 참조 수와 서버 주소가 없기 때문이다. `openapi/*.yaml` 에는 `oas3-operation-security-defined` 를 끈다. 이 규칙은 보안 요구의 값을 oauth2 의 scope 로만 읽는데 OpenAPI 3.1.0 4.8.30 은 그 밖의 체계에서 필요한 역할 이름 목록으로 쓰도록 허용하기 때문이다.

코드 타입은 표준 생성기로 만든다: Python `datamodel-code-generator`, TypeScript `openapi-typescript`. 생성물은 고치지 않는다.
