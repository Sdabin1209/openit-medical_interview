# 영역 브리프

영역 작업자가 처음 읽는 문서다. 영역 구성은 [ADR 0019](../adr/0019-영역-구성-7개.md), 컴포넌트는 [design.md](../design.md), 영역 사이 값은 `contracts/`(태그 `contracts-v8.0.0`, 동결)가 정본이다.

## 모든 영역 공통
- 정본: `contracts/`(영역 사이 값), `docs/design.md`(맡는 일·컴포넌트·영역 사이 어휘 4절), `contracts/inputs/`(결정 기록, 데이터셋 정본 `labels.py`·`IO_SPEC.md`·`SQL.md`), `docs/adr/`. 이 밖의 옛 구현은 읽지 않고 근거로 쓰지 않는다.
- 계약은 동결이다. 부족하거나 틀렸다고 판단하면 고치지 말고 `docs/change-requests/<영역>-<번호>.md` 에 변경 요청을 쓴다.
- 영역 폴더는 `tools/new-area` 로 만들고 ADR 0003 구조를 따른다. 계약 타입은 생성 명령으로만 만든다(손으로 옮기지 않는다). 영역 안 컴포넌트 사이 값은 영역의 `types` 에 한 번만 정의한다.
- 컴포넌트는 `types` 와 생성 타입만 import 한다. 영역 밖 통신은 `link_` 컴포넌트만 한다. 이웃 영역은 계약 타입으로 만든 가짜(메모리 구현)로 대신해 혼자 시험한다.
- 값은 낸 쪽이 한 번만 검증한다(R7). 받은 계약 값을 다시 검사하지 않는다.
- 기술은 ADR 0001(Python 3.12·FastAPI·Pydantic v2·SQLAlchemy 2·asyncpg·Alembic·PostgreSQL 16 / React·Vite·TS). 새 의존은 표준 오픈소스, 배포물은 허용형 라이선스만, 버전 지정 없이 설치.
- 비자명한 선택은 영역 `docs/adr/` 에 ADR, 상수에는 근거 주석.
- 끝 조건(모든 영역): 영역 시험(단위·계약 적합성 Schemathesis)·린트·pyright(또는 tsc)·import-linter rc=0, `openit-check all` rc=0, `deploy/deploy build <영역>` rc=0(Trivy 포함), `tools/smoke` rc=0. 영역 README 5절에 시험 상태.

| 영역 | 브리프 |
|---|---|
| survey-service | [survey-service.md](survey-service.md) |
| model-runtime | [model-runtime.md](model-runtime.md) |
| model-lab | 프로젝트 최하위 순위(E2E 뒤, 사용자 결정 2026-11-10). [model-lab.md](model-lab.md)는 그때 학습 래퍼로 다시 쓴다 |
| platform | [platform.md](platform.md) |
| kiosk-frontend, admin-console | [web.md](web.md) |

## 순서
1. 기반(타입 생성, 공유 라이브러리, 적합성 시험)
2. survey-service, model-runtime, platform(병렬)
3. kiosk-frontend, admin-console
4. 배포 통합과 E2E
5. model-lab(최하위)
