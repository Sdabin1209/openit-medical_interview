# 흐름과 계약의 대응

각 흐름(N01~N14, `flows.md`)이 어느 작업과 스키마로 구현되는지 적는다. 작업은 `openapi/*.yaml`, 스키마는 `components.yaml` 에 있다. 아래 스키마 목록은 그 흐름의 작업(작업 없는 흐름은 대표 스키마)에서 `$ref` 를 따라간 전체(참조의 닫힘)이고 이 문서를 만들 때 계산한 것이다. 한 스키마가 여러 흐름에 쓰이면 여러 번 나온다.

## N01 kiosk-frontend → survey-service

- 무엇: 세션 시작(시작 코드, 문진표 선택), 환자 발화 턴(글자와 턴 ID), 세션 종료, 세션 상태 확인, 직원 다시 부르기
- 작업: listActiveQuestionnaires, startSession, startSessionStream, submitTurn, submitTurnStream, endSession, getSessionState, requestStaffCall
- 대표 스키마: ActiveQuestionnaireList, SessionStartRequest, StartCodeValue, TurnRequest, UtteranceText, TurnId, SessionId
- 참조의 닫힘 25개: Timestamp, DeviceId, QuestionnaireId, QuestionnaireTitle, QuestionnaireSummary, ActiveQuestionnaireList, StartCodeValue, SessionId, TurnId, UtteranceText, ResponseSentence, QuestionItemId, SessionStatus, PauseReason, TurnFailureReason, StaffHelpNotice, SessionStartRequest, SessionStarted, TurnRequest, TurnResponse, SessionEnded, SessionState, AlertId, AlertKind, StaffAlert

## N02 survey-service → kiosk-frontend

- 무엇: N01 작업의 응답: 세션 시작 결과, 턴 응답(다음 질문, 응답 문장, 실패 신호), 세션 상태, 활성 문진표 목록
- 작업: 같은 작업의 응답(startSession, startSessionStream, submitTurn, submitTurnStream, endSession, getSessionState, listActiveQuestionnaires)
- 대표 스키마: SessionStarted, TurnResponse, SessionEnded, SessionState, TurnFailureReason, PauseReason, ResponseSentence
- 참조의 닫힘 25개: Timestamp, DeviceId, QuestionnaireId, QuestionnaireTitle, QuestionnaireSummary, ActiveQuestionnaireList, StartCodeValue, SessionId, TurnId, UtteranceText, ResponseSentence, QuestionItemId, SessionStatus, PauseReason, TurnFailureReason, StaffHelpNotice, SessionStartRequest, SessionStarted, TurnRequest, TurnResponse, SessionEnded, SessionState, AlertId, AlertKind, StaffAlert

## N03 survey-service → model-runtime

- 무엇: 추출 요청(지금 문항, 직전에 물은 문항, 직전 화면 문장, 발화, 저장된 칸 값, 순서표, 칸 규격, 문항 은행 버전)과 응답 문장 요청(행동, 사유, 추출 출력의 값·칸·노트, 발화, 저장된 칸 값, 다음 자리). 모델 입력의 글은 요청에 없고 model-runtime 이 만든다
- 작업: extractAction, generateResponse, generateResponseStream
- 대표 스키마: ExtractionRequest, ResponseGenerationRequest, StoredSlots, ResponseNext, QuestionFlowTable, QuestionFieldSpecs, RuntimeContractVersion, ActionExtractionRules
- 참조의 닫힘 64개: UtteranceText, ResponseSentence, QuestionItemId, SlotKey, SlotRefString, RepeatKey, RepeatKeys, SlotDataType, SlotUnit, SlotNumber, OptionCode, OptionLabel, QuestionOption, QuestionOptions, QuestionFieldSpec, QuestionFieldSpecs, QuestionText, FlowTarget, FlowComparison, ConditionValue, FlowCondition, FlowBranch, FlowRule, QuestionFlowTable, RuntimeContractVersion, YesNoAnswer, NoValue, SlotText, SlotAnswer, StoredSlotStatus, StoredSlot, StoredSlots, ModelIoFeature, MinimumModelIoVersion, ModelIoFeatureRequirement, ModelIoFeatureRequirements, NextItemRuleKind, NextItemRule, CurrentItemScope, CurrentItemRule, ActionExtractionRules, AlphabeticalOrder, EnsureAscii, InsertionOrder, ModelInputSerialization, ExtractionAction, ActionReason, ValueStatus, ValuePrecision, ValueSave, ExtractedValue, ExtractedValues, SlotRefStrings, OutOfSchemaNote, ActionExtraction, ExtractionRequest, ExtractionResult, ResponseAction, ResponseNextType, ResponseNext, ResponseGenerationRequest, ResponseResult, OciDigest, ViolationCode

