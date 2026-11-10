# 시스템 설계: 영역과 컴포넌트

영역 구성의 결정과 근거는 [ADR 0019](adr/0019-영역-구성-7개.md), 폴더 구조는 [ADR 0003](adr/0003-영역-폴더의-표준-구조.md)이다. 이 문서는 영역마다 맡는 일, 컴포넌트와 그 역할, 컴포넌트 사이 값, 영역 사이 흐름을 정한다. 영역 사이 값의 정의는 `contracts/`(헤드), 영역 안 컴포넌트 사이 값의 정의는 그 영역의 `types` 가 맡는다(구조 규칙 4·5·6). 컴포넌트 이름 앞의 `link_` 는 영역 밖과 통신하는 컴포넌트다(영역 밖 통신은 이것만 한다).

## 1. 한눈에

```
환자 ─ kiosk-frontend ─┐                         ┌─ model-runtime ─ 레지스트리(모델 패키지)
                        ├─ platform(입구·인증) ─ survey-service ┘          ▲
직원·의사·관리자 ─ admin-console ┘                  │  ▲                    │ 게시
                                                    │  └ 실패 사례 내보내기 ─ model-lab(잡, 학습 서버)
                                    병원 시스템 ◀ 결과(FHIR, 당겨 가기)      ▲ 데이터셋(외부 담당)
```

## 2. 영역별 설계

### survey-service (상시 서비스, Python·FastAPI)
문진 한 건의 시작부터 결과까지와, 그 과정의 기록·실패 사례·문항 세트를 맡는다. 모델 출력의 뜻은 다시 검사하지 않는다(model-runtime 이 보증, R7).

| 컴포넌트 | 역할 | 입력 → 출력(이름만. 정의는 영역의 types) |
|---|---|---|
| link_kiosk_api | 키오스크 요청을 받는 HTTP 서버(시작 코드 확인, 세션 시작, 턴, 종료, 직원 호출, 알림 구독) | 계약 요청 → 세션 명령 |
| link_admin_api | 직원·관리자 요청을 받는 HTTP 서버(시작 코드 발급, 결과, 확인 표시, 문항 세트 올리기·활성화, 실패 사례 검토) | 계약 요청 → 결과 조회·문항 세트·검토 명령 |
| link_hospital_api | 병원 시스템이 결과를 당겨 가는 HTTP 서버(FHIR QuestionnaireResponse) | 결과 조회 → FHIR 결과 |
| link_model_client | model-runtime 에 추출·응답 문장을 요청 | 추출 요청 → 검증된 추출 결과, 응답 문장 |
| link_push | 직원 알림을 웹 푸시로 보냄(RFC 8030) | 알림 → 푸시 전송 |
| link_risk_in | 외부 위험 감지기의 신호를 받음(위험 감지가 켜졌을 때만) | 위험 신호 → 위험 정지 명령 |
| start_code | 일회용 시작 코드 발급(6자리 숫자, 대상자 참조값과 묶음, 유효 시간), 한 번 쓰면 폐기 | 발급 요청 → 시작 코드 |
| session | 세션 상태와 진행: 다음 문항, 되묻기 한도, 시간 한도, 위험 정지, 종료 | 세션 명령·검증된 추출 결과 → 세션 상태, 다음 질문 |
| turn | 턴 하나의 처리: 추출 요청 만들기(발화, 순서표, 칸 규격, 세션 상태), 결과를 세션에 반영, 응답 문장 요청 | 발화·세션 상태 → 턴 응답 |
| question_bank | 문항 세트 검증·저장·버전·활성 목록, 순서표와 칸 규격 제공 | 올린 문항 세트 → 활성 문항 세트, 순서표, 칸 규격 |
| result | 세션 결과 조립과 FHIR 변환, 확인 표시 | 세션 상태 → 결과, FHIR 결과 |
| alert | 직원 알림 만들기(위험, 직원 호출, 결과 도착). 되묻기 한도에 닿으면 건너뛰고 알림은 내지 않는다(v7-flow-resolutions) | 세션 사건 → 알림 |
| trace | 턴 기록과 업무 로그 저장(최소 1회 수신, 중복 제거) | 턴 기록 → 저장된 기록 |
| failure_case | 실패 탐지(규칙), 검토 상태, 비식별 내보내기 | 저장된 기록·검토 결과 → 실패 사례, 비식별 내보내기 |
| store | DB 접근(PostgreSQL, SQLAlchemy) | 저장·조회 명령 → 레코드 |

### model-runtime (상시 서비스, Python·FastAPI, GPU)
모델 패키지를 적재해 추출(LoRA-A)과 응답 문장(LoRA-B)을 내고, 출력이 계약 규칙을 지키는지 보증한다. 데이터셋 입출력 규칙(`labels.py`)이 닿는 유일한 곳이다.

