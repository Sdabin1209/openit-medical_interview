# 문진 키오스크 v7 영역 사이 데이터 흐름

기준일 2026-11-10. 영역 구성은 [ADR 0019](../docs/adr/0019-영역-구성-7개.md)이고 흐름 N01~N14 의 정본은 [docs/design.md](../docs/design.md) 3절이다. 사용자 결정과 충돌 정리는 [docs/v7-flow-resolutions.md](../docs/v7-flow-resolutions.md)다. 이 문서는 각 흐름에 계약의 작업과 스키마 이름을 연결한다. 스키마·작업이 어느 흐름에 쓰이는지는 `traceability.md` 가 흐름마다 적는다.

## 요약

- 영역은 7개(survey-service, model-runtime, platform, model-lab, kiosk-frontend, admin-console, deploy)와 계약의 주인 head 다(`areas.yaml`). 상시 HTTP 서비스는 survey-service, model-runtime 과 화면·platform 의 상태 작업뿐이다. model-lab 은 잡이라 HTTP 서버가 없고 계약의 작업이 없다.
- 영역 사이 흐름은 14개(N01~N14)다. 계약의 작업은 48개(survey-service 29, model-runtime 10, 화면과 platform 은 건강 상태·지표 3개씩), 스키마는 355개다.
- 모델 패키지는 레지스트리의 OCI 아티팩트(N10)이고 게시용 HTTP 작업은 없다. 활성화 승인·롤백은 model-runtime 의 작업이다(N07). 사람의 신원은 OIDC 접근 토큰의 sub 클레임이며 본문이나 별도 헤더의 신원은 쓰지 않는다(design.md 3절 끝, RFC 9068).
- 문항 은행 버전 호환은 별도 흐름이 없다. model-runtime 이 추출·응답 요청마다 받은 `runtime_contract_version` 을 적재한 패키지의 값과 비교해 다르면 409 `QUESTION_BANK_VERSION_MISMATCH` 로 거부한다(N03).
- 턴 기록과 업무 로그의 수집, 실패 탐지는 survey-service 영역 안의 일이라 계약에 값이 없다(ADR 0019).
- 모델 입출력의 합격 조건은 계약의 `ActionExtractionRules` 와 `ActionExtraction`, 요청의 순서표·칸 규격에서만 나오고 위반 코드 하나가 조건 하나다(`ViolationCode`). 검사는 model-runtime 의 출력 검증이 한 번 한다(R7). 의미 위반율은 값 고쳐 쓰기(D115) 전의 모델 출력으로 센다.

## 영역 사이 흐름

