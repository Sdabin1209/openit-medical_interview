# survey-service

## 1. 하는 일
문진 한 건의 시작부터 결과까지와 그 과정의 기록·실패 사례·문항 세트를 맡는 상시 서비스다(Python, FastAPI, PostgreSQL 16). 직원이 일회용 시작 코드(6자리 숫자)를 발급하면 환자가 키오스크에서 그 코드로 세션을 시작하고, 턴마다 이웃 model-runtime 에 값 추출과 응답 문장을 요청해 세션을 진행하고, 끝나면 결과를 병원 시스템이 당겨 갈 수 있게(FHIR R4 QuestionnaireResponse) 한다. 모델 출력의 뜻은 다시 검사하지 않는다(model-runtime 이 보증, R7).

## 2. 받는 계약·내는 계약
- 내는 HTTP 계약: [`contracts/openapi/survey-service.yaml`](../../contracts/openapi/survey-service.yaml)(작업 26개와 `/healthz`·`/readyz`·`/metrics`). 키오스크(기기 mTLS), 직원·의사·관리자(OIDC), 기계 호출자(JWT 접근 토큰: 병원 시스템, 위험 감지기, model-lab, ADR 0014)가 부른다. 서비스는 TLS 를 끝내지 않고 영역 전용 내부 네트워크에서 평문 HTTP 로 듣는다(TLS 는 영역 게이트웨이, ADR 0015).
- 부르는 HTTP 계약: [`contracts/openapi/model-runtime.yaml`](../../contracts/openapi/model-runtime.yaml)의 `extractAction`, `generateResponse`, `getModelStatus`(구조화된 값만 보낸다). 영역 게이트웨이의 CONNECT 터널 위에서 클라이언트 인증서로 mTLS 를 하고 client credentials 로 받은 기계 토큰을 보낸다. 시험에서는 계약 타입으로 만든 가짜 model-runtime 이 대신한다.
- 받는 환경 입력: 계약 `SurveyServiceEnv`(비밀은 `NAME_FILE` 경로, ADR 0005). `OPENIT_TLS_CERTIFICATE_FILE`·`OPENIT_TLS_PRIVATE_KEY_FILE` 은 이웃을 부를 때 보이는 클라이언트 인증서와 개인키다. `OPENIT_MACHINE_TOKENS_FILE` 은 호출자 이름과 역할의 표(`MachineTokenTable`)다.
- 이미지 선언: [`jobs.json`](jobs.json)(JobsDeclaration), [`exposure.json`](exposure.json)(Exposure), [`inputs.json`](inputs.json)(ContainerInputs)가 라벨 `io.openit.jobs`·`exposure`·`inputs` 의 원본이다(ADR 0016).
- 타입은 `src/survey_service/contract/models.py` 로 생성한다(손으로 고치지 않는다). 생성 대상은 `pyproject.toml` 의 `[tool.openit.contract]` 가 정한다.
- 이 영역이 낸 변경 요청: [`docs/change-requests/survey-service-001~007`](../../docs/change-requests/)(계약 9.0.0 이 004~007 을 반영했다. 처리 표시는 헤드가 한다).

## 3. 컴포넌트
컴포넌트는 `types.py` 와 계약 타입만 알고, DB 는 `store/`, 이웃·HTTP 는 `link/` 에서만 쓴다(경계는 import-linter 가 지킨다, ADR 0009).

