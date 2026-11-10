# 독립 검토 85건의 처리

ADR 0019 개정으로 대상 일부가 없어짐: 아래 85건의 검토가 다룬 release-gate·ops-feedback·question-authoring·synthetic-data 영역과 model-lab 서버의 스키마·작업은 계약에서 지워졌다(그 처리 줄은 당시의 기록으로 남긴다). 이번 개정의 대조 결과(NoneCommit/audit-out/A.md·B.md·C.md의 OK 가 아닌 250항목)의 처리는 맨 아래 "대조 결과 처리(ADR 0019 개정)" 절에 있다.

검토 파일은 `NoneCommit/review-contract-opus.md`(번호 1~57), `NoneCommit/review-contract-codex.md`(번호 C1~C20), `NoneCommit/review-contract-codex-2.md`(번호 E1~E8)다. 증거 칸은 이 문서를 만든 시점의 파일 위치(파일:줄)와 계약 시험 이름이며, 위치는 스크립트가 파일을 찾아 적었다. 증거를 대지 못하는 항목은 "고침"으로 적지 않았다.

처리 수: 고침 76, 일부 고침 8, 재현 불가 1, 고치지 않음 0 (합계 85).

| 번호 | 처리 | 내용 | 증거 |
|---|---|---|---|
| 1 | 고침 | `ActionReason` 에 `CONFLICT_DOES_NOT_DRINK` 를 넣어 정본 20종과 같게 했고 근거를 실측 범위로 고쳤다 | components.yaml:1143 |
| 2 | 고침 | `PauseReason` 과 `AlertKind` 에서 되묻기 초과를 지웠고 `ReaskLimit` 근거를 사용자 결정 U36 으로 바꿨다 | components.yaml:410; components.yaml:2521 |
| 3 | 고침 | 기계 독자용 `FailureCaseExport` 와 `listFailureCaseExports` 를 만들고 원문 작업에서 기계 토큰을 뺐다 | components.yaml:1651; openapi/ops-feedback.yaml:55; 시험 "실패 사례: 기계 독자용 모양에는 발화 원문이 없고, CONFIRMED …"; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| 4 | 고침 | JWT 서명은 서비스가 JWKS 로 검증하고(RFC 9068) 기기 신원은 `X-Forwarded-Client-Cert` 로 넘긴다. 영역 사이는 mTLS 와 기계 토큰이다 | components.yaml:324; components.yaml:3029; components.yaml:3012; 시험 "JWT 클레임은 RFC 9068 필수 클레임이 빠지면 거부하고 그 밖의 …" |
| 5 | 고침 | v2 사본에서 v3 값을 빼고 `ModelIoVersion` 을 릴리스·패키지에 싣고 v3 후보는 별도 문서로 뒀다 | components.yaml:1060; model-io-v3-proposal.md:1; 시험 "모델 패키지: LORA_A 와 LORA_B 가 하나씩이 아니면 거부한다…" |
| 6 | 고침 | `ResponseRequest`, `ActionExtraction`, `ExtractedValue`, `ResponseNext`, `CaseReview` 에 조건부 필수를 넣었다 | components.yaml:1304; 시험 "ResponseRequest: 정본 행은 받고 행동별 필수·금지 키와 n…"; 시험 "ActionExtraction: 정본 행은 받고 행동별 reason·ta…" |
| 7 | 고침 | `ModelInputSerialization` 과 요청의 `state_key_order` 를 정의하고 데이터셋 불일치를 DC-05·DC-06 으로 올렸다 | components.yaml:1111; components.yaml:1226; dataset-change-requests.md:11 |
| 8 | 고침 | `ActionExtractionRules` 를 정의하고 save·precision 규칙을 `ExtractedValue` 스키마로 옮겼다 | components.yaml:1096; 시험 "ExtractedValue: save 와 status, 값 없음과 pre…" |
| 9 | 고침 | `ReaskLimit` 이 세는 대상을 정의하고 v3 의존 기능은 `ModelIoFeatureRequirements` 와 README 에 비활성 조건으로 적었다 | components.yaml:2521; components.yaml:1047; README.md:72; 시험 "모델 입출력 v3 의존 기능은 v3 이상에서만 켜진다고 표로 정의한다…" |
| 10 | 고침 | 문항·칸·순서표의 x-owner 를 survey-service 로, 모델 입출력 값은 head 로 바꿨다 | components.yaml:701; components.yaml:1060 |
| 11 | 고침 | `DevicePlacementTable` 과 `SURVEY_DEVICE_PLACEMENTS_FILE` 을 survey-service 입력으로 두고 키오스크 설정 입력을 지웠다 | components.yaml:2538; components.yaml:2581 |
| 12 | 고침 | 세션을 시작한 기기의 ID 로만 접근하게 하고 다른 기기에는 404 로 숨긴다 | openapi/survey-service.yaml:84; README.md:41 |
| 13 | 고침 | startSession 에 429, 422, 409 와 같은 기기의 재시작 멱등을 정의했다 | openapi/survey-service.yaml:73; openapi/survey-service.yaml:72 |
| 14 | 고침 | `Idempotency-Key` 를 4개 만들기 작업에 두고 위험 신호와 시작은 자연 키를 쓴다 | components.yaml:3040; openapi/release-gate.yaml:183; 시험 "작업: 멱등 키는 필요한 작업에만 있고 위험 신호는 자연 키를 쓴다…" |
| 15 | 고침 | `createRollbackRequest` 에 reviewer 와 operator 의 oidc 대안을 두고 자동 제출 설정을 더했다 | openapi/release-gate.yaml:308; components.yaml:2643; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| 16 | 고침 | 후보는 필요한 승인이 끝난 버전만 나온다는 규칙을 정의했다 | components.yaml:826 |
| 17 | 고침 | `Exposure.egress` 가 `EgressTarget`(서비스 또는 외부 호스트와 포트)을 참조하고 상한이 32다 | components.yaml:2888; 시험 "구조의 숫자가 서로 맞는다(같은 구조에서 산출)…" |
| 18 | 고침 | `EXTERNAL_MACHINE_TOKEN` 대상을 더하고 외부 기계 호출자는 영역 게이트웨이로 직접 온다고 정했다 | components.yaml:2839 |
| 19 | 고침 | 모든 서비스 Env 에 루트 인증서와 서비스 인증서·키 파일 입력을 넣었다 | components.yaml:2548; components.yaml:2561 |
| 20 | 고침 | 영역별 백업 자격·암호화 키 파일과 `OFFSITE_SYNC`·`RESTORE_TEST` 잡을 넣었다 | components.yaml:2579; components.yaml:2441 |
| 21 | 고침 | `PlatformEnv` 에 admin 비밀번호, 경보 수신처, 노출 선언 폴더, CA 와 인증서 방식을 넣었다 | components.yaml:2807; components.yaml:2818 |
| 22 | 고침 | `TimeBudgetTable` 과 값별 상수(유휴 초기화 60초 포함)를 정의했다 | components.yaml:103; components.yaml:83 |
| 23 | 고침 | 역할을 `security` 표준 자리에 쓰고 표준 규칙 하나만 사유와 함께 껐다 | lint/ruleset.yaml:112; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| 24 | 고침 | 건강 본문의 미디어 유형을 application/json 으로 바꾸고 자체 모양이라고 적었다 | components.yaml:171; openapi/platform.yaml:25 |
| 25 | 일부 고침 | format 단언 규칙을 README 에 적고 모든 uuid 에 pattern 과 maxLength 를 뒀다. openit 린트 규칙은 바꾸지 않았다 | README.md:33; 시험 "구조의 숫자가 서로 맞는다(같은 구조에서 산출)…" |
| 26 | 고침 | `ProblemReason` 을 쓰이는 20개로 정하고 각 값에 내는 작업을 적었다 | components.yaml:35 |
| 27 | 일부 고침 | `SubjectRef` 에 pattern 을 넣었다. query 값은 식별 정보가 아닌 불투명 참조값이라 GET 을 유지했다 | components.yaml:367 |
| 28 | 고침 | `FhirMapping` 과 OperationOutcome 오류를 정의했다 | components.yaml:1502; components.yaml:2547 |
| 29 | 고침 | 추출·응답 요청에 `release_id` 를 싣고 응답에 처리한 릴리스를 담는다 | components.yaml:1235 |
| 30 | 고침 | 사용자 결정 UD-16 에 따라 학습 서버가 당겨 가는 작업을 만들었다 | openapi/model-lab.yaml:68 |
| 31 | 고침 | 쪽이 아닌 목록은 UD-10, 식별 이름은 UD-14 로 근거를 바꾸고 RetryAfter 와 MetricValue 를 고쳤다 | components.yaml:76; components.yaml:1839 |
| 32 | 고침 | `DeploymentLayout.servers` 상한을 서비스 수 10 으로 하고 근거를 UD-15 로 적었다 | components.yaml:2996 |
| 33 | 고침 | `SlotNumber` 를 안전한 수 범위로 넓혔다 | components.yaml:647 |
| 34 | 고침 | `DatasetFileSet` 을 더하고 `DatasetFiles` 를 8개로 했다 | components.yaml:1999; components.yaml:2019 |
| 35 | 고침 | `BlankReason.NOT_ASKED` 와 사유 대응을 정의했다 | components.yaml:1373 |
| 36 | 고침 | 사용자 결정 UD-12 에 따라 음성 출력도 기기 안에서만 처리한다고 적었다 | components.yaml:394 |
| 37 | 고침 | `ImageLabelSet` 에 라벨 키를 정의했다 | components.yaml:2951 |
| 38 | 고침 | 공유 응답·보안·매개변수 정의를 components.yaml 한 곳에 뒀다 | components.yaml:2999; components.yaml:3053; 시험 "작업: 역할을 요구하면 403 이 있고 401 에는 WWW-Authent…" |
| 39 | 고침 | flows.md 의 영역 수를 12로 고쳤다 | flows.md:20 |
| 40 | 고침 | 202 를 201 과 200 으로 바꿨다 | openapi/survey-service.yaml:147 |
| 41 | 고침 | `Unauthorized` 에 WWW-Authenticate 헤더를 정의했다 | components.yaml:3050; 시험 "작업: 역할을 요구하면 403 이 있고 401 에는 WWW-Authent…" |
| 42 | 고침 | 빈 설명을 보강했다 | components.yaml:2038 |
| 43 | 고침 | `HostAddress`, `DeidentifiedUtterance`, `PassFail` 으로 나누거나 합쳤다 | components.yaml:2530; components.yaml:2180 |
| 44 | 고침 | `SlotText` 갈래를 더했다 | components.yaml:991 |
| 45 | 고침 | GateChecks 5, DeliveryCount 200 으로 맞추고 TTL 근거와 기본 300초를 적었다 | components.yaml:2199; components.yaml:1600; components.yaml:2520 |
| 46 | 고침 | 구조상 최대값을 그대로 썼다(68, 14, 21) | components.yaml:1414; components.yaml:285 |
| 47 | 고침 | `HostAddress` 가 IPv4 와 IPv6 를 받는다 | components.yaml:2529 |
| 48 | 고침 | `ProblemType` 을 절대 URI 로 정했다 | components.yaml:17 |
| 49 | 고침 | 스트림 설명에 data 모양과 heartbeat 간격을 적었다 | openapi/survey-service.yaml:195 |
| 50 | 고침 | 표현을 "설치처의 의료 정보 시스템" 으로 바꿨다 | components.yaml:247 |
| 51 | 고침 | `ArtifactId` 설명에 올리는 쪽이 만든 UUID 라고 적었다 | components.yaml:1732 |
| 52 | 일부 고침 | 업로드에 `Repr-Digest` 와 413 을 더했다. maxLength 는 린트 요구로 남겼다 | components.yaml:3034; openapi/model-lab.yaml:139; 시험 "작업: 업로드에는 Repr-Digest 와 413 이 있다…" |
| 53 | 고침 | `DatabaseUrl` 을 `postgresql://` 만 받게 했다 | components.yaml:2516 |
| 54 | 고침 | `TraceDelivery` 에 `minProperties: 1` 을 뒀다 | components.yaml:1593 |
| 55 | 고침 | `BusinessLogEntry` 에 `actor_client` 와 읽기 사건 종류를 더했다 | components.yaml:1581; components.yaml:1564 |
| 56 | 고침 | `CaseReview.base_case_version` 을 필수로 했다 | components.yaml:1698; 시험 "실패 사례: 기계 독자용 모양에는 발화 원문이 없고, CONFIRMED …" |
| 57 | 고침 | DC-05~DC-08 을 더했고 F37 은 UD-18 로 정리했다 | dataset-change-requests.md:14; traceability.md:43 |
| C1 | 고침 | `ReprDigestValue` 의 최대 길이를 54 로 고치고 RFC 9530 의 실제 헤더 값으로 검증한다 | components.yaml:184; 시험 "Repr-Digest: RFC 9530 의 실제 예시를 받고 길이가 어긋…" |
| C2 | 고침 | `listFailureCases`·`getFailureCase` 에서 기계 토큰을 뺐다(검토자만) | openapi/ops-feedback.yaml:36; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| C3 | 고침 | `Exposure.egress` 가 `EgressTarget` 을 참조하고 상한 32다(앞선 기록과 달리 이번에 파일에 반영) | components.yaml:2888; 시험 "구조의 숫자가 서로 맞는다(같은 구조에서 산출)…" |
| C4 | 고침 | 대체 역할마다 별도 Security Requirement Object 로 나눴다 | openapi/survey-service.yaml:180; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| C5 | 고침 | `createRollbackRequest` 에 reviewer·operator 의 oidc 대안을 더했다 | openapi/release-gate.yaml:308; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| C6 | 고침 | JWT 검증 설정(발급자, JWKS, 허용 aud)을 검증하는 서비스 Env 4개에 뒀다 | components.yaml:2558; components.yaml:2557 |
| C7 | 고침 | START 와 행동별 필수·금지 키와 next 조합을 스키마에 넣었다. 학습 서버 final·finaltest 의 LoRA-A 입력·출력 46,655행과 LoRA-B 입력·응답 46,774행(합계 93,429행, 읽기만)을 계약 스키마로 검증해 어긴 행이 0임을 확인했다 | components.yaml:1320; 시험 "ResponseRequest: 정본 행은 받고 행동별 필수·금지 키와 n…"; 시험 "ActionExtraction: 정본 행은 받고 행동별 reason·ta…" |
| C8 | 일부 고침 | FHIR 공식 JSON Schema(HL7 R4, CC0)를 시험에 연결해 우리 대응 규칙의 예시와 자료형·코드 부정 사례를 검증한다. 공식 스키마는 필수 칸(1..1)을 강제하지 않아(status 없음도 통과) 필수 칸은 계약 스키마가 더하며, FHIR 검증기(필수 칸·불변식 전체)는 연결하지 않았다 | components.yaml:1460; lint/tests/fixtures/fhir/README.md:6; 시험 "FHIR R4 공식 스키마: 우리 대응 규칙대로 만든 Questionna…"; 시험 "FHIR R4 공식 스키마: 자료형이 틀린 답과 잘못된 코드를 거부한다…"; 시험 "FHIR R4: 공식 JSON Schema 는 필수 칸(1..1)을 강제…" |
| C9 | 고침 | v3 의존 기능의 비활성과 활성 조건을 README 와 결정 문서에 적고 계약 표로 뒀다 | README.md:72; ../docs/v7-flow-resolutions.md:51; components.yaml:1047; 시험 "모델 입출력 v3 의존 기능은 v3 이상에서만 켜진다고 표로 정의한다…" |
| C10 | 고침 | `ResultBlank` 가 반복 키를 포함한 칸 참조 `key` 를 쓴다 | components.yaml:1397; 시험 "결과 빈칸은 반복 키까지 칸을 가린다…" |
| C11 | 고침 | `DatasetImport.pending_artifact_ids` 를 8로, 환경 입력 선언 상한을 칸 수 이상으로 맞췄다 | components.yaml:2081; 시험 "구조의 숫자가 서로 맞는다(같은 구조에서 산출)…" |
| C12 | 고침 | 어댑터 구성, 성공한 학습 결과, CONFIRMED 사례, 비율 단위 값의 불변조건을 스키마에 넣었다 | components.yaml:1907; 시험 "모델 패키지: LORA_A 와 LORA_B 가 하나씩이 아니면 거부한다…"; 시험 "학습 결과: 성공인데 어댑터나 실행 기록이 없으면 거부한다…"; 시험 "지표: 비율 단위의 값은 1 을 넘으면 거부한다…" |
| C13 | 고침 | `BusinessEventId` 와 필수 session_id·행위자 조건을 넣었다 | components.yaml:1568; 시험 "업무 로그: event_id 가 없거나 필요한 행위자가 없으면 거부한다…" |
| C14 | 일부 고침 | 필수 지표의 계산식·단위·분모와 slice 표기(기준=값)를 정의했다. 위반 코드(ViolationCode)는 정본에 이름이 있는 5개만 두었고 코드마다의 판정 규칙은 정본에 정의가 없어 정하지 못했다 | components.yaml:1772; components.yaml:1810; components.yaml:1831; components.yaml:1824; 시험 "지표 slice 는 기준=값 표기만 받고 위반 코드는 정본에 이름이 있는…" |
| C15 | 고침 | 위험 신호의 멱등 키 참조를 지우고 FHIR 401·503 에 헤더를 뒀다 | components.yaml:3088; components.yaml:3092; 시험 "작업: 멱등 키는 필요한 작업에만 있고 위험 신호는 자연 키를 쓴다…"; 시험 "작업: 역할을 요구하면 403 이 있고 401 에는 WWW-Authent…" |
| C16 | 고침 | 표준이 범위를 정하지 않는 값은 사용자 결정(UD-19~UD-22)을 근거로 하고 63·18 계산을 바로잡았다 | components.yaml:16; components.yaml:265; components.yaml:637; user-decisions-needed.md:53 |
| C17 | 고침 | RFC 9068 프로파일(typ 은 at+jwt 와 application/at+jwt 둘 다, 필수 클레임, aud 배열과 로컬 프로파일)을 스키마와 README 표로 정의했다 | components.yaml:303; components.yaml:314; README.md:55; 시험 "JOSE 헤더: typ 이 at+jwt 또는 application/at+…" |
| C18 | 고침 | `ObservationCount` 로 합치고 `TokenAudience` 를 `ServiceName` 참조로 바꾸고 설명을 보충했다 | components.yaml:928; components.yaml:296 |
| C19 | 일부 고침 | `JsonPointer` 를 RFC 6901 5 로 고치고 삭제된 "되묻기 초과" 문구를 지웠다. RFC 9457 의 title 3.1.3, status 3.1.2 는 RFC 원문으로 확인해 그대로 뒀다 | components.yaml:49; components.yaml:19 |
| C20 | 고침 | 이 문서를 현재 파일 기준의 증거(파일:줄, 시험 이름)로 다시 썼고 package.json 설명을 고쳤다. 일부만 해결한 항목은 일부로 적었다 | package.json:4 |
| E1 | 고침 | `AccessTokenType` 이 `at+jwt` 와 `application/at+jwt` 를 모두 받는다 | components.yaml:305; README.md:61; 시험 "JOSE 헤더: typ 이 at+jwt 또는 application/at+…" |
| E2 | 일부 고침 | HL7 공식 FHIR R4 JSON Schema(CC0)를 시험에 연결해 QuestionnaireResponse·OperationOutcome 예시와 자료형·코드 부정 사례를 검증한다. 공식 스키마가 필수 칸을 강제하지 않는 한계는 시험으로 기록하고 계약 스키마가 보완한다 | lint/tests/fixtures/fhir/README.md:6; 시험 "FHIR R4 공식 스키마: 우리 대응 규칙대로 만든 Questionna…"; 시험 "FHIR R4 공식 스키마: 자료형이 틀린 답과 잘못된 코드를 거부한다…"; 시험 "FHIR R4: 공식 JSON Schema 는 필수 칸(1..1)을 강제…" |
| E3 | 일부 고침 | `MetricSliceDimension`(slice 표기 기준=값)과 `ViolationCode`(정본에 이름이 있는 5개)를 정의했다. 코드마다의 판정 규칙과 완전한 코드 집합은 정본에 없어 정하지 못했다 | components.yaml:1831; components.yaml:1838; 시험 "지표 slice 는 기준=값 표기만 받고 위반 코드는 정본에 이름이 있는…" |
| E4 | 고침 | `Timestamp` 에 소수 9자리 이하 pattern 을 넣고 10자리를 거부한다 | components.yaml:16; 시험 "시각: 소수 초는 9자리까지이고 오프셋이 있어야 한다(10자리 거부)…" |
| E5 | 고침 | `ModelIoFeatureRequirements` 가 기능마다 contains 와 minContains·maxContains 1 로 중복·누락을 거부한다 | components.yaml:1047; components.yaml:1055; 시험 "v3 의존 기능 표: 기능마다 정확히 하나이고 중복과 누락을 거부한다…" |
| E6 | 고침 | `examplesValid` 가 스키마 경로를 붙여 위치(components.schemas.<이름>.examples.<번호>)를 알리고 부정 시험을 더했다 | lint/functions/examplesValid.js:15; 시험 "예시가 스키마를 어기면 린트가 실패하고 위치(경로)를 알린다…" |
| E7 | 고침 | `DatasetFiles` 설명을 final 6개와 finaltest 2개, 합계 8개로 고쳤다 | components.yaml:2019 |
| E8 | 재현 불가 | Codex 환경의 `lint.test.mjs` rc=1 은 원인 출력이 없고 재현되지 않았다(깨끗한 clone 에서 npm ci 뒤 npm test rc=0, 아래 보고 참고). 시험의 임시 파일 경로(`build/`)는 시험이 만들고 병렬 실행하는 시험 파일은 서로 파일을 공유하지 않는다 | lint/tests/lint.test.mjs:7 |

