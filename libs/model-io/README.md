# model-io

## 1. 하는 일
모델 입력 직렬화, LoRA-A 출력 검증(output_guard)과 값 고쳐 쓰기(D115), 평가 지표 계산을 한다. 데이터셋 입출력 규칙(`contracts/inputs/labels.py`, `IO_SPEC.md`)이 닿는 코드는 이 라이브러리가 유일하다. model-runtime(운영)과 model-lab(평가)이 같은 코드를 쓴다(D97).

## 2. 쓰는 계약
`pyproject.toml` 의 `[tool.openit.contract] schemas` 가 정본이다. 합격 조건 명세(`ActionExtractionRules`)의 **값**은 요청에 실리지 않으므로 이 라이브러리가 `DEFAULT_RULES` 로 가진다(근거 주석은 `core/rules.py`). 이웃 영역의 사실은 복사하지 않는다.

## 3. 공개 API
`src/model_io/__init__.py` 의 `__all__` 이 공개 API 다. 구현은 `core/`, 생성 타입은 `contract/` 다. 입력은 계약 값을 JSON 으로 푼 모양(dict)이다. 영역이 가진 생성 클래스와 이 라이브러리의 생성 클래스가 서로 다른 클래스이므로 클래스를 넘기지 않는다.

| 이름 | 입력 | 출력 | 하는 일 |
|---|---|---|---|
| `serialize_extraction_input` | `ActionExtractionInput` 의 dict, `state_key_order` | 글자 | LoRA-A 모델 입력 글자. 최상위 키 정렬, state 는 요청의 순서 |
| `serialize_response_input` | `ResponseRequest` 의 dict | 글자 | LoRA-B 모델 입력 글자. 모든 수준 정렬 |
| `build_flow_index`, `build_field_index` | 순서표, 칸 규격 | 색인 | 요청의 `flow`, `fields` 를 검증에 쓰는 색인으로 |
| `compose_extraction_input` | 질문 문항, 직전 문항, 상담원 말, 발화, 저장된 칸 목록 | 모델 입력 객체, state 칸 순서 | LoRA-A 입력 만들기. state 에 넣을 문항(지금·직전·참조 원천 REF_SOURCE)과 묶음 순서를 고른다 |
| `compose_response_from_request` | 응답 생성 요청(`ResponseGenerationRequest` 의 dict) | LoRA-B 입력 객체 | 저장된 칸에서 state 를 고르고 topic·known·ask·previous·current·hold 를 만든다. START 는 다음 문항의 topic 과 질문 문장 |
| `select_state`, `reference_item` | 저장된 칸 목록, 문항 | state, 참조 원천 문항 | state 고르기와 정본 REF_SOURCE 찾기 |
| `ModelInputError` | | 예외 | 문항·칸·값이 정본의 표에 없어 글을 만들 수 없다(서버는 400) |
| `compose_response_input`, `compose_start_input` | LoRA-A 출력·state·발화·다음 질문 문장, 또는 첫 질문 문장 | `ResponseRequest` 의 dict | 데이터셋 정본의 표와 문장 틀로 topic·known·ask·previous·current·hold 를 만든다 |
| `check_extraction_output` | 모델 출력 글자, `GuardContext` | `GuardOutcome` | 위반 코드 10개를 한 번에 검사, D115 고쳐 쓰기, 검증된 출력 또는 출력 불가 |
| `find_violations` | 모델 출력 글자, `GuardContext` | `Violation` 목록 | 고쳐 쓰기 전 출력의 위반만(의미 위반율 계산용) |
| `expected_next_item` | action, 출력, `GuardContext` | 문항 또는 `None` | 계약 `NextItemRule` 이 정한 next_item |
| `evaluate_extraction`, `evaluate_responses`, `build_report` | 표본들 | 지표, `EvaluationReport` | 계약 필수 지표 아홉 개 계산 |

## 4. 실행·시험 명령
```
uv sync
uv run pytest                 # 단위·계약 시험(학습 파일 없이)
uv run lint-imports           # 경계 점검
uv run pyright                # 타입 검사(strict)
uv run ruff check             # 린트
MODEL_IO_DATASET_DIR=<폴더> uv run pytest -m dataset -s   # 학습 파일 시험. <폴더>/final/, <폴더>/finaltest/ 에 lora_a_*.jsonl, lora_b_*.jsonl
uv run --project ../../tools/checks openit-gen-contract .   # 계약 타입 다시 만들기(`schemas` 를 바꾼 뒤)
```
학습 파일은 학습 서버에서 `ssh openit "cat ~/dataset/final/lora_a_train.jsonl"` 처럼 읽어 와 리포 밖(또는 git 제외 폴더)에 둔다. 서버에는 아무것도 만들지 않는다.

## 5. 시험 상태
측정 결과는 [services/model-runtime/README.md](../../services/model-runtime/README.md) 5절에 있다(한 곳에만 쓴다). 시험이 지키는 것: 위반 코드 10개마다 위반 사례, 고쳐 쓰기, 직렬화, 지표, 그리고 OUTPUT_SCHEMA 판정이 계약 `ActionExtraction` 의 JSON Schema 판정과 같은지(`tests/contract`).

## 6. ADR 목록
- [0001 템플릿에서 시작](docs/adr/0001-템플릿에서-시작.md)
- [0002 출력 검증과 직렬화의 구조](docs/adr/0002-출력-검증과-직렬화의-구조.md)
- [0003 사람 말 표와 문장 틀을 정본에서 그대로 옮긴다](docs/adr/0003-사람-말-표와-문장-틀을-정본에서-그대로-옮긴다.md)
- [0004 LoRA-A state 고르기와 묶음 순서](docs/adr/0004-LoRA-A-state-고르기와-묶음-순서.md)