| 번호 | 보내는 쪽 → 받는 쪽 | 무엇 | 계약 작업 | 스키마 | 근거 |
|---|---|---|---|---|---|
| N01 | kiosk-frontend → survey-service | 세션 시작(시작 코드, 문진표 선택), 환자 발화 턴(글자와 턴 ID), 세션 종료, 세션 상태 확인, 직원 다시 부르기 | listActiveQuestionnaires, startSession, submitTurn, endSession, getSessionState, requestStaffCall | ActiveQuestionnaireList, SessionStartRequest, StartCodeValue, TurnRequest, UtteranceText, TurnId, SessionId | D55, D66, D85(1), D136, U86, C20, L23 |
| N02 | survey-service → kiosk-frontend | N01 작업의 응답: 세션 시작 결과, 턴 응답(다음 질문, 응답 문장, 실패 신호), 세션 상태, 활성 문진표 목록 | 같은 작업의 응답(startSession, submitTurn, endSession, getSessionState, listActiveQuestionnaires) | SessionStarted, TurnResponse, SessionEnded, SessionState, TurnFailureReason, PauseReason, ResponseSentence | D55, D75(1), D66(6), L28, U86 |
| N03 | survey-service → model-runtime | 추출 요청(지금 문항, 직전에 물은 문항, 직전 화면 문장, 발화, 저장된 칸 값, 순서표, 칸 규격, 문항 은행 버전)과 응답 문장 요청(행동, 사유, 추출 출력의 값·칸·노트, 발화, 저장된 칸 값, 다음 자리). 모델 입력의 글은 요청에 없고 model-runtime 이 만든다 | extractAction, generateResponse | ExtractionRequest, ResponseGenerationRequest, StoredSlots, ResponseNext, QuestionFlowTable, QuestionFieldSpecs, RuntimeContractVersion, ActionExtractionRules | D74, D77, D108, D115, R7, ADR 0019, docs/design.md 3절 |
| N04 | model-runtime → survey-service | N03 작업의 응답: 검증을 마친 추출 결과 또는 출력 불가(503 OUTPUT_INVALID), 응답 문장, 적재 상태 | 같은 작업의 응답과 getModelStatus | ExtractionResult, ActionExtraction, ResponseResult, ModelStatus, ModelLoadState, ViolationCode, ProblemDetails | D75(1), D104(3), D115, R7, ADR 0019 |
| N05 | admin-console → survey-service | 시작 코드 발급, 결과 조회·확인 표시, 문항 세트 올리기·활성화, 실패 사례 검토, 직원 개입, 알림 목록·구독 | issueStartCode, listResults, getResult, getResultFhir, acknowledgeResult, uploadQuestionSet, listQuestionSetVersions, getQuestionSetVersion, activateQuestionSet, listFailureCases, getFailureCase, reviewFailureCase, getDeidentifiedTrace, decideIntervention, listStaffAlerts, streamStaffAlerts, getPushConfig, registerPushSubscription | StartCodeIssueRequest, QuestionSetUpload, QuestionSetVersion, ActiveQuestionSet, CaseReview, InterventionDecision, PushSubscription | U83, U92, D52(1), D71, D58(4), D64, ADR 0019, docs/design.md 3절 |
| N06 | survey-service → admin-console | N05 작업의 응답: 시작 코드, 결과, 알림, 문항 세트 목록, 실패 사례와 비식별 턴 기록 | 같은 작업의 응답 | StartCode, SessionResult, ResultPage, StaffAlert, StaffAlertEvent, QuestionSetVersionPage, FailureCase, FailureCasePage, DeidentifiedTrace, WebPushPayload | U83, U92, D64, D71, D87 |
| N07 | admin-console → model-runtime | 모델 적재 상태 조회, 게시된 모델 패키지 목록, 평가 보고서 확인, 활성화 승인, 롤백(승인자 신원은 OIDC 토큰의 sub) | getModelStatus, listModelPackages, getModelPackage, activateModelPackage, rollbackModelPackage | ModelStatus, ModelPackageList, ModelPackageManifest, ActivationRequest, RollbackCommand, ModelChangeReason, OciDigest | D53, D85(3), D46, admin-console-002, ADR 0019, docs/design.md 3절, RFC 9068 |
| N08 | 병원 시스템 → survey-service | 결과를 당겨 가기(JSON 과 FHIR R4 QuestionnaireResponse) | listResults, getResult, getResultFhir | SessionResult, FhirQuestionnaireResponse, FhirMapping, FhirOperationOutcome | C10, D102, U83 |
| N09 | model-lab → survey-service | 확정된(CONFIRMED) 비식별 실패 사례를 당겨 가기 | listFailureCaseExports | FailureCaseExport, FailureCaseExportPage | D52(2), D15, ADR 0019 |
| N10 | model-lab → 레지스트리 → model-runtime | 모델 패키지(OCI 아티팩트, artifactType 으로 구분, digest 로 고정) | HTTP 작업 없음(OCI Distribution 표준이 전송). model-runtime 이 getModelPackage 와 activateModelPackage 로 digest 를 받는다 | ModelPackageOciManifest, ModelPackageManifest, EvaluationReport, ModelPackageBlobDescriptor, ModelPackageArtifactType, ModelPackageBlobMediaType, OciDigest, OciImageManifestMediaType | OCI Image Spec 1.1, ADR 0019, D75(4), D45 |
| N11 | 외부 데이터셋 담당 → model-lab | 확정된 학습·평가 데이터(입출력 규칙은 labels.py 와 IO_SPEC.md) | HTTP 작업 없음(파일을 잡 입력 폴더 OPENIT_DATASET_DIR 에 둔다) | DatasetManifest, DatasetFileDeclaration, DatasetFileRef, DatasetRow, ChatMessage | G02, C25, D74, D77, D100 |
| N12 | platform → 모든 서비스 | 인증된 사용자 신원과 역할(OIDC 접근 토큰), 기기 신원(mTLS), 서비스 인증서(영역 사이 TLS), 기계 토큰 | HTTP 작업 없음(표준 프로토콜). 작업의 security 로 요구한다 | UserIdentityClaims, MachineIdentityClaims, AccessTokenHeader, UserRole, MachineRole, MachineTokenTable, DeviceAllowlist, ForwardedClientCertValue | U82, D113, D136, D122, RFC 9068, RFC 8705, RFC 6749 4.4, platform-002 |
| N13 | deploy → 모든 영역 | 환경 설정, 비밀 파일 경로, 잡 실행, 백업·복구, 이미지 선언, 노출 선언, 배치 설정 | HTTP 작업 없음(잡 실행과 환경 입력) | SurveyServiceEnv, ModelRuntimeEnv, ModelLabEnv, KioskFrontendEnv, AdminConsoleEnv, PlatformEnv, JobsDeclaration, JobRunInput, JobRunResult, ImageDeclaration, ContainerInputs, Exposure, DeploymentLayout, DeployBackupConfig, HostsTable | D84, D128, D130, D131, D133, D134 |
| N14 | 외부 위험 감지기 → survey-service | 위험 신호(위험 감지가 켜졌을 때만) | receiveRiskSignal | RiskSignal, RiskCategory, StaffAlert | D85(2), D88 U1, L11, UD-18 |

