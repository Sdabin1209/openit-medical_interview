# __AREA__

## 1. 하는 일
(잡 영역이 하는 일을 한 문단으로 쓴다. HTTP 서버가 없다. 언제 돌지는 deploy 의 스케줄러가 정하고 영역은 모른다.)

## 2. 받는 계약·내는 계약
(`contracts/` 의 어느 계약을 받고 내는지 링크한다. 이웃 영역의 사실은 복사하지 않는다.)
- 내는 것: 잡 한 번의 결과 `JobRunResult`(표준 출력에 JSON 한 줄), 선언 `JobsDeclaration`(`jobs.json` 이 원본이고 이미지 라벨 `io.openit.jobs` 로 나간다).
- 쓰는 계약 스키마의 이름은 `pyproject.toml` 의 `[tool.openit.contract]` 가 정본이다.

## 3. 컴포넌트
| 컴포넌트 | 파일 | 입력 | 출력 | 하는 일 |
|---|---|---|---|---|
| counter | `src/__PKG__/components/counter.py` | `StepInput` | `StepOutput` | 템플릿 예시. 지우고 자기 컴포넌트로 바꾼다 |

잡은 `src/__PKG__/main.py` 의 `JOBS` 표(잡 이름 → 함수)에 더하고 `jobs.json` 에도 같은 이름과 시간 상한(`timeout_seconds`)을 쓴다. 두 이름 집합이 같은지 시험이 본다.

## 4. 실행·시험 명령
```
uv sync
uv run __PKG__ PURGE_EXPIRED   # 잡 하나를 한 번 실행. 표준 출력은 JobRunResult 한 줄, 종료 코드는 0(성공)·75(일시적 실패)·1(실패)
uv run pytest            # 단위·계약 시험
uv run lint-imports      # 경계 점검
uv run pyright           # 타입 검사(strict)
uv run ruff check        # 린트
deploy/deploy build __AREA__   # 이미지 빌드(진입점이 잡 명령이라 `docker run <이미지> <잡 이름>` 으로 한 번 실행한다)
uv run --project tools/checks openit-notices generate jobs/__AREA__   # 의존을 바꾼 뒤 THIRD_PARTY_NOTICES 를 잠금 파일에서 다시 만든다(리포 루트에서, ADR 0018)
uv run --project tools/checks openit-gen-contract jobs/__AREA__       # 계약 타입 다시 만들기(리포 루트에서, ADR 0020)
```

## 5. 시험 상태
(시험을 돌린 날짜와 결과를 쓴다. 돌리지 않았으면 돌리지 않았다고 쓴다.)

## 6. ADR 목록
- [0001 템플릿에서 시작](docs/adr/0001-템플릿에서-시작.md)
