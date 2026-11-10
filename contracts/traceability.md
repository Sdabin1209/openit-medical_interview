# 흐름과 계약의 대응 (F01~F74)

흐름의 정본은 `flows.md`, 충돌 정리는 `../docs/v7-flow-resolutions.md`(우선)다. 작업은 `openapi/<서비스>.yaml` 의 operationId, 스키마는 `components.yaml` 의 이름이다. 구현 칸이 "계약 밖"이면 사유를 적었다.

| F번호 | 구현 | 작업(operationId, 서비스) | 스키마 | 비고·사유 |
|---|---|---|---|---|
| F01 | 구현 | uploadMaterial, createDraftFromForm (question-authoring) | MaterialUpload, DraftFormInput, QuestionSetContent | 사람 입구는 admin-console 화면(C01). 형식은 정하지 않고 화면 입력으로 언제나 등록(D33) |
| F02 | 구현 | uploadMaterial, createDraftFromForm, getDraftPreview, listDrafts (question-authoring) | DraftPreview, DraftPage, PreviewWarning | 읽지 못하면 PARSE_FAILED 초안으로 알리고 화면 입력으로 잇는다 |
| F03 | 구현 | confirmDraft (question-authoring) | DraftConfirmation, QuestionSetVersion, ReviewRecord | 미리보기 해시에 묶여 확정. 2인 승인은 기본 꺼짐(C02, L13) |
| F04 | 구현 | approveClinically (question-authoring) | ReviewRecord, TwoPersonApprovalRequired | 2인 승인을 켠 설치에서만 쓴다. 꺼져 있으면 흐름이 없다(C02) |
| F05 | 구현 | listCandidateQuestionSets (question-authoring), 잡 COLLECT_CANDIDATES | QuestionSetCandidatePage, ReviewRecord, ChangeClass, JobDeclaration | 가져가는 쪽이 release-gate(candidate-reader). 주기는 deploy 가 선언된 시간 상한에서 정한다(C08) |
| F06 | 구현 | listCandidates, createSubmission (release-gate) | CandidatePage, SubmissionRequest, Submission, GateCheck | 구조가 다른 문진표 세트는 QUESTION_STRUCTURE_MISMATCH(U81, U85) |
| F07 | 구현 | listCandidateModelPackages, getModelPackage, downloadModelPackageArtifact (model-lab) | ModelPackageManifest, EvaluationReport, AdapterEntry | 평가 보고서는 model-lab 이 만든다(C06) |
| F08 | 구현 | getReviewReport (release-gate) | ReviewReport, MetricComparison | 해시는 서버만 계산(D69) |
| F09 | 구현 | decideSubmission, redecideSubmission (release-gate) | ApprovalRequest, GateDecision, HumanDecision | 승인자는 인증된 개인 계정(D88 U7). 사람이 결정한 접수는 재판정하지 않는다(D105) |
| F10 | 구현 | activateRelease, rollbackRelease, listReleases, listRollbackRequests (release-gate) | ActivationRequest, RollbackCommand, ActiveRelease, RollbackRequest | 개별 계정으로 연다(C07) |
| F11 | 구현 | getActiveRelease, getRelease, getReleaseQuestionSet (release-gate) | ActiveRelease, ReleaseManifest, QuestionSetVersion | 규칙 세대가 설치본과 다르면 받는 쪽이 적재를 거부(D46, RELEASE_VERSION_MISMATCH) |
| F12 | 구현 | getActiveRelease, getReleaseModelPackage, downloadReleaseArtifact (release-gate) | ModelPackageManifest, AdapterEntry, ServingConfig, ArtifactRef | 추론 서버가 스스로 읽는다(C05) |
| F13 | 구현 | getActiveRelease (release-gate) | ActiveRelease, OpsFeedbackEnv | 읽는 목적은 결정에 적혀 있지 않다(flows.md 비고 그대로, 계약은 읽기 작업만 정의) |
| F14 | 구현 | createRollbackRequest (release-gate) | RollbackRequestCreate, RollbackRequest, RollbackAutoSubmit | 사람(reviewer, operator)이 CONFIRMED 사례를 근거로 요청한다(C21, L07). 기계 경로(ops-feedback)는 자동 제출 설정이 켜진 설치에서만 쓰며 기본은 꺼짐이다 |
| F15 | 구현 | getQuestionSetVersion, listCandidateQuestionSets (question-authoring) | QuestionBank, QuestionItem, QuestionFieldSpec | model-lab 이 question-reader 권한으로 읽기만 한다(D49) |
| F16 | 구현 | getQuestionSetVersion, listCandidateQuestionSets (question-authoring) | QuestionBank, QuestionSetVersion | synthetic-data 가 question-reader 권한으로 읽기만 한다(D49) |
| F17 | 구현 | createDatasetImport, uploadDatasetFile, completeDatasetImport, getDatasetImport (synthetic-data) | DatasetImportRequest, DatasetImport, DatasetRow, ChatMessage | 사용 허락 확인됨(C25). 리포에는 합성 시험 샘플만 둔다 |
| F18 | 구현 | listDatasetVersions, getDatasetVersion, downloadDatasetFile (synthetic-data) | DatasetManifest, DatasetFileDeclaration, DatasetFileSet, ArtifactRef | 지정 버전을 model-lab 이 읽어 간다 |
| F19 | 구현 | listFailureCaseExports (ops-feedback), 잡 PUBLISH_SEEDS | FailureCaseExport, FailureCaseExportPage | case-reader 권한. 비식별 사례만 나가고 환자 발화 원문은 없다(D15, L17) |
| F20 | 구현 | listFailureCaseExports (ops-feedback) | FailureCaseExport, ReviewStatus | review_status=CONFIRMED 로 회귀 평가 집합을 읽는다(D52(2)). 발화 원문은 없다 |
| F21 | 구현 | listFailureSignals (ops-feedback) | FailureSignal, FailureSignalPage, ConfusionCase | signal-reader 권한(question-authoring) |
| F22 | 구현 | listImprovementSignals (question-authoring) | ImprovementSignal, ImprovementSignalPage | 저자 경로는 별도 인증 뒤(D88 U9) |
| F23 | 영역 안 | 없음(키오스크 화면 안, 발화는 F29 의 submitTurn 으로 간다) | UtteranceText | 음성은 기기 안에서 글자로 바꾸고 외부 STT 로 보내지 않으며 Web Speech API 는 쓰지 않는다(C12). 변환 구현 선택은 kiosk-frontend 몫 |
| F24 | 결정 대기 | 없음(화면 출력, 문장은 F30 의 응답으로 온다) | ResponseSentence | 응답 문장의 음성 출력을 기기 안에서만 할지 정해지지 않았다(user-decisions-needed UD-12) |
| F25 | 구현 | issueStartCode, startSession (survey-service) | StartCodeIssueRequest, StartCode, SessionStartRequest, SubjectRef | 직원이 발급한 일회용 시작 코드(C20). 설치처 연동은 만들지 않는다 |
| F26 | 구현(HTTP 밖) | 없음(배포 때 파일 입력) | DevicePlacementTable, SurveyServiceEnv(SURVEY_DEVICE_PLACEMENTS_FILE), DevicePlacement | 기기별 기본 문진표 배치표를 survey-service 가 받아 mTLS 로 확인된 기기 ID 로 고른다(U86). 기기 토큰은 없앴다(D136) |
| F27 | 계약 밖 | 없음(조직 PKI 가 기기에 인증서를 준다) | DeviceAllowlist, DeviceAllowEntry | 발급·폐기는 조직 몫(D113). 허용 목록 입력은 F54 의 PlatformEnv 로 deploy 가 준다(C13) |
| F28 | 구현 | securityScheme device_mtls (모든 기기 경로), 헤더 매개변수 ForwardedClientCert | DeviceId, DeviceSerialNumber, DeviceAllowlist, ForwardedClientCertValue | 영역 게이트웨이가 인증서를 검증하고 Envoy 표준 헤더로 넘긴다. 서비스는 게이트웨이와의 mTLS 에서만 그 헤더를 믿는다(D136, RFC 8705) |
| F29 | 구현 | startSession, submitTurn, endSession (survey-service) | SessionStartRequest, SessionStarted, TurnRequest, SessionEnded, TurnId | 같은 turn_id 재전송은 멱등(D55). 환자 식별 정보는 키오스크에 없다 |
| F30 | 구현 | submitTurn, listActiveQuestionnaires (survey-service) | TurnResponse, TurnFailureReason, ActiveQuestionnaireList | 실패 신호는 세션 상태를 바꾸지 않는다(D75(1)) |
| F31 | 구현 | getSessionState (survey-service) | SessionState, PauseReason | 2초 폴링(D66(6)) |
| F32 | 구현 | requestStaffCall (survey-service) | StaffAlert, AlertKind | 직원 호출 알림이 닿지 않았을 때 키오스크가 다시 부른다. 되묻기 한도는 호출이 아니라 건너뛰기다(사용자 결정 U36) |
| F33 | 구현 | extractAction, generateResponse (model-runtime) | ExtractionRequest, ResponseGenerationRequest, ActionExtractionInput, ResponseRequest, ModelIoVersion | 모델 입출력 v2(데이터셋 정본). 시작(START)은 응답 문장만 부른다(D74). 입력 직렬화는 ModelInputSerialization(D77) |
| F34 | 구현 | extractAction, generateResponse (model-runtime) | ExtractionResult, ActionExtraction, ActionExtractionRules, ResponseResult, ProblemReason(OUTPUT_INVALID, RELEASE_MISMATCH) | 받는 쪽은 다시 검증하지 않는다(D104(3)). 합격 조건은 ActionExtractionRules |
| F35 | 구현 | getModelStatus (model-runtime) | ModelStatus, ModelLoadState | 적재는 추론 서버가 일으킨다(C05) |
| F36 | 구현 | receiveTraceDelivery (ops-feedback) | TraceDelivery, TurnTrace, BusinessLogEntry, TraceDeliveryReceipt | 최소 1회 전달, 중복 제거는 ops-feedback(D16) |
| F37 | 구현 | receiveRiskSignal (survey-service) | RiskSignal, RiskCategory | 위험 감지는 기본 꺼짐(C04, L11). 분류 목록은 임상 검토 전 임시(D88 U2). 외부 감지기가 발화를 얻는 길은 정해지지 않았다(UD-18) |
| F38 | 구현 | listStaffAlerts, streamStaffAlerts, registerPushSubscription (survey-service) | StaffAlert, StaffAlertPage, StaffAlertEvent, WebPushPayload | 받는 쪽은 C01 에 따라 admin-console 이다(flows.md 는 kiosk-frontend 의 두 번째 앱으로 적었으나 C01 이 우선). 알림 종류는 위험, 직원 호출, 결과 도착 |
| F39 | 구현 | registerPushSubscription, getPushConfig, decideIntervention (survey-service) | PushSubscription, PushConfig, InterventionDecision | 표준 Web Push(RFC 8030, 8291, 8292, C11). 푸시 서비스는 계약 밖 표준 |
| F40 | 구현 | decideIntervention (survey-service) | InterventionDecision, InterventionAction | 직원 화면은 admin-console(C01) |
| F41 | 구현 | listResults, getResult, listStaffAlerts, streamStaffAlerts (survey-service) | SessionResult, ResultPage, AlertKind(RESULT_READY), WebPushPayload | 화면을 닫은 의사에게는 웹 푸시(U92). 결과에 환자 발화 원문은 없다 |
| F42 | 구현 | acknowledgeResult (survey-service) | ResultAcknowledgement | 접근 기록도 남는다(U83) |
| F43 | 영역 안 | 없음(admin-console 화면 조작, 화면이 F41·F42 의 작업을 부른다) | SessionResult, ResultPage | 인쇄는 화면 기능. clinician 역할(U83) |
| F44 | 구현 | listResults, getResult, getResultFhir (survey-service) | SessionResult, FhirQuestionnaireResponse, ResultPage | 당겨 가기만(C10). machine_token result-reader. 밀어 보내기는 만들지 않는다 |
| F45 | 구현 | reviewFailureCase (ops-feedback) | CaseReview, FailureCase | 같은 검토는 멱등(D71(3)) |
| F46 | 구현 | listFailureCases, getFailureCase, getDeidentifiedTrace (ops-feedback, reviewer 역할만) | FailureCase, FailureCasePage, DeidentifiedTrace | 검토용 발화 원문 180일(L12). 검토자와 승인자는 역할 분리(D71(1)) |
| F47 | 구현 | listSubmissions, getSubmission, getReviewReport, decideSubmission (release-gate) | Submission, SubmissionPage, ReviewReport, ApprovalRequest | F08·F09 의 화면 쪽 중계(C01) |
| F48 | 영역 안 | 없음(admin-console 화면 조작, 화면이 F45·F46 의 작업을 부른다) | FailureCase, CaseReview | reviewer 역할 |
| F49 | 영역 안 | 없음(admin-console 화면 조작, 화면이 F47 의 작업을 부른다) | ApprovalRequest, ReviewReport | release-approver 역할 |
| F50 | 계약 밖(표준) | 없음(Keycloak 의 OIDC 로그인과 가입 신청) | UserRole, UserIdentityClaims | 표준 IdP(U82). securityScheme oidc 가 서비스 쪽 요구를 정한다 |
| F51 | 계약 밖(표준) | 없음(Keycloak 관리 기능으로 가입 승인과 역할 부여) | UserRole | 초기 admin 계정은 임시 비밀번호(U82). 역할 이름만 계약이 정의한다 |
| F52 | 구현 | securityScheme oidc (사람 호출을 받는 모든 작업) | UserIdentityClaims, RealmAccessClaim, UserId, OidcIssuerUrl | 서비스가 JWT 의 서명을 IdP 공개 키(JWKS)로 검증한다(RFC 9068). 승인·검토 기록에 개인 ID(D88 U7) |
| F53 | 계약 밖(표준) | 없음(step-ca 의 ACME, RFC 8555) | CaMode, IngressCertificateMode, AcmeDirectoryUrl, 서비스 Env 의 OPENIT_ROOT_CERTIFICATE_FILE·OPENIT_TLS_CERTIFICATE_FILE·OPENIT_TLS_PRIVATE_KEY_FILE | 인증서 발급은 표준 프로토콜이 정본(C14). 방식과 신뢰 앵커와 인증서 파일 경로만 환경 입력으로 계약에 있다 |
| F54 | 구현(HTTP 밖) | 없음(배포가 환경 입력과 비밀 파일 경로를 준다) | SurveyServiceEnv, ReleaseGateEnv, QuestionAuthoringEnv, OpsFeedbackEnv, ModelRuntimeEnv, ModelLabEnv, SyntheticDataEnv, KioskFrontendEnv, AdminConsoleEnv, PlatformEnv, MachineTokenTable, SecretFilePath | 비밀은 환경 변수가 아니라 NAME_FILE 경로(D84) |
| F55 | 구현(HTTP 밖) | 없음(스케줄러가 잡을 한 번 실행) | JobName, JobDeclaration, JobsDeclaration, JobRunInput, JobRunResult | 영역은 시간 상한만 선언하고 주기는 deploy 가 정한다(C08, D131) |
| F56 | 구현(HTTP 밖) | 없음(백업·복구 잡) | JobName(BACKUP, RESTORE), JobRunInput, JobRunResult, BackupSnapshotId | 데이터 주인은 저장소를 가진 영역 전부(C15) |
| F57 | 계약 밖(표준) | 없음(restic REST 저장소 프로토콜) | BackupRepositoryUrl, OffsiteBackupUrl, BackupSnapshotId | 서버 밖 대상이 필수이고 주소는 설정(C09) |
| F58 | 구현 | 서비스마다 Healthz, Readyz, Metrics (예: surveyServiceHealthz) | HealthReport, HealthCheck, PrometheusExposition | 건강 본문은 draft-inadarei-api-health-check 모양으로 한 번 정의(U101 의 공백을 닫음) |
| F59 | 구현(HTTP 밖) | 없음(Prometheus Alertmanager 가 알림을 낸다) | AlertReceiverUrl, PlatformEnv | 알림 수신처는 platform 의 환경 입력이다. 서버 전체 중단은 보증하지 않고 서버 밖 감시로 알린다(D10) |
| F60 | 구현(HTTP 밖) | 없음(이미지 라벨) | ImageDeclaration, ImageLabelSet, ContainerInputs, Exposure, JobsDeclaration, DatabaseDeclaration | 선언은 이미지 라벨에 싣고(라벨 키는 ImageLabelSet), deploy 는 이미지 안을 열지 않는다(D134) |
| F61 | 계약 밖(표준 도구) | 없음(Docker Buildx Bake 가 리포 루트에서 빌드) | 없음 | 모노레포라 요청 버전은 커밋 하나다(ADR 0002, ADR 0004) |
| F62 | 계약 밖(표준) | 없음(OCI Distribution 레지스트리) | ImageRevision | 이미지 게시는 표준 레지스트리 프로토콜(D24, ADR 0004) |
| F63 | 계약 밖(표준) | 없음(OCI Distribution 레지스트리, images.lock 의 digest) | ImageRevision | digest 로 고정해 받는다(ADR 0002, ADR 0004) |
| F64 | 구현(HTTP 밖) | 없음(운영자가 파일로 준다) | DeploymentLayout, ServerEntry, DevicePlacement | 열림 U97 은 설계 방향만 확정(flows.md 비고) |
| F65 | 계약 밖(표준) | 없음(모델 허브에서 가중치 내려받기) | ModelRuntimeEnv(OPENIT_MODEL_CACHE_DIR), BaseModelName | 모델 허브 프로토콜이 정본. 캐시 폴더는 유지된다(D73) |
| F66 | 결정 대기 | 없음 | TrainingRunRequest, ArtifactRef | 값은 정의했으나 학습 서버에 전하는 방식이 정해지지 않았다(UD-16). 설정 파일의 내용은 학습 서버 코드가 정본(D78, G06) |
| F67 | 구현 | publishTrainingRunResult, uploadTrainingArtifact (model-lab) | TrainingRunResult, TrainingRunReceipt, ArtifactContent | 학습 서버가 HTTPS 게시 API 로 올린다(C16) |
| F68 | 계약 밖(구조) | 없음(contracts 폴더 자체와 생성 타입) | 없음 | 모노레포의 contracts/ 가 정본이고 소비자는 생성 타입만 쓴다(ADR 0002) |
| F69 | 구현(정의) | 없음(components.yaml 의 정의) | QuestionBank, QuestionFlowTable, QuestionFieldSpec, SessionResult | 문진 스키마(문항·칸·순서표·결과)의 주인은 survey-service, 모델 입출력의 주인은 head 다(D19, D21, D75(2), D104(2)) |
| F70 | 계약 밖(코드 라이브러리) | 없음(libs/link) | 없음 | 영역 통신 기반은 라이브러리 의존이며 영역 사이 HTTP 가 아니다(D118) |
| F71 | 계약 밖(코드 라이브러리) | 없음(libs/model-runtime) | 없음 | 라이브러리 의존이며 영역 사이 HTTP 가 아니다(D06) |
| F72 | 계약 밖(절차) | 없음(헤드가 contracts/ 를 커밋으로 바꾼다) | 없음 | 계약 변경 중에는 영역에 일을 맡기지 않는다(D19) |
| F73 | 계약 밖(절차) | 없음(영역 브리프와 변경 지시 문서) | 없음 | 사람과 에이전트 사이의 문서이며 시스템 값이 아니다 |
| F74 | 계약 밖(절차) | 없음(docs/change-requests 의 변경 요청 문서) | 없음 | 영역은 계약을 직접 고치지 않고 요청을 낸다(D19, D21) |
