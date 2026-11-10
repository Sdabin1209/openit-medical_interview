# __AREA__

## 1. 하는 일
(라이브러리가 하는 일을 한 문단으로 쓴다.)

## 2. 쓰는 계약
(`contracts/` 의 어느 스키마를 쓰는지는 `pyproject.toml` 의 `[tool.openit.contract] schemas` 가 정본이다. 이웃 영역의 사실은 복사하지 않는다.)

## 3. 공개 API
`src/__PKG__/__init__.py` 의 `__all__` 이 공개 API 다. 구현은 `core/`, 생성 타입은 `contract/` 다.

| 이름 | 입력 | 출력 | 하는 일 |
|---|---|---|---|
| (아직 없다) | | | |

## 4. 실행·시험 명령
```
uv sync
uv run pytest
uv run lint-imports   # 경계 점검
uv run pyright        # 타입 검사(strict)
uv run ruff check     # 린트
uv run --project ../../tools/checks openit-gen-contract .   # 계약 타입 다시 만들기(`schemas` 를 바꾼 뒤)
```
서비스·잡이 쓰려면 `tools/new-area {service|job} <이름> --lib __AREA__` 로 만들거나, 영역 폴더에서 `uv add ../../libs/__AREA__` 를 한다(경로 의존, ADR 0020).

## 5. 시험 상태
(시험을 돌린 날짜와 결과를 쓴다. 돌리지 않았으면 돌리지 않았다고 쓴다.)

## 6. ADR 목록
- [0001 템플릿에서 시작](docs/adr/0001-템플릿에서-시작.md)
