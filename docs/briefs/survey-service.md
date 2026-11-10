# survey-service 브리프

공통 규칙은 [README](README.md). 맡는 일과 컴포넌트는 [design.md 2절 survey-service](../design.md).

## 구현할 계약 작업(`contracts/openapi/survey-service.yaml`, 26개 + healthz·readyz·metrics)
- 키오스크(기기 mTLS): listActiveQuestionnaires, startSession, submitTurn, endSession, getSessionState, requestStaffCall
- 직원·의사·관리자(OIDC): issueStartCode, decideIntervention, listStaffAlerts, streamStaffAlerts, getPushConfig, registerPushSubscription, listResults, getResult, getResultFhir, acknowledgeResult, listFailureCases, getFailureCase, reviewFailureCase, getDeidentifiedTrace, uploadQuestionSet, listQuestionSetVersions, getQuestionSetVersion, activateQuestionSet
- 기계 토큰: listResults·getResult·getResultFhir(병원 시스템, result-reader), receiveRiskSignal(risk-detector), listFailureCaseExports(model-lab, case-reader)
- 신원은 platform 이 넘긴 것만 쓴다: 사람은 OIDC 토큰 클레임, 기기는 `X-Forwarded-Client-Cert`, 기계는 토큰. 본문 신원은 쓰지 않는다.

## 부르는 이웃
- model-runtime: extractAction, generateResponse(N03·N04). 시험에서는 계약 타입으로 만든 가짜 model-runtime(정해진 출력, 출력 불가, 시간 초과를 낼 수 있음)을 쓴다.

## 지켜야 할 결정(정본)
- 시작 코드: 6자리 숫자, 유효 시간 기본 300초(최대 600), 한 번 쓰면 폐기(UD-04, C20).
- 발화 한 턴 300자(사용자 결정).
- 되묻기 한도: 처음 질문 1회 + 되묻기 2회. 한도에 닿으면 그 문항을 건너뛰고 직원 알림은 내지 않는다. 검증된 출력의 action(REASK·CONFIRM)을 세어 session 이 판단한다(docs/v7-flow-resolutions.md).
- 모델 입출력 v3 의존 기능(확인 중 상태, 뜻 묻기 한도 면제, 설명 3회 뒤 직원 도움)은 활성 패키지의 model_io_version 이 v3 이상일 때만(ModelIoFeatureRequirements). 지금은 꺼짐.
- 실패한 턴은 세션 상태를 바꾸지 않는다(D75). 출력 불가는 같은 요청 1회 재시도 후 실패 신호.
- 유휴 60초 뒤 세션 만료(UD-17, SessionStatus EXPIRED).
- 결과는 병원 시스템이 당겨 간다(FHIR R4 QuestionnaireResponse, 빈칸은 data-absent-reason). 보내지 않는다.
- 위험 감지는 기본 꺼짐. 꺼져 있으면 receiveRiskSignal 은 RISK_DETECTION_DISABLED.
- 턴 기록·업무 로그는 영역 안 trace 컴포넌트가 저장(최소 1회, 중복 제거). 실패 탐지·검토·비식별 내보내기는 failure_case. CONFIRMED 만 내보낸다.
- 문항 세트는 올려서 검증·저장·활성화. 추출 요청에 문항 은행 버전(runtime_contract_version)을 실어 보낸다.

## DB
PostgreSQL 16(영역 전용, compose.dev.yaml 로 개발 시 띄움), SQLAlchemy 2 + asyncpg, Alembic 마이그레이션.

## 끝 조건(공통에 더해)
- 문진 한 건 시나리오 시험: 시작 코드 발급 → 시작 → 턴 여러 번(가짜 model-runtime) → 한도 건너뛰기 → 종료 → 결과·FHIR 조회 → 확인 표시. 포그라운드로 rc=0.