## 영역 안의 일(계약에 값이 없다)

| 일 | 영역 | 이유 |
|---|---|---|
| 턴 기록과 업무 로그 저장, 중복 제거 | survey-service(trace) | 같은 영역 안의 컴포넌트 사이 값이라 영역의 types 가 맡는다(구조 규칙 5, ADR 0019) |
| 실패 탐지 규칙, 비식별 | survey-service(failure_case) | 같은 영역 안 |
| 접근 기록(누가 결과를 읽었는가) | survey-service(result) | 같은 영역 안 |
| 모델 패키지 검증·적재·활성 포인터 | model-runtime(package_loader, release) | 같은 영역 안 |
| 데이터셋 가져오기, 학습, 평가, 게시 단계 사이의 값 | model-lab | 잡 단계 사이 값은 영역 안 |
| 게시 전 평가의 의미 위반율 | model-lab(evaluate) | `libs/model-io` 의 같은 검증기를 쓴다(D97) |

## 옛 흐름 번호 F01~F74 의 행방

옛 계약(영역 12개)의 흐름 번호다. 스키마의 `x-basis` 에 남은 F 번호가 어디로 갔는지 찾는 용도이며 새 흐름은 N 번호다.

| 옛 번호 | 지금 |
|---|---|
| F01 | N05 (uploadQuestionSet: 시스템 밖에서 만든 문항 세트를 올린다) |
| F02 | 없어짐(미리보기는 문항 작성이 시스템 밖이라 없다) |
| F03 | 없어짐(저자 확인 절차가 없다) |
| F04 | 없어짐(임상 근거 승인 절차와 2인 승인이 없다) |
| F05 | 없어짐(후보 수집) |
| F06 | 없어짐(출고 제출) |
| F07 | N10 |
| F08 | N07 (getModelPackage 로 평가 보고서를 본다. 현재 활성 릴리스와 맞댄 검토 보고서는 없다) |
| F09 | N07 (activateModelPackage 가 승인이다. 반려는 활성화하지 않는 것이다) |
| F10 | N07 |
| F11 | 없어짐(survey-service 는 활성 문항 세트를 영역 안에서 가진다: N05 activateQuestionSet) |
| F12 | N10 과 N07 |
| F13 | 없어짐(릴리스 읽기) |
| F14 | 없어짐(롤백 요청 자동 제출은 없고 롤백은 사람이 N07 로 한다) |
| F15 | 없어짐(model-lab 이 문항 정의를 읽는 흐름은 design.md 에 없다) |
| F16 | 없어짐(데이터셋 게시 영역이 없다) |
| F17 | N11 |
| F18 | 영역 안(model-lab 의 import_dataset 이 N11 의 데이터를 가져와 검증한다) |
| F19 | 없어짐(시드 게시) |
| F20 | N09 |
| F21 | 없어짐(개선 신호) |
| F22 | 없어짐(개선 신호) |
| F23 | 계약 밖(사람과 kiosk-frontend 화면 사이) |
| F24 | 계약 밖(사람과 kiosk-frontend 화면 사이) |
| F25 | N05 (issueStartCode: 직원이 대상자 참조값으로 시작 코드를 발급한다) |
| F26 | N13 (DevicePlacementTable 을 survey-service 환경 입력으로 준다) |
| F27 | 계약 밖(조직 PKI 의 기기 인증서 발급) |
| F28 | N12 |
| F29 | N01 |
| F30 | N02 |
| F31 | N02 |
| F32 | N01 |
| F33 | N03 |
| F34 | N04 |
| F35 | N04 와 N07 (getModelStatus) |
| F36 | 영역 안(턴 기록과 업무 로그는 survey-service 의 trace 컴포넌트가 저장한다, ADR 0019) |
| F37 | N14 |
| F38 | N06 |
| F39 | N05 |
| F40 | 계약 밖(직원과 admin-console 화면 사이) |
| F41 | N06 |
| F42 | N05 |
| F43 | 계약 밖(의사와 admin-console 화면 사이) |
| F44 | N08 |
| F45 | N05 |
| F46 | N06 |
| F47 | N07 |
| F48 | 계약 밖(검토자와 화면 사이) |
| F49 | 계약 밖(승인자와 화면 사이) |
| F50 | N12 |
| F51 | N12 |
| F52 | N12 |
| F53 | N12 |
| F54 | N13 |
| F55 | N13 |
| F56 | N13 |
| F57 | N13 |
| F58 | 번호 없음(모든 서비스의 /healthz·/readyz·/metrics 작업을 platform 감시가 읽는다) |
| F59 | 영역 안(platform 의 monitoring 이 외부에 경보를 보낸다) |
| F60 | N13 |
| F61 | N13 |
| F62 | N13 |
| F63 | N13 |
| F64 | N13 |
| F65 | 계약 밖(model-runtime 이 모델 허브에서 기반 모델을 받는다. 계약은 환경 입력 OPENIT_MODEL_CACHE_DIR 만 정한다) |
| F66 | 없어짐(학습 서버는 model-lab 잡이고 별도 영역이 아니다) |
| F67 | 없어짐(학습 서버의 결과 게시가 없다: model-lab 이 N10 으로 직접 게시한다) |
| F68 | 번호 없음(계약 자체: 헤드가 소유한다) |
| F69 | 번호 없음(문진 스키마는 survey-service 가 소유하고 읽기 전용으로 둔다) |
| F70 | 번호 없음(link 는 코드 라이브러리다) |
| F71 | 번호 없음(libs/model-io 라이브러리, design.md 2절) |
| F72 | 번호 없음(계약 변경 절차) |
| F73 | 번호 없음(영역 브리프) |
| F74 | 번호 없음(변경 요청) |