## N04 model-runtime → survey-service

- 무엇: N03 작업의 응답: 검증을 마친 추출 결과 또는 출력 불가(503 OUTPUT_INVALID), 응답 문장, 적재 상태
- 작업: 같은 작업의 응답과 getModelStatus
- 대표 스키마: ExtractionResult, ActionExtraction, ResponseResult, ModelStatus, ModelLoadState, ViolationCode, ProblemDetails
- 참조의 닫힘 55개: Timestamp, UserId, UtteranceText, ResponseSentence, QuestionItemId, SlotKey, SlotRefString, RepeatKey, RepeatKeys, SlotDataType, SlotUnit, SlotNumber, OptionCode, OptionLabel, QuestionOption, QuestionOptions, QuestionFieldSpec, QuestionFieldSpecs, QuestionText, FlowTarget, FlowComparison, ConditionValue, FlowCondition, FlowBranch, FlowRule, QuestionFlowTable, RuntimeContractVersion, YesNoAnswer, NoValue, SlotText, SlotAnswer, StoredSlotStatus, StoredSlot, StoredSlots, ModelIoVersion, ExtractionAction, ActionReason, ValueStatus, ValuePrecision, ValueSave, ExtractedValue, ExtractedValues, SlotRefStrings, OutOfSchemaNote, ActionExtraction, ExtractionRequest, ExtractionResult, ResponseAction, ResponseNextType, ResponseNext, ResponseGenerationRequest, ResponseResult, ModelLoadState, ModelStatus, OciDigest

## N05 admin-console → survey-service

- 무엇: 시작 코드 발급, 결과 조회·확인 표시, 문항 세트 올리기·활성화, 실패 사례 검토, 직원 개입, 알림 목록·구독
- 작업: issueStartCode, listResults, getResult, getResultFhir, acknowledgeResult, uploadQuestionSet, listQuestionSetVersions, getQuestionSetVersion, activateQuestionSet, listFailureCases, getFailureCase, reviewFailureCase, getDeidentifiedTrace, decideIntervention, listStaffAlerts, streamStaffAlerts, getPushConfig, registerPushSubscription
- 대표 스키마: StartCodeIssueRequest, QuestionSetUpload, QuestionSetVersion, ActiveQuestionSet, CaseReview, InterventionDecision, PushSubscription
- 참조의 닫힘 104개: Timestamp, PageCursor, UserId, DeviceId, QuestionnaireId, QuestionnaireTitle, SubjectRef, StartCodeValue, StartCodeIssueRequest, StartCode, SessionId, UtteranceText, ResponseSentence, QuestionItemId, SessionStatus, PauseReason, TurnFailureReason, SessionState, AlertId, AlertKind, StaffAlert, StaffAlertPage, AlertEventName, EventSequence, StaffAlertEvent, ServerSentEventStream, InterventionAction, InterventionDecision, PushEndpoint, PushPublicKey, PushAuthSecret, PushKeys, PushSubscription, PushSubscriptionId, PushSubscriptionRegistered, PushConfig, SlotKey, SlotRefString, RepeatKey, RepeatKeys, SlotDataType, SlotUnit, SlotNumber, OptionCode, OptionLabel, QuestionOption, QuestionOptions, QuestionFieldSpec, QuestionFieldSpecs, QuestionText, QuestionItem, QuestionItems, QuestionBank, FlowTarget, FlowComparison, ConditionValue, FlowCondition, FlowBranch, FlowRule, QuestionFlowTable, QuestionSetContent, Sha256Digest, Int32Positive, RuntimeContractVersion, QuestionSetVersionId, QuestionSetVersion, QuestionSetUpload, QuestionSetVersionPage, ActiveQuestionSet, YesNoAnswer, NoValue, SlotText, SlotAnswer, ExtractionAction, ActionReason, ValueStatus, ValuePrecision, ValueSave, ExtractedValue, ExtractedValues, SlotRefStrings, OutOfSchemaNote, ActionExtraction, BlankReason, ResultAnswer, ResultBlank, SessionResult, ResultSummary, ResultPage, ResultAcknowledgement, FhirResourceType, FhirQuestionnaireResponse, FhirResponseStatus, CaseId, CaseVersion, FailureKind, ReviewStatus, ReviewedInput, FailureCase, FailureCasePage, CaseReview, DeidentifiedUtterance, DeidentifiedTrace, QuestionSetVersionIsActive

## N06 survey-service → admin-console