| 컴포넌트 | 역할 | 입력 → 출력(이름만. 정의는 영역의 types) |
|---|---|---|
| link_api | 추출·응답 문장·적재 상태·활성화·롤백 요청을 받는 HTTP 서버 | 계약 요청 → 명령 |
| link_registry | 레지스트리에서 모델 패키지를 digest 로 받음(OCI) | 패키지 digest → 패키지 파일 |
| package_loader | 패키지 검증(매니페스트, 어댑터 해시, 입출력 버전)과 적재 | 패키지 파일 → 적재된 모델 |
| release | 활성 패키지 포인터, 활성화·롤백과 그 기록(승인자, 시각, 사유) | 승인된 활성화·롤백 → 활성 패키지 |
| prompt | 모델 입력 글자 만들기(데이터셋 입출력 규칙, 직렬화) | 추출·응답 요청 → 모델 입력 |
| inference | 추론 엔진 호출 | 모델 입력 → 모델 출력 글자 |
| output_guard | 출력 검증(형식, 저장 규칙, targets, next_item, 문항·칸, 칸 규격, 현재 문항)과 값 고쳐 쓰기(D115). 결과는 검증된 출력 또는 출력 불가 | 모델 출력 → 검증된 추출 결과 |
| responder | 응답 문장 출력의 검증 | 모델 출력 → 응답 문장 |

prompt 와 output_guard 의 규칙은 `libs/model-io`(라이브러리)에 두고 model-lab 의 평가가 같은 것을 쓴다(운영과 같은 검증기, D97).

### platform (상시 서비스, 기성품 구성)
| 컴포넌트 | 역할 |
|---|---|
| gateway | 입구(Envoy). TLS 종단, 키오스크 기기 인증서 검증(mTLS), 경로 라우팅 |
| identity | 사람 인증(Keycloak, OIDC), 역할 부여 |
| identity_proxy | 화면 로그인 앞단(oauth2-proxy) |
| ca | 사설 CA(step-ca, ACME) |
| monitoring | 감시(Prometheus, blackbox_exporter), 인증서 만료 경보 |
| registry | 이미지·모델 패키지 레지스트리(Distribution + Caddy TLS) |

### model-lab (학습 파이프라인, 잡, 학습 서버에서 실행)
| 컴포넌트(잡 단계) | 역할 | 입력 → 출력(이름만. 정의는 영역의 types) |
|---|---|---|
| import_dataset | 데이터셋 담당이 확정한 학습·평가 데이터를 가져와 입출력 규칙으로 검증 | 외부 데이터셋 → 검증된 데이터셋 |
| link_failure_cases | survey-service 에서 확정된 비식별 실패 사례를 받음 | 요청 → 실패 사례 |
| prepare | 학습 형식 변환, 실패 사례를 회귀 평가 집합으로 | 데이터셋·실패 사례 → 학습 입력, 평가 집합 |
| train | 학습 실행(LoRA-A, LoRA-B) | 학습 입력·설정 → 어댑터, 실행 기록 |
| evaluate | 평가 보고서(의미 위반율 등, `libs/model-io` 사용) | 어댑터·평가 집합 → 평가 보고서 |
| publish | 모델 패키지(어댑터, 매니페스트, 평가 보고서)를 레지스트리에 게시 | 어댑터·보고서 → 패키지 digest |

### kiosk-frontend (화면, React)
| 컴포넌트 | 역할 |
|---|---|
| link_survey | survey-service 호출(시작, 턴, 종료, 직원 호출) |
| speech | 기기 안 음성 인식·합성(외부로 보내지 않음) |
| start_view | 시작 코드 입력(숫자 키패드), 문진표 선택 |
| conversation_view | 질문·응답 문장 표시, 발화 입력 |
| idle_reset | 유휴 초기화(60초) |

### admin-console (화면, React)
| 컴포넌트 | 역할 |
|---|---|
| link_survey | survey-service 호출(결과, 확인 표시, 문항 세트, 실패 사례) |
| link_model | model-runtime 호출(적재 상태, 활성화·롤백) |
| start_code_view | 대상자 참조값으로 시작 코드 발급, 6자리 숫자를 화면에 표시(직원이 말로 불러 주거나 적어 주거나 출력한다) |
| result_view | 결과 목록·상세·인쇄·확인 표시 |
| alert_view | 직원 알림 확인과 개입(위험 정지 해제) |
| question_set_view | 문항 세트 올리기·활성화 |
| failure_review_view | 실패 사례 검토 |
| release_view | 모델 패키지 평가 보고서 확인, 활성화 승인, 롤백 |

