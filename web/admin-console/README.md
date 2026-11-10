# admin-console

## 1. 하는 일
직원·의사·문항 세트 작성자·실패 사례 검토자·모델 활성화 승인자·운영자가 쓰는 업무 화면(정적 React 앱, nginx-unprivileged). 서버 일은 하지 않는다. 직원은 시작 코드를 발급하고(6자리 숫자 표시, QR 없음) 알림(SSE, 웹 푸시)을 받아 확인·정지 해제를 한다. 의사는 결과 목록·상세를 보고 인쇄하고 확인 표시를 한다. 작성자는 문항 세트를 올리고 활성화한다. 검토자는 실패 사례를 검토한다. 승인자는 모델 패키지의 평가 보고서를 보고 활성화를 승인하며, 운영자와 승인자는 롤백한다. 로그인은 앞단 oauth2-proxy 가 하고 화면은 토큰을 다루지 않는다([ADR 0002](docs/adr/0002-같은-출처와-oauth2-proxy-로그인-역할-읽기.md)).

## 2. 받는 계약·내는 계약
- 부르는 계약: [survey-service](../../contracts/openapi/survey-service.yaml)(N05, N06), [model-runtime](../../contracts/openapi/model-runtime.yaml)(N07). 타입은 `npm run generate:contract` 로만 만든다(`src/contract/`, 손으로 고치지 않는다). 위 두 문서에 더해 공유 값 문서 [components.yaml](../../contracts/components.yaml)도 생성 입력이라 작업이 참조하지 않는 `UserRole`·`StaffAlertEvent` 등도 생성 타입에서 얻는다([ADR 0007](docs/adr/0007-계약-타입-생성에-공유-값-문서를-포함한다.md)). 생성물이 계약과 같은지는 `npm run check:contract` 와 `openit-check contract-drift` 가 본다.
- 내는 계약: [admin-console](../../contracts/openapi/admin-console.yaml)(`/healthz`, `/readyz`, `/metrics`). `/healthz`, `/readyz` 는 nginx 설정이 답한다. 화면은 `/console/` 아래에서 서비스하고 감시 경로는 접두어 밖 루트다. 화면이 부르는 `/v1/…`, `/oauth2/…` 는 접두어 밖 절대 경로다([ADR 0010](docs/adr/0010-화면은-console-접두어-아래에서-서비스한다.md)).
- 선언: `exposure.json`(`Exposure`: 화면 경로 `/console/`, `HUMAN_OIDC`, 나가는 호출 없음)과 `inputs.json`(`ContainerInputs`)이 이미지 라벨 `io.openit.exposure`·`io.openit.inputs` 의 원본이다. Dockerfile 은 `ARG EXPOSURE`·`ARG INPUTS` 로 라벨을 단다([ADR 0009](docs/adr/0009-노출-선언과-이미지-라벨-원본-파일.md)).
- [변경 요청 001~005](../../docs/change-requests/)의 처리(계약 9.0.0): 001 역할은 oauth2-proxy `groups` 로 확정([ADR 0002](docs/adr/0002-같은-출처와-oauth2-proxy-로그인-역할-읽기.md)), 002 패키지 목록과 004 활성 표시([ADR 0008](docs/adr/0008-모델-패키지는-목록에서-고르고-활성-여부를-보인다.md)), 003 생성 타입에 공유 값 문서 포함(ADR 0007), 005 같은 출처 상대 경로 확정과 노출 선언(ADR 0009).

## 3. 컴포넌트
| 컴포넌트 | 폴더 | 입력(props) | 하는 일 |
|---|---|---|---|
| Layout | `src/components/Layout` | 사용자 이름, 메뉴, 열린 알림 수 | 머리글·역할별 메뉴·본문 |
| StartCodeView | `src/components/StartCodeView` | 문진표 목록, 발급한 코드, 진행·오류 | 시작 코드 발급, 6자리 표시, 출력 |
| AlertView | `src/components/AlertView` | 알림, 연결 상태, 푸시 상태 | 알림 목록, 확인, 정지 해제(대화상자) |
| ResultList / ResultDetail | `src/components/ResultList`, `ResultDetail` | 결과 요약·상세 | 결과 목록(TanStack Table), 상세, 인쇄, 확인 표시 |
| QuestionSetView | `src/components/QuestionSetView` | 버전 목록(활성 여부 포함) | JSON 파일 올리기, 활성화(이미 활성인 버전은 막음) |
| FailureReviewView | `src/components/FailureReviewView` | 사례, 비식별 기록 | 사례 목록, 검토 결과 게시 |
| ReleaseView | `src/components/ReleaseView` | 적재 상태, 게시된 패키지 목록(쪽 나누기, 활성 여부), 고른 패키지의 목록표 | 패키지 고르기, 평가 보고서, 활성화 승인, 롤백 |