- 무엇: N05 작업의 응답: 시작 코드, 결과, 알림, 문항 세트 목록, 실패 사례와 비식별 턴 기록
- 작업: 같은 작업의 응답
- 대표 스키마: StartCode, SessionResult, ResultPage, StaffAlert, StaffAlertEvent, QuestionSetVersionPage, FailureCase, FailureCasePage, DeidentifiedTrace, WebPushPayload
- 참조의 닫힘 105개: Timestamp, PageCursor, UserId, DeviceId, QuestionnaireId, QuestionnaireTitle, SubjectRef, StartCodeValue, StartCodeIssueRequest, StartCode, SessionId, UtteranceText, ResponseSentence, QuestionItemId, SessionStatus, PauseReason, TurnFailureReason, SessionState, AlertId, AlertKind, StaffAlert, StaffAlertPage, AlertEventName, EventSequence, StaffAlertEvent, ServerSentEventStream, InterventionAction, InterventionDecision, PushEndpoint, PushPublicKey, PushAuthSecret, PushKeys, PushSubscription, PushSubscriptionId, PushSubscriptionRegistered, PushConfig, WebPushPayload, SlotKey, SlotRefString, RepeatKey, RepeatKeys, SlotDataType, SlotUnit, SlotNumber, OptionCode, OptionLabel, QuestionOption, QuestionOptions, QuestionFieldSpec, QuestionFieldSpecs, QuestionText, QuestionItem, QuestionItems, QuestionBank, FlowTarget, FlowComparison, ConditionValue, FlowCondition, FlowBranch, FlowRule, QuestionFlowTable, QuestionSetContent, Sha256Digest, Int32Positive, RuntimeContractVersion, QuestionSetVersionId, QuestionSetVersion, QuestionSetUpload, QuestionSetVersionPage, ActiveQuestionSet, YesNoAnswer, NoValue, SlotText, SlotAnswer, ExtractionAction, ActionReason, ValueStatus, ValuePrecision, ValueSave, ExtractedValue, ExtractedValues, SlotRefStrings, OutOfSchemaNote, ActionExtraction, BlankReason, ResultAnswer, ResultBlank, SessionResult, ResultSummary, ResultPage, ResultAcknowledgement, FhirResourceType, FhirQuestionnaireResponse, FhirResponseStatus, CaseId, CaseVersion, FailureKind, ReviewStatus, ReviewedInput, FailureCase, FailureCasePage, CaseReview, DeidentifiedUtterance, DeidentifiedTrace, QuestionSetVersionIsActive

## N07 admin-console → model-runtime

- 무엇: 모델 적재 상태 조회, 게시된 모델 패키지 목록, 평가 보고서 확인, 활성화 승인, 롤백(승인자 신원은 OIDC 토큰의 sub)
- 작업: getModelStatus, listModelPackages, getModelPackage, activateModelPackage, rollbackModelPackage
- 대표 스키마: ModelStatus, ModelPackageList, ModelPackageManifest, ActivationRequest, RollbackCommand, ModelChangeReason, OciDigest
- 참조의 닫힘 39개: Timestamp, UserId, RuntimeContractVersion, ModelIoVersion, ModelLoadState, ModelChangeReason, ActivationRequest, RollbackCommand, ModelStatus, SemanticVersion, BaseModelName, AdapterRole, ByteSize, OciDigest, ModelPackageBlobMediaType, ModelPackageBlobDescriptor, TokenLimit, SamplingTemperature, ConstrainedDecoding, ServingConfig, AdapterEntry, RequiredMetricName, MetricName, ExtraMetricName, MetricGroupName, MetricSlice, MetricUnit, MetricValue, SampleCount, EvaluationMetric, DatasetVersionId, EvaluationReport, TrainingRunId, TrainingLineage, ModelPackageManifest, ModelPackageList, ModelPackageSummary, ModelPackageIsActive, PageCursor

## N08 병원 시스템 → survey-service

- 무엇: 결과를 당겨 가기(JSON 과 FHIR R4 QuestionnaireResponse)
- 작업: listResults, getResult, getResultFhir
- 대표 스키마: SessionResult, FhirQuestionnaireResponse, FhirMapping, FhirOperationOutcome
- 참조의 닫힘 37개: Timestamp, PageCursor, FhirIssueSeverity, FhirIssueCode, FhirIssue, FhirOperationOutcome, FhirOutcomeResourceType, UserId, DeviceId, QuestionnaireId, QuestionnaireTitle, SubjectRef, SessionId, QuestionItemId, SessionStatus, SlotRefString, SlotNumber, OptionCode, QuestionSetVersionId, YesNoAnswer, NoValue, SlotText, SlotAnswer, ValuePrecision, BlankReason, ResultAnswer, ResultBlank, SessionResult, ResultSummary, ResultPage, FhirResourceType, FhirQuestionnaireResponse, FhirResponseStatus, FhirAbsentReason, FhirStatusMapEntry, FhirAbsentMapEntry, FhirMapping