| 컴포넌트 | 파일 | 입력 | 출력 | 하는 일 |
|---|---|---|---|---|
| link_kiosk_api | `src/survey_service/link/kiosk_api.py` | 키오스크 요청 | 세션·턴 응답 | 시작 코드 확인, 세션 시작·턴·종료·상태, 직원 호출, 활성 문진표 목록 |
| link_admin_api | `src/survey_service/link/admin_api.py` | 직원·관리자·model-lab 요청 | 코드·알림·문항 세트·사례 | 시작 코드 발급, 개입, 알림 목록·스트림, 푸시 구독, 문항 세트, 실패 사례 검토·내보내기 |
| link_hospital_api | `src/survey_service/link/hospital_api.py` | 결과 조회 | 결과, FHIR 결과 | 결과 목록·상세·FHIR, 확인 표시, 접근 기록 |
| link_model_client | `src/survey_service/link/model_client.py`, `machine_token.py`, `tls.py` | 추출·응답 요청 | 검증된 추출 결과, 응답 문장 | model-runtime 호출(게이트웨이 터널, mTLS, 기계 토큰) |
| link_push | `src/survey_service/link/push.py` | 알림, 구독 | 푸시 전송 | Web Push(RFC 8030·8291·8292) |
| link_risk_in | `src/survey_service/link/risk_in.py` | 위험 신호 | 정지된 세션, 알림 | 위험 감지가 켜졌을 때만 받는다 |
| start_code | `src/survey_service/components/start_code.py` | 발급 요청 | 시작 코드, 판정 | 6자리 코드 발급, 한 번 쓰면 폐기 |
| session | `src/survey_service/components/session.py` | 세션 명령, 추출 결과 | 세션 상태 | 다음 문항, 되묻기 한도, 유휴 만료, 정지·재개·종료 |
| turn | `src/survey_service/components/turn.py` | 발화, 세션, 문항 세트 | 추출 요청, 응답 요청, 고정 문장 | 모델 요청 만들기 |
| question_bank | `src/survey_service/components/question_bank.py` | 올린 문항 세트 | 검증 결과, 해시, 다음 문항 | 문항 세트 검증과 순서표 계산 |
| result | `src/survey_service/components/result.py` | 세션 상태 | 결과, FHIR 결과 | 결과 조립과 FHIR 변환 |
| alert | `src/survey_service/components/alert.py` | 세션 사건 | 알림, 푸시 내용 | 위험·직원 호출·결과 도착 알림 |
| trace | `src/survey_service/components/trace.py` | 턴 사건 | 턴 기록 | 턴 기록과 업무 로그(중복 제거) |
| failure_case | `src/survey_service/components/failure_case.py` | 턴 기록, 검토 | 실패 사례, 내보내기 | 규칙 탐지, 검토 버전, 비식별 내보내기(CONFIRMED 만) |
| store | `src/survey_service/store/` | 저장·조회 명령 | 레코드 | PostgreSQL(SQLAlchemy 2, asyncpg), Alembic 마이그레이션 |

잡(`src/survey_service/jobs.py`): DETECT_FAILURES, PURGE_EXPIRED(ADR 0010, 0016). 유휴 만료는 서버가 판정한다(ADR 0017).

## 4. 실행·시험 명령
```
uv sync
uv run pytest                    # 단위·행동·시나리오·계약 적합성(임시 SQLite, 이웃은 가짜)
uv run pytest -m postgres        # 같은 시험을 PostgreSQL 16 컨테이너에서(docker 필요)
uv run lint-imports              # 경계 점검
uv run pyright                   # 타입 검사(strict)
uv run ruff check                # 린트
mkdir -p .dev && openssl rand -hex 16 > .dev/pg_password && docker compose -f compose.dev.yaml up -d --wait   # 개발용 DB
OPENIT_DATABASE_URL=postgresql://survey@127.0.0.1:<배정된 포트>/survey OPENIT_DATABASE_PASSWORD_FILE=$PWD/.dev/pg_password uv run alembic upgrade head
uv run python -m survey_service.jobs PURGE_EXPIRED --requested-at 2026-11-10T09:00:00+00:00   # 잡(환경 입력 필요)
uv run --project tools/checks openit-gen-contract services/survey-service   # 계약 타입 다시 만들기(리포 루트에서, ADR 0020)
uv run --project tools/checks openit-notices generate services/survey-service   # 의존을 바꾼 뒤(리포 루트에서, ADR 0018)
deploy/deploy build survey-service   # 이미지 빌드(Trivy 포함)
tools/smoke service survey-service   # 이미지 스모크(/healthz, /readyz, 기기 요청)
```
pytest 는 임시 폴더를 `TMPDIR`(작업 트리 안 git 제외 폴더 `.pytest-tmp`)로 준다: `TMPDIR=$PWD/.pytest-tmp uv run pytest`.

## 5. 시험 상태
(2026-11-11, 영역 작업자가 이 작업에서 실행한 결과. 작업 트리 `openit-v7-integration`, 계약 9.0.0)