## 대조 결과 처리(ADR 0019 개정)

대상은 `NoneCommit/audit-out/A.md`(205항목 중 53), `B.md`(202항목 중 89), `C.md`(217항목 중 108)에서 OK 가 아닌 250항목이다. 번호는 A·B·C 순서의 일련번호이고 두 번째 칸은 대조 파일과 그 파일의 행번호(C 는 개정 전 줄)와 스키마·작업 이름이다. 증거 칸은 스키마·작업 이름으로 위치를 가리킨다(줄 번호는 개정마다 바뀐다). 계약 시험은 `lint/tests/contract.test.mjs` 의 시험 이름으로 확인한다.

판정 용어: **고침**은 계약의 값·패턴·설명·근거를 정본이나 표준에 맞게 바꿨거나 근거를 정본 문장(헤드 결정 docs/design.md 4절, UD-23~25 포함)으로 바로잡은 것, **지움**은 ADR 0019 로 대상이 계약에서 없어진 것, **정할 수 없음**은 근거가 없어 값을 지어내지 않고 근거에 그 사실을 밝혀 둔 것(헤드 결정이 필요하다), **측정 확인 불가**는 정본이나 재측정으로 확인하지 못한 것이다.

처리 수: 고침 174, 지움 71, 정할 수 없음 5, 측정 확인 불가 0 (합계 250). 첫 처리에서 '정할 수 없음' 63건이었던 것은 헤드 결정(2026-11-10: docs/design.md 4절 어휘, UD-23~UD-25, 표준·모델 카드·API 명세 원문 확인, ContainerInputs 복원)을 반영해 나머지 외에는 '고침'이 되었다. 대조의 '측정 확인 불가' 32건 중 31건은 학습 서버 final·finaltest 93,429행 재측정(`NoneCommit/measure/report.md`)으로 확인해 '고침'(근거 수치 교정)이 되었고, 1건(`ArtifactContent` 의 어댑터 크기)은 재측정하지 않았으나 파일 올리기·내려받기 작업이 없어져 스키마를 지웠다.