## N09 model-lab → survey-service

- 무엇: 확정된(CONFIRMED) 비식별 실패 사례를 당겨 가기
- 작업: listFailureCaseExports
- 대표 스키마: FailureCaseExport, FailureCaseExportPage
- 참조의 닫힘 29개: Timestamp, PageCursor, QuestionnaireId, QuestionItemId, SlotRefString, SlotNumber, OptionCode, FlowTarget, YesNoAnswer, NoValue, SlotText, SlotAnswer, ExtractionAction, ActionReason, ValueStatus, ValuePrecision, ValueSave, ExtractedValue, ExtractedValues, SlotRefStrings, OutOfSchemaNote, ActionExtraction, CaseId, CaseVersion, FailureKind, ReviewStatus, ReviewedInput, FailureCaseExport, FailureCaseExportPage

## N10 model-lab → 레지스트리 → model-runtime

- 무엇: 모델 패키지(OCI 아티팩트, artifactType 으로 구분, digest 로 고정)
- 작업: HTTP 작업 없음(OCI Distribution 표준이 전송). model-runtime 이 getModelPackage 와 activateModelPackage 로 digest 를 받는다
- 대표 스키마: ModelPackageOciManifest, ModelPackageManifest, EvaluationReport, ModelPackageBlobDescriptor, ModelPackageArtifactType, ModelPackageBlobMediaType, OciDigest, OciImageManifestMediaType
- 참조의 닫힘 35개: Timestamp, RuntimeContractVersion, ModelIoVersion, SemanticVersion, BaseModelName, AdapterRole, ByteSize, OciDigest, ModelPackageArtifactType, ModelPackageBlobMediaType, ModelPackageBlobDescriptor, OciImageManifestMediaType, OciSchemaVersion, ModelPackageOciManifest, TokenLimit, SamplingTemperature, ConstrainedDecoding, ServingConfig, AdapterEntry, RequiredMetricName, MetricName, ExtraMetricName, MetricGroupName, MetricSliceDimension, ViolationCode, MetricSlice, MetricUnit, MetricValue, SampleCount, EvaluationMetric, DatasetVersionId, EvaluationReport, TrainingRunId, TrainingLineage, ModelPackageManifest

## N11 외부 데이터셋 담당 → model-lab

- 무엇: 확정된 학습·평가 데이터(입출력 규칙은 labels.py 와 IO_SPEC.md)
- 작업: HTTP 작업 없음(파일을 잡 입력 폴더 OPENIT_DATASET_DIR 에 둔다)
- 대표 스키마: DatasetManifest, DatasetFileDeclaration, DatasetFileRef, DatasetRow, ChatMessage
- 참조의 닫힘 21개: Timestamp, Sha256Digest, RuntimeContractVersion, AdapterRole, ByteSize, DatasetVersionId, DatasetSplit, RowCount, DatasetFileSet, DatasetFileRef, DatasetFileDeclaration, DatasetFiles, DatasetName, DatasetOrigin, DatasetManifest, HumanReviewMark, ChatRole, ChatMessageContent, ChatMessage, ScenarioId, DatasetRow

## N12 platform → 모든 서비스

- 무엇: 인증된 사용자 신원과 역할(OIDC 접근 토큰), 기기 신원(mTLS), 서비스 인증서(영역 사이 TLS), 기계 토큰
- 작업: HTTP 작업 없음(표준 프로토콜). 작업의 security 로 요구한다
- 대표 스키마: UserIdentityClaims, AccessTokenHeader, MachineIdentityClaims, UserRole, MachineRole, MachineTokenTable, DeviceAllowlist, ForwardedClientCertValue
- 참조의 닫힘 28개: ServiceName, ForwardedClientCertValue, NumericDate, UserId, UserRole, MachineRole, MachineClientName, MachineTokenEntry, MachineTokenTable, RealmAccessClaim, PreferredUsername, TokenAudienceClaim, AccessTokenType, OidcClientId, TokenId, AccessTokenHeader, JwsAlgorithmName, UserIdentityClaims, DeviceId, DeviceSerialNumber, SecretFilePath, OidcIssuerUrl, DeviceAllowEntry, DeviceAllowlist, MachineIdentityClaims, MachineRealmAccessClaim, MachineOidcClientId, MachineSubjectId