link: `src/link/http.ts`(openapi-fetch, [ADR 0003](docs/adr/0003-계약-호출은-openapi-fetch.md)), `survey.ts`(link_survey), `model.ts`(link_model), `alerts.ts`(SSE·웹 푸시, [ADR 0004](docs/adr/0004-알림-스트림-웹-푸시-갱신-주기.md)), `session.ts`(로그인·역할). 서비스 워커는 `public/sw.js`. 조립은 `src/App.tsx`, `src/Pages.tsx`([ADR 0006](docs/adr/0006-화면-구성과-입력-방식.md)).

| 역할 | 보이는 화면(계약 각 작업의 `security` 요구) |
|---|---|
| staff | 시작 코드, 알림(개입 포함) |
| clinician | 알림(결과 도착), 결과 |
| author | 문항 세트 |
| reviewer | 실패 사례 |
| release-approver | 모델 패키지(승인, 롤백) |
| operator | 모델 패키지(롤백) |
| admin | 없음(계정 관리는 Keycloak) |

## 4. 실행·시험 명령
```
npm ci
npm run dev                 # 개발 서버(서버 API 는 없다. 시험의 가짜로 보려면 tests/e2e 참고)
npm run build               # 타입 검사 후 정적 파일 빌드
npm run generate:contract   # 계약에서 타입 다시 만들기
npm run check:contract      # 생성물이 계약과 같은지
npm run lint                # eslint(경계 점검 포함)
npm run typecheck           # 타입 검사(tsc --noEmit)
npm test                    # Vitest(단위·계약·경계)
tools/web-e2e admin-console # Playwright(공식 이미지 안, 리포 루트에서)
deploy/deploy build admin-console
tools/smoke web admin-console
```

## 5. 시험 상태
2026-11-11, 이 환경(WSL2, Docker Desktop, 호스트에 Playwright 브라우저 라이브러리 없음)에서 돌린 종료 코드다. 한 환경에서만 확인했다. 계약 9.0.0 에 맞춘 뒤 다시 돌렸다.

| 명령 | rc |
|---|---|
| `npm test`(6 파일 84 시험: 단위, 계약 생성 대조, 선언 파일 대조, 경계) | 0 |
| `npm run typecheck` | 0 |
| `npm run lint` | 0 |
| `npm run check:contract` | 0 |
| `npm run build` | 0 |
| `tools/web-e2e admin-console`(6 시나리오) | 0 |
| `openit-check declarations`·`licenses`·`notices`·`area-isolation`·`dockerfile-lint`·`image-pins` | 0 |

`openit-check contract-drift` 는 이 영역이 아니라 `web/_example`(node_modules 없음)에서 위반 1 이 나 rc=1 이었다. 이 영역의 위반은 없었다.

이 작업에서 이미지 빌드, `tools/smoke`, `openit-check all` 은 돌리지 않았다(이미지 빌드는 deploy 의 일).

확인하지 못한 것:
- oauth2-proxy 의 `groups` 에 Keycloak 역할이 나오는 구성(platform), 입구가 `/` 와 `/v1/` 를 나누는 라우팅, 입구가 알림 스트림의 시간 제한을 끄는지.
- 실제 model-runtime 의 `listModelPackages`·survey-service 의 `is_active` 와의 만남(가짜 서버로만 시험).
- 실제 푸시 서비스로의 구독과 전달(헤드리스 브라우저에 없음). 서비스 워커 `public/sw.js` 는 린트만 했다.
- 가짜 응답은 타입으로만 계약과 맞췄고 JSON Schema 검증은 하지 않았다([ADR 0005](docs/adr/0005-시험-가짜-백엔드-하나를-공유.md)).
- 실제 사용자의 사용성(JSON 편집 등).

## 6. ADR 목록
- [0001 템플릿에서 시작](docs/adr/0001-템플릿에서-시작.md)
- [0002 같은 출처와 oauth2-proxy 로그인, 역할 읽기](docs/adr/0002-같은-출처와-oauth2-proxy-로그인-역할-읽기.md)
- [0003 계약 호출은 openapi-fetch](docs/adr/0003-계약-호출은-openapi-fetch.md)
- [0004 알림 스트림, 웹 푸시, 갱신 주기](docs/adr/0004-알림-스트림-웹-푸시-갱신-주기.md)
- [0005 시험: 가짜 백엔드 하나를 공유](docs/adr/0005-시험-가짜-백엔드-하나를-공유.md)
- [0006 화면 구성과 입력 방식](docs/adr/0006-화면-구성과-입력-방식.md)
- [0007 계약 타입 생성에 공유 값 문서 포함](docs/adr/0007-계약-타입-생성에-공유-값-문서를-포함한다.md)
- [0008 모델 패키지는 목록에서 고르고 활성 여부를 보인다](docs/adr/0008-모델-패키지는-목록에서-고르고-활성-여부를-보인다.md)
- [0009 노출 선언과 이미지 라벨 원본 파일](docs/adr/0009-노출-선언과-이미지-라벨-원본-파일.md)
- [0010 화면은 /console/ 접두어 아래에서 서비스한다](docs/adr/0010-화면은-console-접두어-아래에서-서비스한다.md)