| 번호 | 대조 파일 행 이름 | 원래 판정 | 처리 | 증거 |
|---|---|---|---|---|
| 1 | A.md 17 `ProblemType` | 없음 | 고침 | components.yaml `ProblemType`: 패턴을 RFC 3986 3.1 의 scheme 이 있는 URI 로 맞췄다(https 전용 주장 삭제). RFC 9457 3.1.1 |
| 2 | A.md 22 `ProblemReason` | 없음 | 고침 | components.yaml `ProblemReason`: 각 코드를 쓰는 작업(파일·작업 이름)과 맡는 2절 컴포넌트를 x-enum-descriptions 에 적고 근거를 그 작업과 design.md 2절로 댔다 |
| 3 | A.md 77 `PageLimit` | 근거 없음 | 고침 | components.yaml `PageLimit`: 헤드가 정한 표준·사용자 결정(UD-21~UD-24, OIDC Core, RFC 5280, RFC 3986, ADR 0001)을 근거로 바꾸고 값을 맞췄다(JobTimeoutSeconds 86400→259200, MetricValue 상한 2147483647→2^53-1) |
| 4 | A.md 78 `PageCursor` | 근거 없음 | 고침 | components.yaml `PageCursor`: 상한을 (Timestamp 35 + UUID 36 + 구분자 1 = 72바이트)의 base64url 길이 96 으로 계산해 바꿨다(140→96) |
| 5 | A.md 133 `ServiceName` | 근거 없음 | 고침 | components.yaml `ServiceName`: ADR 0019 와 docs/design.md 2절의 상시 서비스 3개와 화면 2개로 다시 정의하고 근거를 ADR 0019 로 바꿨다 |
| 6 | A.md 150 `HealthStatus` | 없음 | 고침 | components.yaml `HealthStatus`: 근거를 U101(건강 확인 본문 스키마가 없다는 빈 곳)과 D111 로 바꾸고, 이름과 모양은 만료된 초안을 참고한 계약의 선택임을 밝혔다(표준이라고 쓰지 않음) |
| 7 | A.md 158 `HealthCheck` | 없음 | 고침 | components.yaml `HealthCheck`: 근거를 U101(건강 확인 본문 스키마가 없다는 빈 곳)과 D111 로 바꾸고, 이름과 모양은 만료된 초안을 참고한 계약의 선택임을 밝혔다(표준이라고 쓰지 않음) |
| 8 | A.md 170 `ImageRevision` | 없음 | 고침 | components.yaml `ImageRevision`: D108(3) 의 16진수 revision 과 git 객체 ID 길이(40 또는 64)로 근거를 바로잡았다 |
| 9 | A.md 171 `HealthReport` | 없음 | 고침 | components.yaml `HealthReport`: 근거를 U101(건강 확인 본문 스키마가 없다는 빈 곳)과 D111 로 바꾸고, 이름과 모양은 만료된 초안을 참고한 계약의 선택임을 밝혔다(표준이라고 쓰지 않음) |
| 10 | A.md 183 `ForwardedClientCertValue` | 근거 없음 | 고침 | components.yaml `ForwardedClientCertValue`: 근거를 Envoy XFCC 사양(입구가 Envoy: design.md 2절), D113, D136, UD-19 로 바로잡았다. D113 의 X-Openit-Device 는 Caddy 입구 시절의 전달 방식이라 design.md 의 Envoy 입구로 대체했다 |
| 11 | A.md 184 `ReprDigestValue` | 어긋남 | 지움 | 파일 올리기·내려받기 작업이 없어져(모델 패키지는 OCI 아티팩트) 스키마 `ReprDigestValue` 를 지웠다 (커밋 a89a8eb) |
| 12 | A.md 185 `IdempotencyKeyValue` | 근거 없음 | 고침 | components.yaml `IdempotencyKeyValue`: UUID 형식의 근거를 RFC 9562 4 로 직접 인용하고 IETF 초안은 표준이 아님을 밝혔다 |
| 13 | A.md 187 `NumericDate` | 없음 | 고침 | components.yaml `NumericDate`: 상한 253402300799 를 9999-12-31T23:59:59Z 의 에포크 초 계산으로 근거를 댔다(계산 확인) |
| 14 | A.md 222 `PrometheusExposition` | 어긋남 | 고침 | components.yaml `PrometheusExposition`: 8 MiB 는 바이트라 본문 계층에서 강제하고 maxLength 는 글자 수라는 구분을 설명에 적었다(UD-03) |
| 15 | A.md 243 `MachineRole` | 없음 | 고침 | components.yaml `MachineRole`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 16 | A.md 265 `MachineClientName` | 어긋남 | 고침 | components.yaml `MachineClientName`: 패턴을 RFC 1035 2.3.1 의 label 문법(영문자 시작, 영문자·숫자 끝)으로 맞췄다 |
| 17 | A.md 285 `MachineTokenTable.tokens` | 없음 | 고침 | components.yaml `MachineTokenTable.tokens`: tokens 상한을 기계 호출자 4개(N03·N08·N09·N14)로 바로잡고 근거에 적었다 |
| 18 | A.md 286 `RealmAccessClaim` | 근거 없음 | 정할 수 없음 | components.yaml `RealmAccessClaim`: realm_access 는 Keycloak 제품 클레임이라 표준 근거가 없고 정본(U82)은 역할을 받는다고만 한다. 제품 클레임임을 근거에 밝혔다 |
| 19 | A.md 295 `PreferredUsername` | 없음 | 고침 | components.yaml `PreferredUsername`: 헤드가 정한 표준·사용자 결정(UD-21~UD-24, OIDC Core, RFC 5280, RFC 3986, ADR 0001)을 근거로 바꾸고 값을 맞췄다(JobTimeoutSeconds 86400→259200, MetricValue 상한 2147483647→2^53-1) |
| 20 | A.md 299 `TokenAudienceClaim.oneOf[1]` | 근거 없음 | 고침 | components.yaml `TokenAudienceClaim.oneOf[1]`: 해당 하위 제약(배열 최대, not const none)에 직접 x-basis 를 달았다(구조 값, RFC 9068 4) |
| 21 | A.md 323 `JwsAlgorithmName.not` | 근거 없음 | 고침 | components.yaml `JwsAlgorithmName.not`: 해당 하위 제약(배열 최대, not const none)에 직접 x-basis 를 달았다(구조 값, RFC 9068 4) |
| 22 | A.md 340 `DeviceId` | 없음 | 고침 | components.yaml `DeviceId`: 헤드가 정한 표준·사용자 결정(UD-21~UD-24, OIDC Core, RFC 5280, RFC 3986, ADR 0001)을 근거로 바꾸고 값을 맞췄다(JobTimeoutSeconds 86400→259200, MetricValue 상한 2147483647→2^53-1) |
| 23 | A.md 346 `QuestionnaireId` | 없음 | 고침 | components.yaml `QuestionnaireId`: 헤드가 정한 표준·사용자 결정(UD-21~UD-24, OIDC Core, RFC 5280, RFC 3986, ADR 0001)을 근거로 바꾸고 값을 맞췄다(JobTimeoutSeconds 86400→259200, MetricValue 상한 2147483647→2^53-1) |
| 24 | A.md 368 `StartCodeValue` | 없음 | 고침 | components.yaml `StartCodeValue`: 정확히 6자리 숫자의 근거를 C20 과 design.md 2절(start_code: 6자리 숫자)로 바로잡았다 |
| 25 | A.md 394 `ResponseSentence` | 측정 확인 불가 | 고침 | components.yaml `ResponseSentence`: 학습 서버 93,429행 재측정(B 응답 134, current_question 172)과 IO_SPEC.md 4.2 로 근거를 바로잡았다. 344 는 172 의 2배 |
| 26 | A.md 396 `SessionStatus` | 없음 | 고침 | components.yaml `SessionStatus`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 27 | A.md 408 `PauseReason` | 없음 | 고침 | components.yaml `PauseReason`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 28 | A.md 417 `TurnFailureReason` | 없음 | 고침 | components.yaml `TurnFailureReason`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 29 | A.md 427 `StaffHelpNotice` | 없음 | 정할 수 없음 | components.yaml `StaffHelpNotice`: 설명 요청 3번 뒤 직원 도움 안내는 v7-flow-resolutions 에 있으나 고정 문장을 서비스가 쓴다는 책임 문장은 design.md 4절에도 없다. 계약의 정의임을 근거에 밝혀 두었다 |
| 30 | A.md 503 `AlertKind` | 없음 | 고침 | components.yaml `AlertKind`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 31 | A.md 561 `InterventionAction` | 없음 | 고침 | components.yaml `InterventionAction`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 32 | A.md 620 `WebPushPayload` | 어긋남 | 고침 | components.yaml `WebPushPayload`: 4096옥텟을 RFC 8291 4 의 지원 하한(평문 3993)으로 바로잡아 전역 최대가 아님을 밝혔다 |
| 33 | A.md 679 `QuestionText` | 측정 확인 불가 | 고침 | components.yaml `QuestionText`: SQL.md 질문 문장 최대 56 과 재측정 next.text 최대 62(93,429행)로 124 를 확인했다 |
| 34 | A.md 702 `FlowComparison` | 없음 | 고침 | components.yaml `FlowComparison`: 여섯 연산이 FHIR R4 enableWhen.operator(=, !=, >, <, >=, <=)와 같은 뜻임을 근거로 하고 설명에 FHIR 연산자를 적었다(원문 확인) |
| 35 | A.md 747 `FlowRule.branches` | 어긋남 | 고침 | components.yaml `FlowRule.branches`: labels.py next_after 의 규칙에서 한 문항 뒤 최대 갈래 수 2(조건 1 + 기본 경로)를 세고 2배인 4 로 바꿨다(14→4) |
| 36 | A.md 773 `ChangeClass` | 없음 | 지움 | ADR 0019 로 question-authoring 영역이 없어져 스키마 `ChangeClass` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 37 | A.md 849 `MediaType` | 어긋남 | 지움 | 파일 올리기·내려받기 작업이 없어져(모델 패키지는 OCI 아티팩트) 스키마 `MediaType` 를 지웠다 (커밋 a89a8eb) |
| 38 | A.md 872 `DraftStatus` | 없음 | 지움 | ADR 0019 로 question-authoring 영역이 없어져 스키마 `DraftStatus` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 39 | A.md 895 `DraftSummary` | 없음 | 지움 | ADR 0019 로 question-authoring 영역이 없어져 스키마 `DraftSummary` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 40 | A.md 907 `DraftPage` | 없음 | 지움 | ADR 0019 로 question-authoring 영역이 없어져 스키마 `DraftPage` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 41 | A.md 930 `ConfusionSummary` | 없음 | 지움 | ADR 0019 로 ops-feedback 영역이 없어져 스키마 `ConfusionSummary` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 42 | A.md 989 `YesNoAnswer` | 측정 확인 불가 | 고침 | components.yaml `YesNoAnswer`: boolean 건수를 25463 에서 재측정한 15572 로 고쳤다(93,429행) |
| 43 | A.md 990 `NoValue` | 측정 확인 불가 | 고침 | components.yaml `NoValue`: null 건수를 8820 에서 재측정한 11992 로 고쳤다(93,429행) |
| 44 | A.md 991 `SlotText` | 없음 | 고침 | components.yaml `SlotText`: 헤드가 정한 표준·사용자 결정(UD-21~UD-24, OIDC Core, RFC 5280, RFC 3986, ADR 0001)을 근거로 바꾸고 값을 맞췄다(JobTimeoutSeconds 86400→259200, MetricValue 상한 2147483647→2^53-1) |
| 45 | A.md 1019 `CollectedState` | 측정 확인 불가 | 고침 | components.yaml `CollectedState`: 재측정 state 최대 9(93,429행)로 18 을 확인했다 |
| 46 | A.md 1028 `CurrentQuestionText` | 측정 확인 불가 | 고침 | components.yaml `CurrentQuestionText`: 재측정 current_question 최대 172(93,429행)로 344 를 확인했다 |
| 47 | A.md 1029 `ModelIoFeature` | 없음 | 고침 | components.yaml `ModelIoFeature`: 기능 이름 셋을 docs/design.md 4절로 근거를 바꿨다 |
| 48 | A.md 1036 `MinimumModelIoVersion` | 근거 없음 | 고침 | components.yaml `MinimumModelIoVersion`: 기능 이름 셋을 docs/design.md 4절로 근거를 바꿨다 |
| 49 | A.md 1053 `ModelIoFeatureRequirements.allOf[0].contains.fea` | 근거 없음 | 고침 | components.yaml `ModelIoFeatureRequirements.allOf[0].contains.feature`: 기능 이름 셋을 docs/design.md 4절로 근거를 바꿨다 |
| 50 | A.md 1054 `ModelIoFeatureRequirements.allOf[1].contains.fea` | 근거 없음 | 고침 | components.yaml `ModelIoFeatureRequirements.allOf[1].contains.feature`: 기능 이름 셋을 docs/design.md 4절로 근거를 바꿨다 |
| 51 | A.md 1055 `ModelIoFeatureRequirements.allOf[2].contains.fea` | 근거 없음 | 고침 | components.yaml `ModelIoFeatureRequirements.allOf[2].contains.feature`: 기능 이름 셋을 docs/design.md 4절로 근거를 바꿨다 |
| 52 | A.md 1060 `ModelIoVersion` | 없음 | 고침 | components.yaml `ModelIoVersion`: v2 는 IO_SPEC.md 머리말(형식 v2 확정)로 바로잡고 v3 의 뜻은 v7-flow-resolutions 로 연결했다. 글자 표기는 계약의 정의임을 밝혔다 |
| 53 | A.md 1079 `NextItemRuleKind` | 없음 | 고침 | components.yaml `NextItemRuleKind`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 54 | B.md 1101 `ActionExtractionRules` | 측정 확인 불가 | 고침 | components.yaml `ActionExtractionRules`: 근거 수치를 재측정으로 바로잡았다(A 출력 48747행은 46655행). 합격 조건 칸을 코드와 일대일로 하고 현재 문항 규칙을 데이터로 넣었다 |
| 55 | B.md 1163 `ActionReason` | 없음 | 고침 | components.yaml `ActionReason`: 열거 20개가 재측정한 reason 20종(93,429행)과 같음을 근거에 적고 IO_SPEC.md 1장을 인용했다 |
| 56 | B.md 1170 `ValueStatus` | 없음 | 고침 | components.yaml `ValueStatus`: 열거 근거를 SQL.md 6.1 의 7개 상태로 직접 인용했다 |
| 57 | B.md 1177 `ValuePrecision` | 측정 확인 불가 | 고침 | components.yaml `ValuePrecision`: 건수를 재측정한 exact 56930·unspecified 11992·approximate 7119 로 고치고 열거 근거를 SQL.md 로 했다 |
| 58 | B.md 1178 `ValueSave` | 측정 확인 불가 | 고침 | components.yaml `ValueSave`: SQL.md 6.1 과 labels.py 로 근거를 바로잡고 status·save 조합을 재측정(93,429행)으로 확인했다 |
| 59 | B.md 1193 `ExtractedValue.allOf.0.if.properties.status` | 근거 없음 | 고침 | components.yaml `ExtractedValue.allOf.0.if.properties.status`: status 와 save 의 짝은 ActionExtractionRules(SAVE_RULE)로 옮겼고, 남은 precision 조건에 IO_SPEC.md 2.2 와 재측정(null 11992 = unspecified 11992)을 x-basis 로 달았다 |
| 60 | B.md 1194 `ExtractedValue.allOf.0.then.properties.save` | 근거 없음 | 고침 | components.yaml `ExtractedValue.allOf.0.then.properties.save`: status 와 save 의 짝은 ActionExtractionRules(SAVE_RULE)로 옮겼고, 남은 precision 조건에 IO_SPEC.md 2.2 와 재측정(null 11992 = unspecified 11992)을 x-basis 로 달았다 |
| 61 | B.md 1195 `ExtractedValue.allOf.0.else.properties.save` | 근거 없음 | 고침 | components.yaml `ExtractedValue.allOf.0.else.properties.save`: status 와 save 의 짝은 ActionExtractionRules(SAVE_RULE)로 옮겼고, 남은 precision 조건에 IO_SPEC.md 2.2 와 재측정(null 11992 = unspecified 11992)을 x-basis 로 달았다 |
| 62 | B.md 1197 `ExtractedValue.allOf.1.then.properties.precision` | 근거 없음 | 고침 | components.yaml `ExtractedValue.allOf.1.then.properties.precision`: status 와 save 의 짝은 ActionExtractionRules(SAVE_RULE)로 옮겼고, 남은 precision 조건에 IO_SPEC.md 2.2 와 재측정(null 11992 = unspecified 11992)을 x-basis 로 달았다 |
| 63 | B.md 1198 `ExtractedValue.allOf.1.else.properties.precision` | 근거 없음 | 고침 | components.yaml `ExtractedValue.allOf.1.else.properties.precision`: status 와 save 의 짝은 ActionExtractionRules(SAVE_RULE)로 옮겼고, 남은 precision 조건에 IO_SPEC.md 2.2 와 재측정(null 11992 = unspecified 11992)을 x-basis 로 달았다 |
| 64 | B.md 1199 `ExtractedValues` | 측정 확인 불가 | 고침 | components.yaml `ExtractedValues`: 재측정(93,429행) values 4·targets 4·note 35·state 9 로 상한(2배)을 확인하고 근거에 적었다 |
| 65 | B.md 1200 `SlotRefStrings` | 측정 확인 불가 | 고침 | components.yaml `SlotRefStrings`: 재측정(93,429행) values 4·targets 4·note 35·state 9 로 상한(2배)을 확인하고 근거에 적었다 |
| 66 | B.md 1201 `OutOfSchemaNote` | 측정 확인 불가 | 고침 | components.yaml `OutOfSchemaNote`: 재측정(93,429행) values 4·targets 4·note 35·state 9 로 상한(2배)을 확인하고 근거에 적었다 |
| 67 | B.md 1217 `ActionExtraction.allOf.0.if.properties.action` | 근거 없음 | 고침 | components.yaml `ActionExtraction.allOf.0.if.properties.action`: 네 조건(action·reason 별 reason·targets·note 의 있고 없음)에 labels.py a_target 과 IO_SPEC.md 1장·2.2 를 직접 x-basis 로 달았다 |
| 68 | B.md 1219 `ActionExtraction.allOf.1.if.properties.action` | 근거 없음 | 고침 | components.yaml `ActionExtraction.allOf.1.if.properties.action`: 네 조건(action·reason 별 reason·targets·note 의 있고 없음)에 labels.py a_target 과 IO_SPEC.md 1장·2.2 를 직접 x-basis 로 달았다 |
| 69 | B.md 1221 `ActionExtraction.allOf.2.if.properties.action` | 근거 없음 | 고침 | components.yaml `ActionExtraction.allOf.2.if.properties.action`: 네 조건(action·reason 별 reason·targets·note 의 있고 없음)에 labels.py a_target 과 IO_SPEC.md 1장·2.2 를 직접 x-basis 로 달았다 |
| 70 | B.md 1223 `ActionExtraction.allOf.3.if.properties.reason` | 근거 없음 | 고침 | components.yaml `ActionExtraction.allOf.3.if.properties.reason`: 네 조건(action·reason 별 reason·targets·note 의 있고 없음)에 labels.py a_target 과 IO_SPEC.md 1장·2.2 를 직접 x-basis 로 달았다 |
| 71 | B.md 1226 `StateKeyOrder` | 측정 확인 불가 | 고침 | components.yaml `StateKeyOrder`: 재측정(93,429행) values 4·targets 4·note 35·state 9 로 상한(2배)을 확인하고 근거에 적었다 |
| 72 | B.md 1256 `ResponseAction` | 측정 확인 불가 | 고침 | components.yaml `ResponseAction`: 열거 근거를 IO_SPEC.md 1장과 labels.py 로 하고 START 119행은 재측정(93,429행)으로 확인했다 |
| 73 | B.md 1264 `TopicText` | 측정 확인 불가 | 고침 | components.yaml `TopicText`: 재측정(93,429행)으로 B 입력 필드 최대(44·62·46·15·15·18)를 확인하고 근거에 적었다 |
| 74 | B.md 1265 `KnownText` | 측정 확인 불가 | 고침 | components.yaml `KnownText`: 재측정(93,429행)으로 B 입력 필드 최대(44·62·46·15·15·18)를 확인하고 근거에 적었다 |
| 75 | B.md 1266 `AskText` | 측정 확인 불가 | 고침 | components.yaml `AskText`: 재측정(93,429행)으로 B 입력 필드 최대(44·62·46·15·15·18)를 확인하고 근거에 적었다 |
| 76 | B.md 1267 `PreviousValueText` | 측정 확인 불가 | 고침 | components.yaml `PreviousValueText`: 재측정(93,429행)으로 B 입력 필드 최대(44·62·46·15·15·18)를 확인하고 근거에 적었다 |
| 77 | B.md 1268 `CurrentValueText` | 측정 확인 불가 | 고침 | components.yaml `CurrentValueText`: 재측정(93,429행)으로 B 입력 필드 최대(44·62·46·15·15·18)를 확인하고 근거에 적었다 |
| 78 | B.md 1269 `HoldText` | 측정 확인 불가 | 고침 | components.yaml `HoldText`: 재측정(93,429행)으로 B 입력 필드 최대(44·62·46·15·15·18)를 확인하고 근거에 적었다 |
| 79 | B.md 1281 `ResponseNext.if.properties.type` | 근거 없음 | 고침 | components.yaml `ResponseNext.if.properties.type`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 80 | B.md 1304 `ResponseRequest.allOf.0.if.properties.action` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.0.if.properties.action`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 81 | B.md 1305 `ResponseRequest.allOf.0.then.properties.next.pro` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.0.then.properties.next.properties.type`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 82 | B.md 1306 `ResponseRequest.allOf.1.if.properties.action` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.1.if.properties.action`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 83 | B.md 1308 `ResponseRequest.allOf.2.if.properties.action` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.2.if.properties.action`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 84 | B.md 1310 `ResponseRequest.allOf.3.if.properties.action` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.3.if.properties.action`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 85 | B.md 1312 `ResponseRequest.allOf.4.if.properties.action` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.4.if.properties.action`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 86 | B.md 1314 `ResponseRequest.allOf.5.if.properties.action` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.5.if.properties.action`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 87 | B.md 1316 `ResponseRequest.allOf.6.if.properties.action` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.6.if.properties.action`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 88 | B.md 1318 `ResponseRequest.allOf.7.if.properties.action` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.7.if.properties.action`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 89 | B.md 1320 `ResponseRequest.allOf.8.if.properties.action` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.8.if.properties.action`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 90 | B.md 1321 `ResponseRequest.allOf.8.then.properties.next.pro` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.8.then.properties.next.properties.type`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 91 | B.md 1322 `ResponseRequest.allOf.9.if.properties.action` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.9.if.properties.action`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 92 | B.md 1323 `ResponseRequest.allOf.9.then.properties.next.pro` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.9.then.properties.next.properties.type`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 93 | B.md 1324 `ResponseRequest.allOf.10.if.properties.reason` | 근거 없음 | 고침 | components.yaml `ResponseRequest.allOf.10.if.properties.reason`: allOf 열한 개 조건과 END 조건의 if·then·else 마다 labels.py(start_b_input, b_input)와 IO_SPEC.md 4.1·5장을 직접 x-basis 로 달았다 |
| 94 | B.md 1342 `ResponseResult` | 측정 확인 불가 | 고침 | components.yaml `ResponseResult`: 근거를 IO_SPEC.md 4.2 와 재측정(B 출력 최대 134)으로 바로잡았다 |
| 95 | B.md 1353 `ModelLoadState` | 없음 | 고침 | components.yaml `ModelLoadState`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 96 | B.md 1376 `BlankReason` | 없음 | 고침 | components.yaml `BlankReason`: NOT_ASKED 를 정본 SQL.md resolution_status 의 UNASKED 로 바꾸고 근거를 U35·U100·U36 으로 바로잡았다 |
| 97 | B.md 1507 `FhirMapping` | 없음 | 정할 수 없음 | components.yaml `FhirMapping`: C10 은 FHIR 조회만 정하고 내부 값에서 FHIR 로 가는 대응은 정본에 없다. FHIR R4 를 근거로 계약이 정의한 대응임을 밝혔다 |
| 98 | B.md 1518 `RiskCategory` | 없음 | 고침 | components.yaml `RiskCategory`: 영문 코드와 한국어 분류의 대응을 docs/design.md 4절로 근거를 바꿨다 |
| 99 | B.md 1536 `DurationMs` | 어긋남 | 지움 | 턴 기록과 업무 로그는 survey-service 영역 안의 값이라(docs/design.md 3절, ADR 0019) 스키마 `DurationMs` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 100 | B.md 1567 `BusinessEventKind` | 없음 | 지움 | 턴 기록과 업무 로그는 survey-service 영역 안의 값이라(docs/design.md 3절, ADR 0019) 스키마 `BusinessEventKind` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 101 | B.md 1584 `BusinessLogEntry.allOf.0.if.properties.kind.not` | 근거 없음 | 지움 | 턴 기록과 업무 로그는 survey-service 영역 안의 값이라(docs/design.md 3절, ADR 0019) 스키마 `BusinessLogEntry` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 102 | B.md 1586 `BusinessLogEntry.allOf.1.if.properties.kind` | 근거 없음 | 지움 | 턴 기록과 업무 로그는 survey-service 영역 안의 값이라(docs/design.md 3절, ADR 0019) 스키마 `BusinessLogEntry` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 103 | B.md 1588 `BusinessLogEntry.allOf.2.if.properties.kind` | 근거 없음 | 지움 | 턴 기록과 업무 로그는 survey-service 영역 안의 값이라(docs/design.md 3절, ADR 0019) 스키마 `BusinessLogEntry` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 104 | B.md 1596 `TraceDelivery` | 없음 | 지움 | 턴 기록과 업무 로그는 survey-service 영역 안의 값이라(docs/design.md 3절, ADR 0019) 스키마 `TraceDelivery` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 105 | B.md 1612 `CaseVersion` | 없음 | 고침 | components.yaml `CaseVersion`: D71(3)의 증가 규칙과 int32 범위(OpenAPI 3.1)로 근거를 나누어 적었다. 시작값 1 은 계약의 선택임을 밝혔다 |
| 106 | B.md 1619 `FailureKind` | 없음 | 고침 | components.yaml `FailureKind`: 정본에 정의가 없는 설명(값 없는 보류·건너뛰기 포함)을 지우고 근거를 G14 의 두 이름으로 바로잡았다 |
| 107 | B.md 1626 `ReviewStatus` | 없음 | 고침 | components.yaml `ReviewStatus`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 108 | B.md 1649 `FailureCase.if.properties.review_status` | 근거 없음 | 고침 | components.yaml `FailureCase.if.properties.review_status`: CONFIRMED 조건의 if·then 에 D52(2)를 직접 x-basis 로 달았다. Export 의 reviewed_input 필수는 계약의 선택임을 밝혔다 |
| 109 | B.md 1668 `FailureCaseExport.if.properties.review_status` | 근거 없음 | 고침 | components.yaml `FailureCaseExport.if.properties.review_status`: CONFIRMED 조건의 if·then 에 D52(2)를 직접 x-basis 로 달았다. Export 의 reviewed_input 필수는 계약의 선택임을 밝혔다 |
| 110 | B.md 1702 `CaseReview.if.properties.review_status` | 근거 없음 | 고침 | components.yaml `CaseReview.if.properties.review_status`: CONFIRMED 조건의 if·then 에 D52(2)를 직접 x-basis 로 달았다. Export 의 reviewed_input 필수는 계약의 선택임을 밝혔다 |
| 111 | B.md 1723 `SemanticVersion` | 어긋남 | 고침 | components.yaml `SemanticVersion`: 패턴을 semver.org 공식 정규식으로 바꿨다(선행 0·빈 조각 거부). 길이 64 는 계약의 선택임을 밝혔다 |
| 112 | B.md 1724 `BaseModelName` | 근거 없음 | 고침 | components.yaml `BaseModelName`: 96자와 이름 형식을 huggingface_hub validate_repo_id 규칙으로 근거를 대고 pattern 과 금지 조건을 더했다(원문 확인, 값은 원문과 같다) |
| 113 | B.md 1745 `ArtifactContent` | 측정 확인 불가 | 지움 | 파일 올리기·내려받기 작업이 없어져(모델 패키지는 OCI 아티팩트) 스키마 `ArtifactContent` 를 지웠다 (커밋 a89a8eb) |
| 114 | B.md 1746 `TokenLimit` | 근거 없음 | 고침 | components.yaml `TokenLimit`: 32768 을 Qwen3 모델 카드의 기본 문맥 길이로 근거를 댔다(원문 확인) |
| 115 | B.md 1747 `SamplingTemperature` | 근거 없음 | 고침 | components.yaml `SamplingTemperature`: 0~2 를 OpenAI OpenAPI 명세의 temperature 범위로 근거를 댔다(원문 확인) |
| 116 | B.md 1787 `RequiredMetricName` | 없음 | 고침 | components.yaml `RequiredMetricName`: 시간 지표를 length_p95_seconds(초)로 바꿔 MetricUnit 과 맞췄다. precision_match_rate 는 D96(2)를 풀어 쓴 이름임을 밝혔다 |
| 117 | B.md 1830 `MetricSliceDimension` | 없음 | 고침 | components.yaml `MetricSliceDimension`: D96·D97·D13 원문을 확인해 여섯 기준의 뜻이 모두 원문에 있음을 근거로 하고 키 이름은 그 뜻에 붙인 계약의 이름으로 밝혔다 |
| 118 | B.md 1837 `ViolationCode` | 없음 | 고침 | components.yaml `ViolationCode`: 옛 열거(VALUE_INVALID 등)를 합격 조건 하나당 코드 하나인 열 개로 바꾸고 근거를 U24·U74·G13 과 계약 스키마 이름으로 바로잡았다 |
| 119 | B.md 1838 `MetricSlice` | 없음 | 고침 | components.yaml `MetricSlice`: 값 길이를 UD-25(1~63자)로 맞췄다(pattern 64→63, maxLength 85→84) |
| 120 | B.md 1845 `MetricUnit` | 없음 | 고침 | components.yaml `MetricUnit`: milliseconds 를 Prometheus 명명 관례(기본 단위 seconds)로 바꾸고 단위 이름의 근거를 적었다(원문 확인) |
| 121 | B.md 1846 `MetricValue` | 어긋남 | 고침 | components.yaml `MetricValue`: 헤드가 정한 표준·사용자 결정(UD-21~UD-24, OIDC Core, RFC 5280, RFC 3986, ADR 0001)을 근거로 바꾸고 값을 맞췄다(JobTimeoutSeconds 86400→259200, MetricValue 상한 2147483647→2^53-1) |
| 122 | B.md 1862 `EvaluationMetric.if.properties.unit` | 근거 없음 | 고침 | components.yaml `EvaluationMetric.if.properties.unit`: ratio 조건과 maximum 1 에 D96 과 비율의 정의를 직접 x-basis 로 달았다 |
| 123 | B.md 1863 `EvaluationMetric.then.properties.value` | 근거 없음 | 고침 | components.yaml `EvaluationMetric.then.properties.value`: ratio 조건과 maximum 1 에 D96 과 비율의 정의를 직접 x-basis 로 달았다 |
| 124 | B.md 1888 `TrainingLineage.properties.training_run_ids` | 없음 | 고침 | components.yaml `TrainingLineage.properties.training_run_ids`: training_run_ids 의 상한 2 를 design.md 2절(train 이 어댑터마다 실행)과 AdapterRole 수로 연결했다 |
| 125 | B.md 1907 `ModelPackageManifest.allOf.0.properties.adapters` | 근거 없음 | 고침 | components.yaml `ModelPackageManifest.allOf.0.properties.adapters.contains.pr`: LORA_A·LORA_B 하나씩 조건에 D45 와 design.md 2절을 직접 x-basis 로 달았다. 패키지 식별자는 OCI digest 로 바꿨다 |
| 126 | B.md 1908 `ModelPackageManifest.allOf.1.properties.adapters` | 근거 없음 | 고침 | components.yaml `ModelPackageManifest.allOf.1.properties.adapters.contains.pr`: LORA_A·LORA_B 하나씩 조건에 D45 와 design.md 2절을 직접 x-basis 로 달았다. 패키지 식별자는 OCI digest 로 바꿨다 |
| 127 | B.md 1961 `TrainingOutcome` | 없음 | 지움 | ADR 0019 로 model-lab 영역이 없어져 스키마 `TrainingOutcome` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 128 | B.md 1975 `TrainingRunResult.if.properties.outcome` | 근거 없음 | 지움 | ADR 0019 로 model-lab 영역이 없어져 스키마 `TrainingRunResult` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 129 | B.md 1997 `DatasetSplit` | 측정 확인 불가 | 고침 | components.yaml `DatasetSplit`: 재측정(93,429행, 파일 8개)으로 최대값·종류·키·갈래·파일 수를 확인하고 근거에 적었다 |
| 130 | B.md 2005 `DatasetFileSet` | 측정 확인 불가 | 고침 | components.yaml `DatasetFileSet`: 재측정(93,429행, 파일 8개)으로 최대값·종류·키·갈래·파일 수를 확인하고 근거에 적었다 |
| 131 | B.md 2019 `DatasetFiles` | 측정 확인 불가 | 고침 | components.yaml `DatasetFiles`: 재측정(93,429행, 파일 8개)으로 최대값·종류·키·갈래·파일 수를 확인하고 근거에 적었다 |
| 132 | B.md 2027 `DatasetOrigin` | 없음 | 고침 | components.yaml `DatasetOrigin`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 133 | B.md 2070 `DatasetImportStatus` | 없음 | 지움 | ADR 0019 로 synthetic-data 영역이 없어져 스키마 `DatasetImportStatus` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 134 | B.md 2089 `HumanReviewMark` | 측정 확인 불가 | 고침 | components.yaml `HumanReviewMark`: 재측정(93,429행, 파일 8개)으로 최대값·종류·키·갈래·파일 수를 확인하고 근거에 적었다 |
| 135 | B.md 2096 `ChatRole` | 측정 확인 불가 | 고침 | components.yaml `ChatRole`: 재측정(93,429행, 파일 8개)으로 최대값·종류·키·갈래·파일 수를 확인하고 근거에 적었다 |
| 136 | B.md 2097 `ChatMessageContent` | 측정 확인 불가 | 고침 | components.yaml `ChatMessageContent`: 재측정(93,429행, 파일 8개)으로 최대값·종류·키·갈래·파일 수를 확인하고 근거에 적었다 |
| 137 | B.md 2103 `ChatMessage` | 측정 확인 불가 | 고침 | components.yaml `ChatMessage`: 재측정(93,429행, 파일 8개)으로 최대값·종류·키·갈래·파일 수를 확인하고 근거에 적었다 |
| 138 | B.md 2108 `ScenarioId` | 측정 확인 불가 | 고침 | components.yaml `ScenarioId`: 재측정(93,429행, 파일 8개)으로 최대값·종류·키·갈래·파일 수를 확인하고 근거에 적었다 |
| 139 | B.md 2114 `DatasetRow` | 측정 확인 불가 | 고침 | components.yaml `DatasetRow`: 재측정(93,429행, 파일 8개)으로 최대값·종류·키·갈래·파일 수를 확인하고 근거에 적었다 |
| 140 | B.md 2118 `DatasetRow.properties.messages` | 측정 확인 불가 | 고침 | components.yaml `DatasetRow.properties.messages`: 재측정(93,429행, 파일 8개)으로 최대값·종류·키·갈래·파일 수를 확인하고 근거에 적었다 |
| 141 | B.md 2133 `CandidateKind` | 없음 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `CandidateKind` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 142 | B.md 2179 `GateCheckName` | 없음 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `GateCheckName` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 143 | C.md 2206 `SubmissionStatus` | 없음 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `SubmissionStatus` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 144 | C.md 2259 `MetricComparison.if.properties.unit` | 근거 없음 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `MetricComparison` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 145 | C.md 2260 `MetricComparison.then.properties.candidate_value` | 근거 없음 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `MetricComparison` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 146 | C.md 2260 `MetricComparison.then.properties.active_value` | 근거 없음 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `MetricComparison` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 147 | C.md 2266 `ReviewReport` | 어긋남 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `ReviewReport` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 148 | C.md 2289 `ApprovalRequest` | 어긋남 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `ApprovalRequest` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 149 | C.md 2295 `ApprovalRequest.if.properties.decision` | 근거 없음 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `ApprovalRequest` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 150 | C.md 2345 `ActiveRelease` | 어긋남 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `ActiveRelease` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 151 | C.md 2367 `ActivationRequest` | 어긋남 | 고침 | components.yaml `ActivationRequest`: 신원을 X-Openit-User 헤더 대신 OIDC 접근 토큰의 sub 클레임에서 얻도록 바꿨다(docs/design.md 3절 끝, ADR 0019, RFC 9068 2.2). 본문에 신원 칸이 없다 |
| 152 | C.md 2389 `RollbackRequestStatus` | 없음 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `RollbackRequestStatus` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 153 | C.md 2395 `RollbackRequest` | 어긋남 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `RollbackRequest` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 154 | C.md 2421 `RollbackCommand` | 어긋남 | 고침 | components.yaml `RollbackCommand`: 신원을 X-Openit-User 헤더 대신 OIDC 접근 토큰의 sub 클레임에서 얻도록 바꿨다(docs/design.md 3절 끝, ADR 0019, RFC 9068 2.2). 본문에 신원 칸이 없다 |
| 155 | C.md 2445 `JobName` | 없음 | 고침 | components.yaml `JobName`: 잡 이름 목록을 docs/design.md 4절로 근거를 바꿨다 |
| 156 | C.md 2446 `JobTimeoutSeconds` | 어긋남 | 고침 | components.yaml `JobTimeoutSeconds`: 헤드가 정한 표준·사용자 결정(UD-21~UD-24, OIDC Core, RFC 5280, RFC 3986, ADR 0001)을 근거로 바꾸고 값을 맞췄다(JobTimeoutSeconds 86400→259200, MetricValue 상한 2147483647→2^53-1) |
| 157 | C.md 2471 `JobRunInput` | 근거 없음 | 고침 | components.yaml `JobRunInput`: 허용 출처 밖의 RUNTIME R9.1 인용을 지우고 D39 로 바꿨다. 시각 주입은 계약의 선택임을 밝혔다 |
| 158 | C.md 2477 `BackupSnapshotId` | 없음 | 정할 수 없음 | components.yaml `BackupSnapshotId`: ID 형식은 restic 도구 관행이고 정본은 restic 사용만 정한다. 그 사실을 근거에 밝혔다 |
| 159 | C.md 2493 `JobRunResult` | 근거 없음 | 정할 수 없음 | components.yaml `JobRunResult`: D130 은 종료 코드만 정한다. 출력 직렬화와 칸은 계약의 정의임을 밝히고 RUNTIME R9 인용을 지웠다 |
| 160 | C.md 2504 `SecretFilePath` | 어긋남 | 고침 | components.yaml `SecretFilePath`: POSIX PATH_MAX 가 4096 으로 고정이라는 주장을 지우고 Linux PATH_MAX 4096(바이트, NUL 포함)을 근거로 하고 글자 수와 바이트 수의 구분을 밝혔다 |
| 161 | C.md 2505 `ConfigFilePath` | 어긋남 | 고침 | components.yaml `ConfigFilePath`: POSIX PATH_MAX 가 4096 으로 고정이라는 주장을 지우고 Linux PATH_MAX 4096(바이트, NUL 포함)을 근거로 하고 글자 수와 바이트 수의 구분을 밝혔다 |
| 162 | C.md 2508 `EgressProxyUrl` | 없음 | 고침 | components.yaml `EgressProxyUrl`: UD-19 주소류 상한을 근거에 더했다 |
| 163 | C.md 2515 `LogLevel` | 없음 | 고침 | components.yaml `LogLevel`: Python logging 표준 수준 다섯 개(CRITICAL 추가)를 근거로 했다 |
| 164 | C.md 2516 `DatabaseUrl` | 근거 없음 | 고침 | components.yaml `DatabaseUrl`: 근거를 D85(6)·D126·D84, PostgreSQL 접속 URI 사양, UD-19 로 바꾸고 ADR 0001 인용을 지웠다 |
| 165 | C.md 2517 `BackupRepositoryUrl` | 없음 | 고침 | components.yaml `BackupRepositoryUrl`: TLS 강제를 C14 로, 상한을 UD-19 로 연결했다. 주소 형식은 restic 사양임을 밝혔다 |
| 166 | C.md 2518 `OffsiteBackupUrl` | 없음 | 고침 | components.yaml `OffsiteBackupUrl`: UD-19 상한을 근거에 더했다 |
| 167 | C.md 2521 `ReaskLimit` | 없음 | 고침 | components.yaml `ReaskLimit`: 근거를 docs/v7-flow-resolutions.md 의 2026-11-10 사용자 결정으로 바로잡았다(U36 은 2026-11-03 의 3회 결정) |
| 168 | C.md 2547 `FhirCanonicalBaseUrl` | 어긋남 | 고침 | components.yaml `FhirCanonicalBaseUrl`: https 전용 패턴을 FHIR canonical 의 절대 URI(scheme 이 있는 URI)로 완화했다 |
| 169 | C.md 2553 `SurveyServiceEnv` | 없음 | 고침 | components.yaml `SurveyServiceEnv`: 근거를 docs/design.md 4절로 바꾸고 입력마다 필요한 2절 컴포넌트를 description 에 적었다. 필요한 컴포넌트가 없는 입력(백업·서버 밖 백업 입력, 화면의 루트 인증서)은 지웠다 |
| 170 | C.md 2591 `ReleaseGateEnv` | 없음 | 지움 | ADR 0019 로 release-gate 영역이 없어져 스키마 `ReleaseGateEnv` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 171 | C.md 2619 `QuestionAuthoringEnv` | 없음 | 지움 | ADR 0019 로 question-authoring 영역이 없어져 스키마 `QuestionAuthoringEnv` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 172 | C.md 2649 `OpsFeedbackEnv` | 없음 | 지움 | ADR 0019 로 ops-feedback 영역이 없어져 스키마 `OpsFeedbackEnv` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 173 | C.md 2677 `ModelRuntimeEnv` | 없음 | 고침 | components.yaml `ModelRuntimeEnv`: 근거를 docs/design.md 4절로 바꾸고 입력마다 필요한 2절 컴포넌트를 description 에 적었다. 필요한 컴포넌트가 없는 입력(백업·서버 밖 백업 입력, 화면의 루트 인증서)은 지웠다 |
| 174 | C.md 2697 `ModelLabEnv` | 없음 | 고침 | components.yaml `ModelLabEnv`: 근거를 docs/design.md 4절로 바꾸고 입력마다 필요한 2절 컴포넌트를 description 에 적었다. 필요한 컴포넌트가 없는 입력(백업·서버 밖 백업 입력, 화면의 루트 인증서)은 지웠다 |
| 175 | C.md 2726 `SyntheticDataEnv` | 없음 | 지움 | ADR 0019 로 synthetic-data 영역이 없어져 스키마 `SyntheticDataEnv` 를 계약에서 지웠다 (커밋 a89a8eb) |
| 176 | C.md 2751 `KioskFrontendEnv` | 없음 | 고침 | components.yaml `KioskFrontendEnv`: 근거를 docs/design.md 4절로 바꾸고 입력마다 필요한 2절 컴포넌트를 description 에 적었다. 필요한 컴포넌트가 없는 입력(백업·서버 밖 백업 입력, 화면의 루트 인증서)은 지웠다 |
| 177 | C.md 2764 `AdminConsoleEnv` | 없음 | 고침 | components.yaml `AdminConsoleEnv`: 근거를 docs/design.md 4절로 바꾸고 입력마다 필요한 2절 컴포넌트를 description 에 적었다. 필요한 컴포넌트가 없는 입력(백업·서버 밖 백업 입력, 화면의 루트 인증서)은 지웠다 |
| 178 | C.md 2797 `CaMode` | 없음 | 고침 | components.yaml `CaMode`: 근거를 ADR 0015(CA·입구 인증서 방식), ADR 0005(EnvKind)로 바꿨다 |
| 179 | C.md 2804 `IngressCertificateMode` | 없음 | 고침 | components.yaml `IngressCertificateMode`: 근거를 ADR 0015(CA·입구 인증서 방식), ADR 0005(EnvKind)로 바꿨다 |
| 180 | C.md 2806 `AlertReceiverUrl` | 어긋남 | 고침 | components.yaml `AlertReceiverUrl`: 수신처가 서버 밖이어야 한다는 주장을 지우고(D10 은 감시 배치의 원칙) 근거를 D10·RFC 6068·UD-19 로 바로잡았다 |
| 181 | C.md 2812 `PlatformEnv` | 없음 | 고침 | components.yaml `PlatformEnv`: 근거를 docs/design.md 4절로 바꾸고 입력마다 필요한 2절 컴포넌트를 description 에 적었다. 필요한 컴포넌트가 없는 입력(백업·서버 밖 백업 입력, 화면의 루트 인증서)은 지웠다 |
| 182 | C.md 2842 `ExposureAudience` | 없음 | 고침 | components.yaml `ExposureAudience`: 값과 뜻을 docs/design.md 4절(헤드 결정 2026-11-10)과 같게 맞추고 근거를 4절과 관련 결정으로 바꿨다 |
| 183 | C.md 2867 `ExternalEgressTarget` | 어긋남 | 고침 | components.yaml `ExternalEgressTarget`: 학습 서버를 egress 상대로 든 F66 근거를 지웠다(ADR 0019 로 학습 서버가 아니라 model-lab 잡이 나가는 쪽이다) |
| 184 | C.md 2878 `EgressTarget` | 어긋남 | 고침 | components.yaml `EgressTarget`: 학습 서버를 egress 상대로 든 F66 근거를 지웠다(ADR 0019 로 학습 서버가 아니라 model-lab 잡이 나가는 쪽이다) |
| 185 | C.md 2887 `Exposure.properties.routes` | 어긋남 | 고침 | components.yaml `Exposure.properties.routes`: routes 상한 산출을 전체 작업 수(건강 상태·지표 포함)로 바로잡았다. 현재 최대 29(survey-service) |
| 186 | C.md 2889 `ContainerPath` | 어긋남 | 고침 | components.yaml `ContainerPath`: POSIX PATH_MAX 가 4096 으로 고정이라는 주장을 지우고 Linux PATH_MAX 4096(바이트, NUL 포함)을 근거로 하고 글자 수와 바이트 수의 구분을 밝혔다 |
| 187 | C.md 2890 `EnvVarName` | 어긋남 | 고침 | components.yaml `EnvVarName`: 패턴을 POSIX 8.1 에 맞춰 첫 글자 밑줄을 허용하도록 고쳤다 |
| 188 | C.md 2897 `EnvKind` | 없음 | 고침 | components.yaml `EnvKind`: 근거를 ADR 0015(CA·입구 인증서 방식), ADR 0005(EnvKind)로 바꿨다 |
| 189 | C.md 2910 `RunAsUid` | 근거 없음 | 고침 | components.yaml `RunAsUid`: root 제외를 ADR 0004 와 CIS Docker Benchmark 4.1 로, 상한을 Linux uid_t 32비트에서 -1 제외로 근거를 댔다 |
| 190 | C.md 2916 `ContainerInputs` | 어긋남 | 고침 | components.yaml `ContainerInputs`: D134 원문의 항목(쓰기 경로의 유지 여부와 쓰는 사용자, 추가 권한, sysctls, 절대 경로 argv 를 역할·잡별로)을 모두 복원했다 |
| 191 | C.md 2922 `DatabaseEngine` | 근거 없음 | 고침 | components.yaml `DatabaseEngine`: 근거를 D85(6)과 D133 으로 바꾸고 ADR 0001 인용을 지웠다 |
| 192 | C.md 2923 `DatabaseMajorVersion` | 근거 없음 | 고침 | components.yaml `DatabaseMajorVersion`: 헤드가 정한 표준·사용자 결정(UD-21~UD-24, OIDC Core, RFC 5280, RFC 3986, ADR 0001)을 근거로 바꾸고 값을 맞췄다(JobTimeoutSeconds 86400→259200, MetricValue 상한 2147483647→2^53-1) |
| 193 | C.md 2934 `ContractsVersionLabel` | 어긋남 | 고침 | components.yaml `ContractsVersionLabel`: 패턴에서 선행 0 을 거부하도록 SemVer 2 에 맞췄다. 메이저 7 은 info.version 에서, 길이 64 는 계약의 선택임을 밝혔다 |
| 194 | C.md 2956 `ImageLabelSet` | 어긋남 | 고침 | components.yaml `ImageLabelSet`: 라벨 키 목록을 docs/design.md 4절(OCI 표준 주석 + io.openit.contracts 하나)로 근거를 바꿨다 |
| 195 | C.md 2966 `ServerName` | 어긋남 | 고침 | components.yaml `ServerName`: 패턴을 RFC 1123 2.1 의 label 문법(하이픈으로 끝나지 않음)으로 맞췄다 |
| 196 | C.md 18 `listCandidateModelPackages` | 없음 | 지움 | ADR 0019 로 model-lab 영역 문서가 없어져 작업 `listCandidateModelPackages` 를 지웠다 (커밋 a89a8eb) |
| 197 | C.md 37 `getModelPackage` | 없음 | 고침 | openapi/model-runtime.yaml `getModelPackage`: N07 에 넣었다(docs/design.md 3절: 모델 패키지 조회, 헤드 결정). candidate-reader 기계 역할은 없앴고 사람(operator, release-approver)이 평가 보고서를 보는 작업이다 |
| 198 | C.md 54 `downloadModelPackageArtifact` | 없음 | 지움 | ADR 0019 로 model-lab 영역 문서가 없어져 작업 `downloadModelPackageArtifact` 를 지웠다 (커밋 a89a8eb) |
| 199 | C.md 68 `listTrainingRequests` | 없음 | 지움 | ADR 0019 로 model-lab 영역 문서가 없어져 작업 `listTrainingRequests` 를 지웠다 (커밋 a89a8eb) |
| 200 | C.md 88 `downloadTrainingInputFile` | 없음 | 지움 | ADR 0019 로 model-lab 영역 문서가 없어져 작업 `downloadTrainingInputFile` 를 지웠다 (커밋 a89a8eb) |
| 201 | C.md 102 `publishTrainingRunResult` | 없음 | 지움 | ADR 0019 로 model-lab 영역 문서가 없어져 작업 `publishTrainingRunResult` 를 지웠다 (커밋 a89a8eb) |
| 202 | C.md 122 `uploadTrainingArtifact` | 없음 | 지움 | ADR 0019 로 model-lab 영역 문서가 없어져 작업 `uploadTrainingArtifact` 를 지웠다 (커밋 a89a8eb) |
| 203 | C.md 18 `extractAction` | 없음 | 고침 | openapi/model-runtime.yaml `extractAction`: inference-caller 권한 이름은 docs/design.md 4절(MachineRole)이 정본이고 MODEL_NOT_LOADED·QUESTION_BANK_VERSION_MISMATCH 는 ProblemReason 이 작업 이름과 model-runtime 의 package_loader 로 근거를 댄다(RELEASE_MISMATCH 는 지웠다) |
| 204 | C.md 36 `generateResponse` | 없음 | 고침 | openapi/model-runtime.yaml `generateResponse`: inference-caller 권한 이름은 docs/design.md 4절(MachineRole)이 정본이고 MODEL_NOT_LOADED·QUESTION_BANK_VERSION_MISMATCH 는 ProblemReason 이 작업 이름과 model-runtime 의 package_loader 로 근거를 댄다(RELEASE_MISMATCH 는 지웠다) |
| 205 | C.md 54 `getModelStatus` | 없음 | 고침 | openapi/model-runtime.yaml `getModelStatus`: inference-caller 권한 이름은 docs/design.md 4절(MachineRole)이 정본이고 MODEL_NOT_LOADED·QUESTION_BANK_VERSION_MISMATCH 는 ProblemReason 이 작업 이름과 model-runtime 의 package_loader 로 근거를 댄다(RELEASE_MISMATCH 는 지웠다) |
| 206 | C.md 19 `receiveTraceDelivery` | 없음 | 지움 | ADR 0019 로 ops-feedback 영역 문서가 없어져 작업 `receiveTraceDelivery` 를 지웠다 (커밋 a89a8eb) |
| 207 | C.md 55 `listFailureCaseExports` | 없음 | 고침 | openapi/survey-service.yaml `listFailureCaseExports`: case-reader 권한 이름은 docs/design.md 4절(MachineRole)이 정본이다 |
| 208 | C.md 92 `reviewFailureCase` | 어긋남 | 고침 | openapi/survey-service.yaml `reviewFailureCase`: 409 응답을 추가했다(CASE_VERSION_MISMATCH). 검토자 신원은 OIDC 접근 토큰의 sub 로 기록한다(design.md 3절) |
| 209 | C.md 127 `listFailureSignals` | 없음 | 지움 | ADR 0019 로 ops-feedback 영역 문서가 없어져 작업 `listFailureSignals` 를 지웠다 (커밋 a89a8eb) |
| 210 | C.md 19 `uploadMaterial` | 없음 | 지움 | ADR 0019 로 question-authoring 영역 문서가 없어져 작업 `uploadMaterial` 를 지웠다 (커밋 a89a8eb) |
| 211 | C.md 52 `listDrafts` | 없음 | 지움 | ADR 0019 로 question-authoring 영역 문서가 없어져 작업 `listDrafts` 를 지웠다 (커밋 a89a8eb) |
| 212 | C.md 87 `confirmDraft` | 없음 | 지움 | ADR 0019 로 question-authoring 영역 문서가 없어져 작업 `confirmDraft` 를 지웠다 (커밋 a89a8eb) |
| 213 | C.md 108 `getQuestionSetVersion` | 없음 | 고침 | openapi/survey-service.yaml `getQuestionSetVersion`: question-reader·candidate-reader 기계 역할을 없애고 문항 세트 올린 사람(author, OIDC)만 읽는 작업으로 바꿨다(model-lab 이 문항 정의를 읽는 흐름이 design.md 에 없다) |
| 214 | C.md 124 `approveClinically` | 없음 | 지움 | ADR 0019 로 question-authoring 영역 문서가 없어져 작업 `approveClinically` 를 지웠다 (커밋 a89a8eb) |
| 215 | C.md 139 `listCandidateQuestionSets` | 없음 | 지움 | ADR 0019 로 question-authoring 영역 문서가 없어져 작업 `listCandidateQuestionSets` 를 지웠다 (커밋 a89a8eb) |
| 216 | C.md 157 `listImprovementSignals` | 어긋남 | 지움 | ADR 0019 로 question-authoring 영역 문서가 없어져 작업 `listImprovementSignals` 를 지웠다 (커밋 a89a8eb) |
| 217 | C.md 21 `getActiveRelease` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `getActiveRelease` 를 지웠다 (커밋 a89a8eb) |
| 218 | C.md 35 `listReleases` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `listReleases` 를 지웠다 (커밋 a89a8eb) |
| 219 | C.md 54 `getRelease` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `getRelease` 를 지웠다 (커밋 a89a8eb) |
| 220 | C.md 71 `getReleaseQuestionSet` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `getReleaseQuestionSet` 를 지웠다 (커밋 a89a8eb) |
| 221 | C.md 87 `getReleaseModelPackage` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `getReleaseModelPackage` 를 지웠다 (커밋 a89a8eb) |
| 222 | C.md 104 `downloadReleaseArtifact` | 어긋남 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `downloadReleaseArtifact` 를 지웠다 (커밋 a89a8eb) |
| 223 | C.md 120 `activateRelease` | 어긋남 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `activateRelease` 를 지웠다 (커밋 a89a8eb) |
| 224 | C.md 139 `rollbackRelease` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `rollbackRelease` 를 지웠다 (커밋 a89a8eb) |
| 225 | C.md 176 `createSubmission` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `createSubmission` 를 지웠다 (커밋 a89a8eb) |
| 226 | C.md 196 `listSubmissions` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `listSubmissions` 를 지웠다 (커밋 a89a8eb) |
| 227 | C.md 216 `getSubmission` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `getSubmission` 를 지웠다 (커밋 a89a8eb) |
| 228 | C.md 232 `getReviewReport` | 어긋남 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `getReviewReport` 를 지웠다 (커밋 a89a8eb) |
| 229 | C.md 249 `decideSubmission` | 어긋남 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `decideSubmission` 를 지웠다 (커밋 a89a8eb) |
| 230 | C.md 270 `redecideSubmission` | 어긋남 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `redecideSubmission` 를 지웠다 (커밋 a89a8eb) |
| 231 | C.md 285 `listGateDecisions` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `listGateDecisions` 를 지웠다 (커밋 a89a8eb) |
| 232 | C.md 303 `createRollbackRequest` | 어긋남 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `createRollbackRequest` 를 지웠다 (커밋 a89a8eb) |
| 233 | C.md 322 `listRollbackRequests` | 없음 | 지움 | ADR 0019 로 release-gate 영역 문서가 없어져 작업 `listRollbackRequests` 를 지웠다 (커밋 a89a8eb) |
| 234 | C.md 23 `listActiveQuestionnaires` | 어긋남 | 고침 | openapi/survey-service.yaml `listActiveQuestionnaires`: 기기 신원 전달을 D113 의 X-Openit-Device 에서 Envoy 표준 헤더 X-Forwarded-Client-Cert 로 바꾼 근거를 docs/design.md 2절(platform 의 gateway 는 Envoy, 기기 인증서 mTLS)로 연결했다. 되묻기 한도 도달 시 서비스가 고정 안내를 쓰는 동작과 직원 호출 계기는 docs/v7-flow-resolutions.md 2026-11-10 결정(되묻기 1회+2회 뒤 건너뜀, 설명 요청 3번 뒤 직원 도움)을 따른다. 활성 문진표의 근거는 릴리스가 아니라 활성 문항 세트로 바꿨다 |
| 235 | C.md 57 `startSession` | 어긋남 | 고침 | openapi/survey-service.yaml `startSession`: START_CODE_INVALID·EXPIRED·USED 는 ProblemReason 이 작업(startSession)과 start_code 컴포넌트로 근거를 댄다. 기기 신원 헤더는 design.md 2절의 Envoy 입구로 바꿨다 |
| 236 | C.md 81 `submitTurn` | 어긋남 | 고침 | openapi/survey-service.yaml `submitTurn`: 기기 신원 전달을 D113 의 X-Openit-Device 에서 Envoy 표준 헤더 X-Forwarded-Client-Cert 로 바꾼 근거를 docs/design.md 2절(platform 의 gateway 는 Envoy, 기기 인증서 mTLS)로 연결했다. 되묻기 한도 도달 시 서비스가 고정 안내를 쓰는 동작과 직원 호출 계기는 docs/v7-flow-resolutions.md 2026-11-10 결정(되묻기 1회+2회 뒤 건너뜀, 설명 요청 3번 뒤 직원 도움)을 따른다. 활성 문진표의 근거는 릴리스가 아니라 활성 문항 세트로 바꿨다 |
| 237 | C.md 103 `endSession` | 어긋남 | 고침 | openapi/survey-service.yaml `endSession`: 기기 신원 전달을 D113 의 X-Openit-Device 에서 Envoy 표준 헤더 X-Forwarded-Client-Cert 로 바꾼 근거를 docs/design.md 2절(platform 의 gateway 는 Envoy, 기기 인증서 mTLS)로 연결했다. 되묻기 한도 도달 시 서비스가 고정 안내를 쓰는 동작과 직원 호출 계기는 docs/v7-flow-resolutions.md 2026-11-10 결정(되묻기 1회+2회 뒤 건너뜀, 설명 요청 3번 뒤 직원 도움)을 따른다. 활성 문진표의 근거는 릴리스가 아니라 활성 문항 세트로 바꿨다 |
| 238 | C.md 120 `getSessionState` | 어긋남 | 고침 | openapi/survey-service.yaml `getSessionState`: 기기 신원 전달을 D113 의 X-Openit-Device 에서 Envoy 표준 헤더 X-Forwarded-Client-Cert 로 바꾼 근거를 docs/design.md 2절(platform 의 gateway 는 Envoy, 기기 인증서 mTLS)로 연결했다. 되묻기 한도 도달 시 서비스가 고정 안내를 쓰는 동작과 직원 호출 계기는 docs/v7-flow-resolutions.md 2026-11-10 결정(되묻기 1회+2회 뒤 건너뜀, 설명 요청 3번 뒤 직원 도움)을 따른다. 활성 문진표의 근거는 릴리스가 아니라 활성 문항 세트로 바꿨다 |
| 239 | C.md 137 `requestStaffCall` | 어긋남 | 고침 | openapi/survey-service.yaml `requestStaffCall`: 기기 신원 전달을 D113 의 X-Openit-Device 에서 Envoy 표준 헤더 X-Forwarded-Client-Cert 로 바꾼 근거를 docs/design.md 2절(platform 의 gateway 는 Envoy, 기기 인증서 mTLS)로 연결했다. 되묻기 한도 도달 시 서비스가 고정 안내를 쓰는 동작과 직원 호출 계기는 docs/v7-flow-resolutions.md 2026-11-10 결정(되묻기 1회+2회 뒤 건너뜀, 설명 요청 3번 뒤 직원 도움)을 따른다. 활성 문진표의 근거는 릴리스가 아니라 활성 문항 세트로 바꿨다 |
| 240 | C.md 156 `decideIntervention` | 어긋남 | 고침 | openapi/survey-service.yaml `decideIntervention`: 경로를 D58(4)의 단수 경로 /v1/sessions/{id}/intervention 으로 되돌렸다 |
| 241 | C.md 192 `streamStaffAlerts` | 어긋남 | 고침 | openapi/survey-service.yaml `streamStaffAlerts`: text/event-stream 본문을 문자열 스트림(ServerSentEventStream)으로 하고 이벤트 data 스키마는 x-event-data-schema 로 따로 두었다. heartbeat·resync 에 id 가 없다는 D87 을 설명에 적었다 |
| 242 | C.md 258 `getResult` | 없음 | 고침 | openapi/survey-service.yaml `getResult`: 접근 기록 종류 이름(RESULT_PULLED·RESULT_VIEWED)을 계약에서 지웠다(영역 안의 값). 읽은 사람(OIDC sub 또는 호출자)과 때를 영역 안 접근 기록에 남긴다고만 적었다 |
| 243 | C.md 304 `receiveRiskSignal` | 없음 | 고침 | openapi/survey-service.yaml `receiveRiskSignal`: risk-detector 권한 이름은 docs/design.md 4절(MachineRole)이 정본이고 RISK_DETECTION_DISABLED·SESSION_NOT_ACTIVE 는 ProblemReason 이 작업과 link_risk_in·session 컴포넌트로 근거를 댄다. 위험 감지는 기본 꺼짐(L11, UD-18) |
| 244 | C.md 18 `listDatasetVersions` | 없음 | 지움 | ADR 0019 로 synthetic-data 영역 문서가 없어져 작업 `listDatasetVersions` 를 지웠다 (커밋 a89a8eb) |
| 245 | C.md 37 `getDatasetVersion` | 없음 | 지움 | ADR 0019 로 synthetic-data 영역 문서가 없어져 작업 `getDatasetVersion` 를 지웠다 (커밋 a89a8eb) |
| 246 | C.md 54 `downloadDatasetFile` | 없음 | 지움 | ADR 0019 로 synthetic-data 영역 문서가 없어져 작업 `downloadDatasetFile` 를 지웠다 (커밋 a89a8eb) |
| 247 | C.md 68 `createDatasetImport` | 없음 | 지움 | ADR 0019 로 synthetic-data 영역 문서가 없어져 작업 `createDatasetImport` 를 지웠다 (커밋 a89a8eb) |
| 248 | C.md 89 `getDatasetImport` | 없음 | 지움 | ADR 0019 로 synthetic-data 영역 문서가 없어져 작업 `getDatasetImport` 를 지웠다 (커밋 a89a8eb) |
| 249 | C.md 106 `uploadDatasetFile` | 없음 | 지움 | ADR 0019 로 synthetic-data 영역 문서가 없어져 작업 `uploadDatasetFile` 를 지웠다 (커밋 a89a8eb) |
| 250 | C.md 129 `completeDatasetImport` | 없음 | 지움 | ADR 0019 로 synthetic-data 영역 문서가 없어져 작업 `completeDatasetImport` 를 지웠다 (커밋 a89a8eb) |