## N13 deploy → 모든 영역

- 무엇: 환경 설정, 비밀 파일 경로, 잡 실행, 백업·복구, 이미지 선언, 노출 선언, 배치 설정
- 작업: HTTP 작업 없음(잡 실행과 환경 입력)
- 대표 스키마: SurveyServiceEnv, ModelRuntimeEnv, ModelLabEnv, KioskFrontendEnv, AdminConsoleEnv, PlatformEnv, JobsDeclaration, JobRunInput, JobRunResult, ImageDeclaration, ContainerInputs, Exposure, DeploymentLayout, DeployBackupConfig, HostsTable
- 참조의 닫힘 103개: Timestamp, KioskRequestLimitSeconds, KioskRetryBudgetSeconds, KioskIdleResetSeconds, KioskProgressNoticeSeconds, GatewayConnectLimitSeconds, GatewayPatientRouteLimitSeconds, SurveyTurnLimitSeconds, ExtractClientLimitSeconds, RespondClientLimitSeconds, ModelExtractLimitSeconds, ModelRespondLimitSeconds, AlertStreamHeartbeatSeconds, SessionStatePollSeconds, TimeBudgetTable, ServiceName, ImageUnitName, ImageRevision, OidcJwksUrl, DeviceId, QuestionnaireId, JobName, JobTimeoutSeconds, JobDeclaration, JobsDeclaration, JobRunInput, BackupSnapshotId, JobExitCode, ProcessedCount, JobRunResult, ListenPort, SecretFilePath, ConfigFilePath, PeerBaseUrl, OciRepositoryName, OidcIssuerUrl, EgressProxyUrl, LogLevel, DatabaseUrl, BackupRepositoryUrl, OffsiteBackupUrl, VapidSubject, StartCodeTtlSeconds, ReaskLimit, ExplainStreakLimit, RiskDetectionEnabled, RawUtteranceRetentionDays, ModelProfileName, HostName, Ipv4Address, Ipv6Address, HostAddress, DevicePlacementTable, FhirCanonicalBaseUrl, SurveyServiceEnv, ModelRuntimeEnv, ModelLabEnv, KioskFrontendEnv, AdminConsoleEnv, CaMode, IngressCertificateMode, AcmeDirectoryUrl, AlertReceiverUrl, PlatformEnv, ExposureAudience, HttpMethodName, RoutePathPrefix, ExposureRoute, ExternalEgressTarget, EgressTarget, Exposure, ContainerPath, CapabilityName, SysctlName, SysctlValue, Sysctl, PathPersistent, WritablePath, ArgvElement, ProcessDeclaration, EnvVarName, EnvKind, EnvDeclaration, IsRequired, RunAsUid, ContainerInputs, DatabaseEngine, DatabaseMajorVersion, DatabaseDeclaration, DeployBackupConfig, ContractsVersionLabel, ImageDeclaration, ImageLabelValue, ImageLabelSet, ServerName, ServerEntry, DevicePlacement, DeploymentLayout, InferenceEngineUrl, SmtpSmarthost, AlertHeartbeatInterval, HostsTable, HostsTableEntry

## N14 외부 위험 감지기 → survey-service

- 무엇: 위험 신호(위험 감지가 켜졌을 때만)
- 작업: receiveRiskSignal
- 대표 스키마: RiskSignal, RiskCategory, StaffAlert
- 참조의 닫힘 10개: Timestamp, DeviceId, QuestionnaireTitle, SessionId, AlertId, AlertKind, StaffAlert, RiskCategory, RiskSourceName, RiskSignal

## 모든 작업에 공통

오류 응답(RFC 9457), 건강 상태, 멱등 키, 쪽 나누기처럼 어느 한 흐름에 속하지 않는 스키마 24개: ProblemType, ProblemTitle, HttpStatus, ProblemDetail, ProblemInstance, ProblemReason, JsonPointer, ProblemFieldError, ProblemFieldErrors, ProblemDetails, RetryAfterSeconds, PageLimit, HealthStatus, HealthCheckName, HealthCheck, HealthChecks, HealthReport, IdempotencyKeyValue, AuthenticateChallenge, PrometheusExposition, PrometheusMetricName, PrometheusMetricLabel, RequiredPrometheusMetric, PrometheusMetricType

## 흐름 수와 규모

- 계약 작업 48개, 스키마 355개. 개정 전(영역 12개)은 작업 98개, 스키마 424개였다.
- 옛 흐름 번호(F01~F74)의 행방은 `flows.md` 마지막 표다.
