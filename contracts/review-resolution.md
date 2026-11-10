# 독립 검토 57건의 처리

검토 파일은 `NoneCommit/review-contract-opus.md` 이다. 번호는 검토 파일의 번호와 같다. 처리 수는 고침 52, 일부 고침 3, 고치지 않음(결정 대기) 2 이다.

| 번호 | 처리 | 내용 |
|---|---|---|
| 1 | 고침 | `ActionReason` 에 `CONFLICT_DOES_NOT_DRINK` 를 넣어 정본 20종과 같게 했다. 근거 문구는 실측 범위(final 과 finaltest 의 A 출력 48747행)로 고쳤다 |
| 2 | 고침 | 건너뛰기를 정본으로 정했다. `PauseReason.REASK_LIMIT_EXCEEDED` 와 `AlertKind.REASK_EXCEEDED` 를 지웠고 `ReaskLimit` 의 근거를 사용자 결정 U36 과 U100 으로 바꿨다(D95 를 대체). traceability F32·F38 을 고쳤다 |
| 3 | 고침 | `FailureCaseExport`(발화 원문과 모델 출력 없음)와 `listFailureCaseExports` 를 만들어 machine_token 경로를 그쪽으로 옮겼다. `listFailureCases` 와 `getFailureCase` 는 reviewer 역할만 읽는다 |
| 4 | 고침 | 서비스가 JWT 서명을 IdP 공개 키(JWKS)로 검증한다(RFC 9068). `UserIdentityClaims` 는 읽는 클레임의 부분집합으로 바꾸고 그 밖의 클레임을 허용한다. 기기 ID 는 Envoy 표준 헤더 `X-Forwarded-Client-Cert` 로 넘기고 게이트웨이가 클라이언트가 보낸 헤더를 지우며 서비스는 게이트웨이와의 mTLS 에서만 믿는다. 영역 사이는 mTLS 와 기계 토큰(`area_mtls`, `machine_token`)이다 |
| 5 | 고침 | v2 사본에서 `confirming`, `MEANING_ASKED`, `REASK_LIMIT`(모델 사유로서)을 뺐다. `ModelIoVersion`(model-io-v2)을 `ModelPackageManifest`, `ReleaseManifest`, `ReleaseSummary`, `ModelStatus` 에 싣고 v3 후보는 `model-io-v3-proposal.md` 와 `dataset-change-requests.md` 로만 뒀다. README 에 버전 구조와 모델 통신 컴포넌트를 서술했다 |
| 6 | 고침 | `ResponseRequest`, `ActionExtraction`, `ExtractedValue` 에 action·reason 별 `if/then` 을 넣었고 `ResponseNext`(END 와 NEXT·SAME), `CaseReview`(CONFIRMED 이면 expected)도 조건부 필수로 했다. 조건은 final 과 finaltest 의 A 출력 48747행이 모두 만족하는 것을 확인한 뒤 넣었다 |
| 7 | 고침 | `ModelInputSerialization`(직렬화 규칙 데이터)와 요청의 `state_key_order` 를 정의했다. 데이터셋 불일치 두 건은 DC-05·DC-06 으로 올렸다 |
| 8 | 고침 | `ActionExtractionRules`(저장 상태, reason 없는 행동, targets 가 필요한 행동, 행동별 next_item 규칙, 재질문 단계에서는 서비스 순서가 우선한다는 문장)를 정의하고 save·precision 규칙은 `ExtractedValue` 의 스키마로 옮겼다. 검사기의 위치(libs/model-runtime)를 명세 설명에 적었다 |
| 9 | 고침 | `ReaskLimit` 이 세는 대상(REASK 와 CONFIRM 의 연속, G12)을 정의에 적었다. 설명 요청 면제와 직원 도움 안내는 모델 입출력 v3 부터 동작한다고 `ExplainStreakLimit`, `StaffHelpNotice` 에 적었다. 직원 도움 안내 문장은 서비스 고정 문장으로 정하고 DC-04 는 변경 없음으로 닫았다. 재질문 단계는 survey-service 내부이고 순서 우선 문장은 `ActionExtractionRules` 에 넣었다 |
| 10 | 고침 | 문항·칸·순서표·`RuntimeContractVersion` 의 x-owner 를 survey-service 로(D19, D21, D75(2)), 모델 입출력 값과 합격 조건과 데이터셋 행은 head 로(D104(2)) 바꿨다. traceability F69 도 맞췄다 |
| 11 | 고침 | `DevicePlacementTable` 과 `SURVEY_DEVICE_PLACEMENTS_FILE` 을 survey-service 입력으로 두고 `KioskDeviceSettings` 와 키오스크의 설정 파일 입력을 지웠다. F26 을 고쳤다 |
| 12 | 고침 | 기기 귀속(다른 기기에는 404)을 submitTurn, endSession, getSessionState, requestStaffCall 의 설명과 README 규칙에 적었다 |
| 13 | 고침 | startSession 에 429(기기별·코드별 실패 시도 한도), 422(START_CODE_INVALID), 409(START_CODE_EXPIRED, START_CODE_USED)를 정의하고 같은 기기가 같은 코드로 다시 시작하면 같은 세션을 200 으로 돌려주게 했다 |
| 14 | 고침 | `Idempotency-Key` 매개변수를 issueStartCode, createSubmission, createRollbackRequest, createDatasetImport 에 두고 receiveRiskSignal 과 startSession 은 자연 키(세션·분류·감지 시각, 기기와 코드)로 했다. README 규칙에 목록을 넣었다 |
| 15 | 고침 | createRollbackRequest 에 사람(reviewer, operator)의 oidc 경로를 더하고 기계 경로는 `OPSFEEDBACK_ROLLBACK_AUTO_SUBMIT`(기본 거짓)이 켜진 설치에서만 쓰게 했다. `RollbackRequest` 에 요청자를 더했다 |
| 16 | 고침 | "후보는 필요한 승인이 모두 끝난 버전만 나온다"를 계약 규칙으로 정했다(`QuestionSetCandidate`, `GateCheckName.CLINICAL_APPROVAL` 설명). 게이트는 저자 확인만 본다 |
| 17 | 고침 | `Exposure.egress` 의 항목을 `EgressTarget`(서비스 또는 `ExternalEgressTarget` 의 호스트와 포트)으로 넓혔다. 목록 크기는 UD-11 이다 |
| 18 | 고침 | `ExposureAudience.EXTERNAL_MACHINE_TOKEN` 을 더하고 외부 기계 호출자는 TLS 와 기계 토큰으로 받는 영역의 게이트웨이로 직접 온다고 정했다(C16 과 D129). 그 작업의 보안 요구에는 `area_mtls` 가 없다 |
| 19 | 고침 | 모든 서비스 Env 에 `OPENIT_ROOT_CERTIFICATE_FILE`, `OPENIT_TLS_CERTIFICATE_FILE`, `OPENIT_TLS_PRIVATE_KEY_FILE` 을 필수로 넣었고 platform 에 `CaMode`, `IngressCertificateMode`, `OPENIT_ACME_DIRECTORY_URL`, `OPENIT_TRUST_LIST_FILE`, `OPENIT_TLS_ROOT_CERTIFICATE_FILE` 을 넣었다 |
| 20 | 고침 | 영역별 `OPENIT_BACKUP_HTTP_CREDENTIALS_FILE` 과 `OPENIT_BACKUP_ENCRYPTION_KEY_FILE`, platform 의 서버 밖 대상 자격과 암호화 키 파일, 사람 인증 DB 입력, 잡 `OFFSITE_SYNC` 와 `RESTORE_TEST` 를 넣었다. 서버 밖 대상이 없으면 시작하지 않고 경보를 낸다는 규칙은 `OPENIT_OFFSITE_BACKUP_URL` 설명에 적었다 |
| 21 | 고침 | `PlatformEnv` 에 수신 포트, 초기 admin 비밀번호 파일, 경보 수신처, 노출 선언 폴더, CA 비밀, 인증서 방식, 사람 인증 DB 를 넣었다. traceability F59 를 "구현(HTTP 밖)"으로 고쳤다 |
| 22 | 고침 | `TimeBudgetTable` 과 값마다의 상수 스키마(D125 의 사슬, heartbeat 15초, 폴링 2초)를 정의했다. 유휴 초기화 시간(D88 U10)은 값이 확인되지 않아 UD-17 로 올렸다 |
| 23 | 고침 | `x-required-roles` 를 지우고 역할을 `security` 요구에 역할 이름으로 적었다. 경고를 내는 `oas3-operation-security-defined` 는 `openapi/*.yaml` 에만 끄고 사유(OpenAPI 3.1.0 4.8.30)를 규칙 파일 주석에 적었다. 경고는 0건이다 |
| 24 | 고침 | 미디어 유형을 `application/json` 으로 바꾸고 근거에 "만료된 초안을 참고한 자체 모양"이라고 적었다 |
| 25 | 일부 고침 | README 에 모든 검증기가 format 단언을 켠다는 규칙을 적고 모든 uuid 에 `pattern` 과 `maxLength` 를 함께 뒀다. 린트 규칙(`openit-string-range`)은 규칙 파일의 openit 규칙을 고치지 않는다는 제약이라 바꾸지 않았다 |
| 26 | 고침 | `ProblemReason` 을 쓰이는 값 20개로 다시 정했고 각 값의 설명에 그 값을 내는 작업을 적었다. 쓰이지 않던 값(RELEASE_VERSION_MISMATCH, DUPLICATE_DELIVERY)은 지웠고 `TurnFailureReason.DEADLINE_EXCEEDED` 는 턴 결과의 신호라 의미가 달라 그대로 뒀다. 주요 작업 설명에도 사유를 적었다 |
| 27 | 일부 고침 | `SubjectRef` 에 pattern 을 넣었다. 조회의 query 값은 불투명 참조값(식별 정보가 아님)이라 로그에 남아도 식별되지 않아 GET 을 그대로 뒀다 |
| 28 | 고침 | `FhirMapping`(세션 상태, 빈칸 사유, linkId·subject·questionnaire 규칙)과 `FhirCanonicalBaseUrl` 환경 입력을 정의했고 FHIR 조회의 오류는 `FhirOperationOutcome`(OperationOutcome)으로 정했다 |
| 29 | 고침 | 추출·응답 요청에 `release_id` 를 싣고 응답에 처리한 `release_id` 를 담게 했다(`ExtractionRequest`, `ExtractionResult`, `ResponseGenerationRequest`, `ResponseResult`). 다르면 409 `RELEASE_MISMATCH` 다 |
| 30 | 고치지 않음(결정 대기) | 학습 서버에 요청을 전하는 방식은 결정이 없다. traceability F66 을 "결정 대기"로 고치고 UD-16 으로 올렸다 |
| 31 | 고침 | 쪽이 아닌 목록은 UD-10, 식별 이름 길이는 UD-14 로 올려 빌린 표준을 지웠다. `RetryAfterSeconds` 는 D125 의 재시도 예산 120초로, `MetricValue` 는 단위(`MetricUnit`)를 더하고 int32 한계로 바꿨다 |
| 32 | 고침 | `DeploymentLayout.servers` 상한을 서비스 수 10(구조 값)으로 바꾸고 근거의 ADR 인용을 지웠으며 U97 의 방식은 UD-15 로 올렸다 |
| 33 | 고침 | `SlotNumber` 를 안전한 수 범위(RFC 7493)로 넓혀 칸별 범위를 칸 규격이 정하게 했다 |
| 34 | 고침 | `DatasetFileSet`(final, finaltest)을 더하고 `DatasetFiles` 를 8개로 했으며 근거 문구를 고쳤다. 묶음 이름 확인은 DC-08 이다 |
| 35 | 고침 | `BlankReason.NOT_ASKED` 를 더하고 모델 사유에서 빈칸 원인으로 옮기는 규칙을 설명에 적었다 |
| 36 | 고치지 않음(결정 대기) | 음성 출력의 외부 전송은 외부 공개 범주라 사용자 결정이 필요하다. traceability F24 를 "결정 대기"로 고치고 UD-12 로 올렸다 |
| 37 | 고침 | `ImageLabelSet` 에 라벨 키와 값의 대응을 정의했다. 값의 최대 길이는 UD-13 이다 |
| 38 | 고침 | `securitySchemes`, `parameters`, `headers`, `responses` 를 `components.yaml` 한 곳에 두고 서비스 문서는 `$ref` 로 참조한다. 역할을 요구하는 모든 작업에 403 을 뒀다(스크립트로 확인) |
| 39 | 고침 | flows.md 와 v7-flow-resolutions 의 영역 수를 12개로 고쳤다 |
| 40 | 고침 | requestStaffCall 과 receiveRiskSignal 의 202 를 201(새로 만듦)과 200(같은 알림을 다시 알림)으로 바꿨다 |
| 41 | 고침 | `Unauthorized` 응답에 `WWW-Authenticate` 헤더를 정의했다 |
| 42 | 고침 | 검토에서 든 칸(DatasetManifest.name·origin, DatasetImport.status, TrainingRunResult.outcome, DevicePlacement.device_id, DatabaseDeclaration, FailureSignal 의 문진표·문항, GateDecision.reason)의 설명에 언제 채워지고 무엇을 가리키는지 적었다. 참조한 컴포넌트가 뜻을 담고 있는 나머지 짧은 설명은 그대로 뒀다 |
| 43 | 고침 | `HostAddress`(hostname, ipv4, ipv6), `DeidentifiedUtterance`, `TurnCount`, `PassFail` 로 나누거나 합쳤고 `ResponseSentence` 와 `CurrentQuestionText` 의 상한을 같게 했다. `EgressProxyUrl` 의 주인은 영역 게이트웨이 이미지를 소유하는 platform(D127)이라 그대로 뒀다 |
| 44 | 고침 | `SlotAnswer` 에 자유 글 갈래(`SlotText`)를 더하고 oneOf 를 anyOf 로 바꿨다 |
| 45 | 고침 | GateChecks 5, DeliveryCount 200, 환경 입력 칸 수의 셈, START 119, `StartCodeTtlSeconds` 의 근거(NIST 5.1.3.2)와 기본 300초(UD-04 권고값)를 맞췄다 |
| 46 | 고침 | 구조상 최대인 값에는 2배를 곱하지 않고 그 값(answers 와 blanks 68, tokens 14, routes 21)을 썼다 |
| 47 | 고침 | `HostAddress` 로 IPv6 를 받게 했다 |
| 48 | 고침 | `ProblemType` 을 절대 URI(`https://openit/problems/<reason>`)와 `about:blank` 로 정했다 |
| 49 | 고침 | `streamStaffAlerts` 설명에 각 이벤트의 data 모양과 heartbeat 간격을 적었다. 이벤트 단위 스키마는 OpenAPI 3.2 로 올릴 때 옮긴다 |
| 50 | 고침 | components 와 openapi 의 표현을 "설치처의 의료 정보 시스템", "설치처 직원"으로 바꿨다 |
| 51 | 고침 | `ArtifactId` 설명에 올리는 쪽이 만든 UUID 라고 적고 README 규칙을 같게 했다 |
| 52 | 일부 고침 | 업로드에 `Repr-Digest`(RFC 9530)와 413 을 더하고 크기 상한은 Content-Length 로 강제한다고 적었다. `maxLength` 는 린트가 상한을 요구해 남겼고 글자 수 단위의 한계를 설명에 적었다 |
| 53 | 고침 | `DatabaseUrl` 을 `postgresql://` 만 받게 했다 |
| 54 | 고침 | `TraceDelivery` 에 `minProperties: 1` 을 뒀다 |
| 55 | 고침 | `BusinessLogEntry` 에 `actor_client` 를, `BusinessEventKind` 에 `RESULT_VIEWED` 와 `RESULT_PULLED` 를 더했다 |
| 56 | 고침 | `CaseReview` 에 `base_case_version` 을 필수로 두고 최신이 아니면 409 `CASE_VERSION_MISMATCH` 로 했다 |
| 57 | 고침 | DC-05~DC-08 을 더했고 F37 의 감지기 입력 경로는 UD-18 로 올렸다 |
