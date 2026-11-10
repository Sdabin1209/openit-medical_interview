# __AREA__

## 1. 하는 일
(영역이 하는 일을 한 문단으로 쓴다.)

## 2. 받는 계약·내는 계약
(`contracts/`의 어느 계약을 받고 내는지 링크한다. 이웃 영역의 사실은 복사하지 않는다.)

## 3. 컴포넌트
| 컴포넌트 | 파일 | 입력 | 출력 | 하는 일 |
|---|---|---|---|---|
| greeter | `src/__PKG__/components/greeter.py` | `GreetingRequest` | `Greeting` | 템플릿 예시. 지우고 자기 컴포넌트로 바꾼다 |

## 4. 실행·시험 명령
```
uv sync
uv run pytest            # 단위·계약·마이그레이션 시험
DATABASE_URL_FILE=<연결 문자열 파일> uv run alembic upgrade head   # DB 마이그레이션(리비전: src/__PKG__/store/migrations/versions/)
uv run lint-imports      # 경계 점검
uv run pyright           # 타입 검사(strict)
uv run ruff check        # 린트
deploy/deploy build __AREA__   # 이미지 빌드
tools/smoke service __AREA__           # 이미지 스모크(/healthz, /readyz)
```

## 5. 시험 상태
(시험을 돌린 날짜와 결과를 쓴다. 돌리지 않았으면 돌리지 않았다고 쓴다.)

## 6. ADR 목록
- [0001 템플릿에서 시작](docs/adr/0001-템플릿에서-시작.md)