| 명령 | 결과 |
|---|---|
| `uv run pytest`(SQLite) | 통과 — 128개 통과, 1개 건너뜀(경로 의존이 없는 영역의 `test_libs`) |
| `uv run pytest -m postgres`(PostgreSQL 16 컨테이너) | 통과 — 63개 |
| `uv run lint-imports` | 통과 — 계약 5개 |
| `uv run pyright`(strict) | 오류 0 |
| `uv run ruff check`, `ruff format --check` | 통과 |
| `openit-check`(licenses, docker-isolation, image-pins, bake-targets, area-isolation, dockerfile-lint, trivyignore, notices, declarations) | 통과(위반 0) |
| `openit-check contract-drift` | 이 영역의 파이썬 생성물은 위반 0. 점검은 `web/_example` 이 `npm ci` 를 요구해 이 환경에서 실패한다(다른 영역 폴더) |

이 작업에서 하지 않은 것: 이미지 빌드와 `tools/smoke service survey-service`(헤드가 이미지 빌드를 맡는다. 스모크 시험은 새 환경 입력과 라벨 선언으로 고쳤으나 실행하지 않았다).

확인하지 못한 것: 실제 Keycloak·model-runtime·영역 게이트웨이·인증서 에이전트·브라우저 푸시 서비스와의 연동(시험은 서명한 시험 토큰, 가짜 발급자, 가짜 model-runtime, 로컬 TLS 서버, RFC 8291 시험 벡터), platform 의 실제 라우트 생성과 `exposure.json` 의 일치(영역 시험은 같은 규칙의 요약 구현), 운영 부하와 응답 시간(측정하지 않았다), 한도 값(시작 코드 실패 10회·5분, 알림 폴링 1초, 토큰 갱신 여유 30초 등)의 적정성.

## 6. ADR 목록
- [0001 템플릿에서 시작](docs/adr/0001-템플릿에서-시작.md)
- [0002 시작 코드 실패 시도 한도와 충돌 처리](docs/adr/0002-시작-코드-실패-시도-한도와-충돌-처리.md)
- [0003 모델 입력의 글 조각은 문항 세트에서만 만든다](docs/adr/0003-모델-입력의-글-조각은-문항-세트에서만-만든다.md)(0013 이 대체)
- [0004 알림 스트림은 DB 폴링 SSE](docs/adr/0004-알림-스트림은-DB-폴링-SSE.md)
- [0005 웹 푸시는 직접 조립한다](docs/adr/0005-웹-푸시는-직접-조립한다.md)
- [0006 접근 토큰 검증과 JWKS 캐시](docs/adr/0006-접근-토큰-검증과-JWKS-캐시.md)
- [0007 DB 스키마와 마이그레이션, 쪽 나누기](docs/adr/0007-DB-스키마와-마이그레이션-쪽-나누기.md)
- [0008 턴 처리의 멱등과 마감과 재시도](docs/adr/0008-턴-처리의-멱등과-마감과-재시도.md)
- [0009 import-linter 층 규칙의 조정](docs/adr/0009-import-linter-층-규칙의-조정.md)
- [0010 잡 명령과 선언](docs/adr/0010-잡-명령과-선언.md)
- [0011 시험 방식](docs/adr/0011-시험-방식.md)
- [0012 범위와 켜지지 않는 기능](docs/adr/0012-범위와-켜지지-않는-기능.md)
- [0013 모델 입력의 글은 model-runtime 이 만들고 서비스는 구조화된 값만 보낸다](docs/adr/0013-모델-입력-글은-model-runtime-이-만든다.md)
- [0014 기계 호출자는 JWT 접근 토큰과 호출자 표로 인증한다](docs/adr/0014-기계-호출자는-JWT-접근-토큰과-호출자-표.md)
- [0015 TLS 는 영역 게이트웨이가 끝내고 서비스는 평문 HTTP 로 듣는다](docs/adr/0015-TLS는-게이트웨이가-끝내고-서비스는-평문-HTTP.md)
- [0016 이미지 선언(잡·노출·입력)의 원본 파일과 노출·나가는 호출 선언](docs/adr/0016-이미지-선언과-노출-나가는-호출.md)
- [0017 유휴 만료는 서버가 판정한다, 문진표 선택은 422, 실패한 턴은 기록하지 않는다, 활성 표시](docs/adr/0017-유휴-만료는-서버가-판정하고-문진표-선택은-422.md)
