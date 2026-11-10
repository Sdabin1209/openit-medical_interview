# 독립 검토 77건의 처리

검토 파일은 `NoneCommit/review-contract-opus.md`(번호 1~57)와 `NoneCommit/review-contract-codex.md`(번호 C1~C20)다. 증거 칸은 이 문서를 만든 시점의 파일 위치(파일:줄)와 계약 시험 이름이며, 위치는 스크립트가 파일을 찾아 적었다. 증거를 대지 못하는 항목은 "고침"으로 적지 않았다.

처리 수: 고침 73, 일부 고침 4, 고치지 않음 0 (합계 77).

| 번호 | 처리 | 내용 | 증거 |
|---|---|---|---|
| 1 | 고침 | `ActionReason` 에 `CONFLICT_DOES_NOT_DRINK` 를 넣어 정본 20종과 같게 했고 근거를 실측 범위로 고쳤다 | components.yaml:1124 |
| 2 | 고침 | `PauseReason` 과 `AlertKind` 에서 되묻기 초과를 지웠고 `ReaskLimit` 근거를 사용자 결정 U36 으로 바꿨다 | components.yaml:403; components.yaml:2488 |
| 3 | 고침 | 기계 독자용 `FailureCaseExport` 와 `listFailureCaseExports` 를 만들고 원문 작업에서 기계 토큰을 뺐다 | components.yaml:1632; openapi/ops-feedback.yaml:55; 시험 "실패 사례: 기계 독자용 모양에는 발화 원문이 없고, CONFIRMED …"; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| 4 | 고침 | JWT 서명은 서비스가 JWKS 로 검증하고(RFC 9068) 기기 신원은 `X-Forwarded-Client-Cert` 로 넘긴다. 영역 사이는 mTLS 와 기계 토큰이다 | components.yaml:317; components.yaml:2996; components.yaml:2979; 시험 "JWT 클레임은 RFC 9068 필수 클레임이 빠지면 거부하고 그 밖의 …" |
| 5 | 고침 | v2 사본에서 v3 값을 빼고 `ModelIoVersion` 을 릴리스·패키지에 싣고 v3 후보는 별도 문서로 뒀다 | components.yaml:1041; model-io-v3-proposal.md:1; 시험 "모델 패키지: LORA_A 와 LORA_B 가 하나씩이 아니면 거부한다…" |
| 6 | 고침 | `ResponseRequest`, `ActionExtraction`, `ExtractedValue`, `ResponseNext`, `CaseReview` 에 조건부 필수를 넣었다 | components.yaml:1285; 시험 "ResponseRequest: 정본 행은 받고 행동별 필수·금지 키와 n…"; 시험 "ActionExtraction: 정본 행은 받고 행동별 reason·ta…" |
| 7 | 고침 | `ModelInputSerialization` 과 요청의 `state_key_order` 를 정의하고 데이터셋 불일치를 DC-05·DC-06 으로 올렸다 | components.yaml:1092; components.yaml:1207; dataset-change-requests.md:11 |
| 8 | 고침 | `ActionExtractionRules` 를 정의하고 save·precision 규칙을 `ExtractedValue` 스키마로 옮겼다 | components.yaml:1077; 시험 "ExtractedValue: save 와 status, 값 없음과 pre…" |
| 9 | 고침 | `ReaskLimit` 이 세는 대상을 정의하고 v3 의존 기능은 `ModelIoFeatureRequirements` 와 README 에 비활성 조건으로 적었다 | components.yaml:2488; components.yaml:1040; README.md:72; 시험 "모델 입출력 v3 의존 기능은 v3 이상에서만 켜진다고 표로 정의한다…" |
| 10 | 고침 | 문항·칸·순서표의 x-owner 를 survey-service 로, 모델 입출력 값은 head 로 바꿨다 | components.yaml:694; components.yaml:1041 |
| 11 | 고침 | `DevicePlacementTable` 과 `SURVEY_DEVICE_PLACEMENTS_FILE` 을 survey-service 입력으로 두고 키오스크 설정 입력을 지웠다 | components.yaml:2505; components.yaml:2548 |
| 12 | 고침 | 세션을 시작한 기기의 ID 로만 접근하게 하고 다른 기기에는 404 로 숨긴다 | openapi/survey-service.yaml:84; README.md:41 |
| 13 | 고침 | startSession 에 429, 422, 409 와 같은 기기의 재시작 멱등을 정의했다 | openapi/survey-service.yaml:73; openapi/survey-service.yaml:72 |
| 14 | 고침 | `Idempotency-Key` 를 4개 만들기 작업에 두고 위험 신호와 시작은 자연 키를 쓴다 | components.yaml:3007; openapi/release-gate.yaml:183; 시험 "작업: 멱등 키는 필요한 작업에만 있고 위험 신호는 자연 키를 쓴다…" |
| 15 | 고침 | `createRollbackRequest` 에 reviewer 와 operator 의 oidc 대안을 두고 자동 제출 설정을 더했다 | openapi/release-gate.yaml:308; components.yaml:2610; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| 16 | 고침 | 후보는 필요한 승인이 끝난 버전만 나온다는 규칙을 정의했다 | components.yaml:819 |
| 17 | 고침 | `Exposure.egress` 가 `EgressTarget`(서비스 또는 외부 호스트와 포트)을 참조하고 상한이 32다 | components.yaml:2855; 시험 "구조의 숫자가 서로 맞는다(같은 구조에서 산출)…" |
| 18 | 고침 | `EXTERNAL_MACHINE_TOKEN` 대상을 더하고 외부 기계 호출자는 영역 게이트웨이로 직접 온다고 정했다 | components.yaml:2806 |
| 19 | 고침 | 모든 서비스 Env 에 루트 인증서와 서비스 인증서·키 파일 입력을 넣었다 | components.yaml:2515; components.yaml:2528 |
| 20 | 고침 | 영역별 백업 자격·암호화 키 파일과 `OFFSITE_SYNC`·`RESTORE_TEST` 잡을 넣었다 | components.yaml:2546; components.yaml:2408 |
| 21 | 고침 | `PlatformEnv` 에 admin 비밀번호, 경보 수신처, 노출 선언 폴더, CA 와 인증서 방식을 넣었다 | components.yaml:2774; components.yaml:2785 |
| 22 | 고침 | `TimeBudgetTable` 과 값별 상수(유휴 초기화 60초 포함)를 정의했다 | components.yaml:103; components.yaml:83 |
| 23 | 고침 | 역할을 `security` 표준 자리에 쓰고 표준 규칙 하나만 사유와 함께 껐다 | lint/ruleset.yaml:112; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| 24 | 고침 | 건강 본문의 미디어 유형을 application/json 으로 바꾸고 자체 모양이라고 적었다 | components.yaml:171; openapi/platform.yaml:25 |
| 25 | 일부 고침 | format 단언 규칙을 README 에 적고 모든 uuid 에 pattern 과 maxLength 를 뒀다. openit 린트 규칙은 바꾸지 않았다 | README.md:33; 시험 "구조의 숫자가 서로 맞는다(같은 구조에서 산출)…" |
| 26 | 고침 | `ProblemReason` 을 쓰이는 20개로 정하고 각 값에 내는 작업을 적었다 | components.yaml:35 |
| 27 | 일부 고침 | `SubjectRef` 에 pattern 을 넣었다. query 값은 식별 정보가 아닌 불투명 참조값이라 GET 을 유지했다 | components.yaml:360 |
| 28 | 고침 | `FhirMapping` 과 OperationOutcome 오류를 정의했다 | components.yaml:1483; components.yaml:2514 |
| 29 | 고침 | 추출·응답 요청에 `release_id` 를 싣고 응답에 처리한 릴리스를 담는다 | components.yaml:1216 |
| 30 | 고침 | 사용자 결정 UD-16 에 따라 학습 서버가 당겨 가는 작업을 만들었다 | openapi/model-lab.yaml:68 |
| 31 | 고침 | 쪽이 아닌 목록은 UD-10, 식별 이름은 UD-14 로 근거를 바꾸고 RetryAfter 와 MetricValue 를 고쳤다 | components.yaml:76; components.yaml:1806 |
| 32 | 고침 | `DeploymentLayout.servers` 상한을 서비스 수 10 으로 하고 근거를 UD-15 로 적었다 | components.yaml:2963 |
| 33 | 고침 | `SlotNumber` 를 안전한 수 범위로 넓혔다 | components.yaml:640 |
| 34 | 고침 | `DatasetFileSet` 을 더하고 `DatasetFiles` 를 8개로 했다 | components.yaml:1966; components.yaml:1986 |
| 35 | 고침 | `BlankReason.NOT_ASKED` 와 사유 대응을 정의했다 | components.yaml:1354 |
| 36 | 고침 | 사용자 결정 UD-12 에 따라 음성 출력도 기기 안에서만 처리한다고 적었다 | components.yaml:387 |
| 37 | 고침 | `ImageLabelSet` 에 라벨 키를 정의했다 | components.yaml:2918 |
| 38 | 고침 | 공유 응답·보안·매개변수 정의를 components.yaml 한 곳에 뒀다 | components.yaml:2966; components.yaml:3020; 시험 "작업: 역할을 요구하면 403 이 있고 401 에는 WWW-Authent…" |
| 39 | 고침 | flows.md 의 영역 수를 12로 고쳤다 | flows.md:20 |
| 40 | 고침 | 202 를 201 과 200 으로 바꿨다 | openapi/survey-service.yaml:147 |
| 41 | 고침 | `Unauthorized` 에 WWW-Authenticate 헤더를 정의했다 | components.yaml:3017; 시험 "작업: 역할을 요구하면 403 이 있고 401 에는 WWW-Authent…" |
| 42 | 고침 | 빈 설명을 보강했다 | components.yaml:2005 |
| 43 | 고침 | `HostAddress`, `DeidentifiedUtterance`, `PassFail` 으로 나누거나 합쳤다 | components.yaml:2497; components.yaml:2147 |
| 44 | 고침 | `SlotText` 갈래를 더했다 | components.yaml:984 |
| 45 | 고침 | GateChecks 5, DeliveryCount 200 으로 맞추고 TTL 근거와 기본 300초를 적었다 | components.yaml:2166; components.yaml:1581; components.yaml:2487 |
| 46 | 고침 | 구조상 최대값을 그대로 썼다(68, 14, 21) | components.yaml:1395; components.yaml:285 |
| 47 | 고침 | `HostAddress` 가 IPv4 와 IPv6 를 받는다 | components.yaml:2496 |
| 48 | 고침 | `ProblemType` 을 절대 URI 로 정했다 | components.yaml:17 |
| 49 | 고침 | 스트림 설명에 data 모양과 heartbeat 간격을 적었다 | openapi/survey-service.yaml:195 |
| 50 | 고침 | 표현을 "설치처의 의료 정보 시스템" 으로 바꿨다 | components.yaml:247 |
| 51 | 고침 | `ArtifactId` 설명에 올리는 쪽이 만든 UUID 라고 적었다 | components.yaml:1713 |
| 52 | 일부 고침 | 업로드에 `Repr-Digest` 와 413 을 더했다. maxLength 는 린트 요구로 남겼다 | components.yaml:3001; openapi/model-lab.yaml:139; 시험 "작업: 업로드에는 Repr-Digest 와 413 이 있다…" |
| 53 | 고침 | `DatabaseUrl` 을 `postgresql://` 만 받게 했다 | components.yaml:2483 |
| 54 | 고침 | `TraceDelivery` 에 `minProperties: 1` 을 뒀다 | components.yaml:1574 |
| 55 | 고침 | `BusinessLogEntry` 에 `actor_client` 와 읽기 사건 종류를 더했다 | components.yaml:1562; components.yaml:1545 |
| 56 | 고침 | `CaseReview.base_case_version` 을 필수로 했다 | components.yaml:1679; 시험 "실패 사례: 기계 독자용 모양에는 발화 원문이 없고, CONFIRMED …" |
| 57 | 고침 | DC-05~DC-08 을 더했고 F37 은 UD-18 로 정리했다 | dataset-change-requests.md:14; traceability.md:43 |
| C1 | 고침 | `ReprDigestValue` 의 최대 길이를 54 로 고치고 RFC 9530 의 실제 헤더 값으로 검증한다 | components.yaml:184; 시험 "Repr-Digest: RFC 9530 의 실제 예시를 받고 길이가 어긋…" |
| C2 | 고침 | `listFailureCases`·`getFailureCase` 에서 기계 토큰을 뺐다(검토자만) | openapi/ops-feedback.yaml:36; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| C3 | 고침 | `Exposure.egress` 가 `EgressTarget` 을 참조하고 상한 32다 | components.yaml:2855; 시험 "구조의 숫자가 서로 맞는다(같은 구조에서 산출)…" |
| C4 | 고침 | 대체 역할마다 별도 Security Requirement Object 로 나눴다 | openapi/survey-service.yaml:180; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| C5 | 고침 | `createRollbackRequest` 에 reviewer·operator 의 oidc 대안을 더했다 | openapi/release-gate.yaml:308; 시험 "보안: 역할마다 별도 요구이고(OR), 원문 경로에 기계 토큰이 없다…" |
| C6 | 고침 | JWT 검증 설정(발급자, JWKS, 허용 aud)을 검증하는 서비스 Env 4개에 뒀다 | components.yaml:2525; components.yaml:2524 |
| C7 | 고침 | START 와 행동별 필수·금지 키와 next 조합을 정본 생성 결과대로 스키마에 넣었다 | components.yaml:1301; 시험 "ResponseRequest: 정본 행은 받고 행동별 필수·금지 키와 n…" |
| C8 | 고침 | FHIR 와 클레임 스키마에 객체 유형과 필수 칸(status, issue 등)을 넣었다. FHIR 나머지 칸은 FHIR 사양이 정본이라 참조한다 | components.yaml:1441; 시험 "FHIR QuestionnaireResponse 는 status 가 없으…"; 시험 "FHIR OperationOutcome 은 issue 가 없거나 비어 있…" |
| C9 | 고침 | v3 의존 기능의 비활성과 활성 조건을 README 와 결정 문서에 적고 계약 표로 뒀다 | README.md:72; ../docs/v7-flow-resolutions.md:51; components.yaml:1040; 시험 "모델 입출력 v3 의존 기능은 v3 이상에서만 켜진다고 표로 정의한다…" |
| C10 | 고침 | `ResultBlank` 가 반복 키를 포함한 칸 참조 `key` 를 쓴다 | components.yaml:1378; 시험 "결과 빈칸은 반복 키까지 칸을 가린다…" |
| C11 | 고침 | `DatasetImport.pending_artifact_ids` 를 8로, 환경 입력 선언 상한을 칸 수 이상으로 맞췄다 | components.yaml:2048; 시험 "구조의 숫자가 서로 맞는다(같은 구조에서 산출)…" |
| C12 | 고침 | 어댑터 구성, 성공한 학습 결과, CONFIRMED 사례, 비율 단위 값의 불변조건을 스키마에 넣었다 | components.yaml:1874; 시험 "모델 패키지: LORA_A 와 LORA_B 가 하나씩이 아니면 거부한다…"; 시험 "학습 결과: 성공인데 어댑터나 실행 기록이 없으면 거부한다…"; 시험 "지표: 비율 단위의 값은 1 을 넘으면 거부한다…" |
| C13 | 고침 | `BusinessEventId` 와 필수 session_id·행위자 조건을 넣었다 | components.yaml:1549; 시험 "업무 로그: event_id 가 없거나 필요한 행위자가 없으면 거부한다…" |
| C14 | 고침 | 필수 지표의 계산식·단위·분모·slice 와 필수 Prometheus 지표(U71)를 정의했다 | components.yaml:1753; components.yaml:1791 |
| C15 | 고침 | 위험 신호의 멱등 키 참조를 지우고 FHIR 401·503 에 헤더를 뒀다 | components.yaml:3055; components.yaml:3059; 시험 "작업: 멱등 키는 필요한 작업에만 있고 위험 신호는 자연 키를 쓴다…"; 시험 "작업: 역할을 요구하면 403 이 있고 401 에는 WWW-Authent…" |
| C16 | 고침 | 표준이 범위를 정하지 않는 값은 프로젝트 선택 상한(UD-19~UD-22)으로 근거를 바꾸고 63·18 계산을 바로잡았다 | components.yaml:16; components.yaml:265; components.yaml:630; user-decisions-needed.md:53 |
| C17 | 고침 | RFC 9068 프로파일(typ, 필수 클레임, aud 배열과 로컬 프로파일)을 스키마와 README 표로 정의했다 | components.yaml:307; README.md:55; 시험 "JOSE 헤더: typ 이 at+jwt 가 아니거나 alg 가 none …" |
| C18 | 고침 | `ObservationCount` 로 합치고 `TokenAudience` 를 `ServiceName` 참조로 바꾸고 설명을 보충했다 | components.yaml:921; components.yaml:296 |
| C19 | 일부 고침 | `JsonPointer` 를 RFC 6901 5 로 고치고 삭제된 "되묻기 초과" 문구를 지웠다. RFC 9457 의 title 3.1.3, status 3.1.2 는 RFC 원문으로 확인해 그대로 뒀다 | components.yaml:49; components.yaml:19 |
| C20 | 고침 | 이 문서를 다시 쓰고 package.json 설명을 고쳤다. | package.json:4 |