### deploy (도구)
`./deploy` 명령(doctor, secrets, build, up, down, status, job, backup, restore, bootstrap, ca, pull)과 배치 설정. ADR 0004·0013.

## 3. 영역 사이 흐름(계약 대상)

| 번호 | 보내는 쪽 → 받는 쪽 | 무엇 |
|---|---|---|
| N01 | kiosk-frontend → survey-service | 세션 시작(시작 코드, 문진표), 턴(발화 글자), 종료, 직원 호출 |
| N02 | survey-service → kiosk-frontend | 턴 응답(다음 질문, 응답 문장, 실패 신호), 세션 상태, 활성 문진표 목록 |
| N03 | survey-service → model-runtime | 추출 요청(발화, 순서표, 칸 규격, 세션 상태, 문항 은행 버전), 응답 문장 요청 |
| N04 | model-runtime → survey-service | 검증된 추출 결과 또는 출력 불가, 응답 문장, 적재 상태 |
| N05 | admin-console → survey-service | 시작 코드 발급, 직원 알림 구독, 결과 조회, 확인 표시, 문항 세트 올리기·활성화, 실패 사례 검토, 직원 개입 |
| N06 | survey-service → admin-console | 결과, 알림, 문항 세트 목록, 실패 사례 |
| N07 | admin-console → model-runtime | 적재 상태 조회, 모델 패키지(매니페스트·평가 보고서) 조회, 활성화 승인, 롤백 |
| N08 | 병원 시스템 → survey-service | 결과 당겨 가기(FHIR) |
| N09 | model-lab → survey-service | 확정된 비식별 실패 사례 받아 가기 |
| N10 | model-lab → 레지스트리 → model-runtime | 모델 패키지(OCI 아티팩트, digest) |
| N11 | 외부 데이터셋 담당 → model-lab | 확정된 학습·평가 데이터(입출력 규칙은 `labels.py`) |
| N12 | platform → 모든 서비스 | 인증된 사용자 신원과 역할(OIDC 토큰), 기기 신원(mTLS), 서비스 인증서 |
| N13 | deploy → 모든 영역 | 환경 설정, 비밀 파일, 잡 실행, 백업·복구 |
| N14 | 외부 위험 감지기 → survey-service | 위험 신호(위험 감지가 켜졌을 때만) |

- model-runtime 은 추출 요청마다 받은 문항 은행 버전을 적재한 패키지의 문항 은행 버전과 맞춰 보고, 다르면 거부한다. 따라서 문항 세트와 모델의 호환 확인에 따로 흐름이 필요 없다.
- 사람의 신원은 platform 이 준 OIDC 토큰의 클레임으로 정한다. 본문이나 별도 헤더의 신원은 쓰지 않는다.

## 4. 영역 사이 어휘(헤드 결정 2026-11-10)

계약의 열거 값 중 표준이나 데이터셋 정본에 목록이 없는 것은 이 절이 정본이다. 계약의 `x-basis` 는 "docs/design.md 4절"을 가리킨다.

| 이름 | 값과 뜻 | 왜 |
|---|---|---|
| SessionStatus | ACTIVE(진행 중), PAUSED(위험 신호나 직원 호출로 멈춤), ENDED_COMPLETE(모든 문항을 마침), ENDED_PARTIAL(환자가 중간에 끝냄), EXPIRED(유휴 초기화 60초, UD-17) | 세션이 가질 수 있는 상태를 session 컴포넌트의 진행 규칙에서 나열했다. 결과는 끝난 두 상태와 만료에서 만든다 |
| PauseReason | RISK_SIGNAL, STAFF_CALL | 세션을 멈추는 사건은 위험 신호(N14)와 직원 호출(N01) 둘뿐이다 |
| TurnFailureReason | EXTRACTION_UNAVAILABLE(추출 출력 불가), RESPONSE_UNAVAILABLE(응답 문장 불가), DEADLINE_EXCEEDED(시간 상한 초과) | 턴이 실패하는 원인은 model-runtime 의 두 출력과 시간 상한뿐이다. 실패한 턴은 세션 상태를 바꾸지 않는다(D75) |
| AlertKind | RISK, CALL_STAFF, RESULT_READY | alert 컴포넌트가 내는 알림 세 가지(2절) |
| InterventionAction | ACKNOWLEDGE(알림 확인), RESUME(멈춘 세션 재개) | 직원 개입은 확인과 재개 둘이다(위험 정지 해제는 RESUME) |
| ReviewStatus | UNREVIEWED, CONFIRMED(실패로 확정, 내보내기 대상), DISMISSED(실패 아님) | failure_case 의 검토 상태. CONFIRMED 만 model-lab 이 받아 간다(N09) |
| ModelLoadState | NOT_LOADED, LOADING, READY, FAILED | package_loader 의 적재 상태 |
| MachineRole | result-reader(병원 시스템 결과 당겨 가기 N08), risk-detector(위험 신호 N14), inference-caller(survey-service 의 추출 요청 N03), case-reader(model-lab 의 실패 사례 받아 가기 N09) | 사람이 아닌 호출자마다 역할 하나(최소 권한) |
| ExposureAudience | HUMAN_OIDC, DEVICE_MTLS, MACHINE_TOKEN, EXTERNAL_MACHINE_TOKEN, DENIED | 입구가 받는 신원 종류(N12)와 노출하지 않음 |
| JobName | IMPORT_DATASET, PREPARE, TRAIN, EVALUATE, PUBLISH(model-lab 단계), DETECT_FAILURES, PURGE_EXPIRED(survey-service), BACKUP, RESTORE, OFFSITE_SYNC, RESTORE_TEST(deploy) | 2절 컴포넌트 중 잡으로 도는 것과 배포 도구의 백업·복구 잡 |
| DatasetOrigin | IMPORTED(데이터셋 담당이 확정한 데이터), SYNTHETIC(학습 파이프라인이 만든 데이터) | model-lab 은 데이터셋 담당의 작업(합성 포함)을 따라 한다(ADR 0019) |
| NextItemRuleKind | TARGET_ITEM(targets 칸의 문항), ASKED_ITEM(입력 question_id), SEQUENCE_AFTER_SAVED(저장한 칸 중 순서표에서 가장 뒤 문항의 다음, 건너뛰기 적용) | 행동별 next_item 규칙의 종류. 행동과의 짝은 데이터셋 정본(labels.py, IO_SPEC.md)을 따른다 |
| ModelIoFeature | CONFIRMING_STATE, MEANING_ASKED_EXEMPTION, STAFF_HELP_AFTER_EXPLAIN | 모델 입출력 v3 에 의존하는 세 기능(v7-flow-resolutions 51행) |
| 현재 문항의 계열 | 문항 식별자에서 첫 `_` 또는 `.` 앞 부분이 같은 문항들(Q7_1·Q7_2 → Q7, Q1.D01 → Q1) | 한 질문이 하위 문항으로 나뉜 데이터셋 문항 식별자 구조(labels.py, SQL.md) |
| RiskCategory | SELF_HARM, CHEST_PAIN, DYSPNEA, ALTERED_CONSCIOUSNESS, SEVERE_BLEEDING, PARALYSIS | D88 U2 의 임상 검토 전 임시 기본 목록. 위험 감지는 기본 꺼짐(L11)이고 켤 때 임상 검토로 확정한다(UD-18) |
| 환경 입력(*Env) | 각 영역 컴포넌트가 필요로 하는 설정만 둔다. 비밀은 `_FILE` 경로(ADR 0005) | 설정의 주인은 영역이고 이름 목록은 2절 컴포넌트에서 나온다 |
| 이미지 라벨 | `org.opencontainers.image.revision`(OCI 표준 주석), `io.openit.contracts`(모노레포의 계약 버전 하나), `io.openit.service`, `io.openit.exposure`, `io.openit.inputs`, `io.openit.jobs`, `io.openit.database` | 모노레포라 계약 버전이 하나이고(ADR 0002), 커밋은 OCI 표준 주석을 쓴다. D50 의 계약별 라벨을 대체한다 |
| 선택한 제품·도구의 규격 | Keycloak 접근 토큰의 `realm_access.roles`, restic 스냅샷 ID(SHA-256 16진수, 짧은 형태 8자 이상) | ADR 로 고른 제품·도구(Keycloak: ADR 0008, restic: D130)의 공식 규격을 그 값의 근거로 쓴다. 제품을 바꾸면 이 값도 바뀐다 |
| 잡 실행 결과(JobRunResult) | 잡은 끝날 때 표준 출력에 JSON 한 줄(JSON Lines)을 낸다. 종료 코드는 0·75·1(D130) | 한 줄 JSON 은 로그 수집 도구가 그대로 읽는 표준 형식(JSON Lines)이고, 종료 코드만으로 모자란 처리 수·시각을 담는다 |
| 직원 도움 안내(StaffHelpNotice) | 안전과 닿는 안내 문장은 모델이 아니라 survey-service 의 고정 문장이다. 모델 입출력 v3 부터 쓴다 | v7-flow-resolutions 41·51행(설명 요청 3번 뒤 직원 도움 안내, v3 의존) |
| FHIR 대응(FhirMapping) | 결과를 HL7 FHIR R4 QuestionnaireResponse 로 옮긴다(빈칸은 data-absent-reason) | FHIR R4 표준이 그대로 근거다(C10) |
