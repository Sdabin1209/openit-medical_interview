"""학습 서버의 학습 파일로 직렬화와 출력 검증을 잰다(ssh 로 읽어 온 사본, 서버에는 아무것도 남기지 않는다).

`MODEL_IO_DATASET_DIR` 아래에 final/ 과 finaltest/ 의 lora_a_*.jsonl, lora_b_*.jsonl 이 있어야 한다.
돌리기: MODEL_IO_DATASET_DIR=<폴더> uv run pytest -m dataset -s
"""

import json
import os
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

from helpers import context
from model_io import check_extraction_output, serialize_extraction_input, serialize_response_input

pytestmark = pytest.mark.dataset

ROOT = os.environ.get("MODEL_IO_DATASET_DIR")


def _files(kind: str) -> list[Path]:
    if not ROOT:
        pytest.fail("MODEL_IO_DATASET_DIR 가 없다")
    found = sorted(Path(ROOT).glob(f"final*/lora_{kind}_*.jsonl"))
    assert found, f"{ROOT} 에 lora_{kind}_*.jsonl 이 없다"
    return found


def _rows(path: Path) -> Iterator[tuple[str, str]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        messages = json.loads(line)["messages"]
        yield messages[1]["content"], messages[2]["content"]


def test_extraction_input_is_byte_equal_to_training_user_message() -> None:
    """final(학습·검증·시험) 44563행은 바이트까지 같다. finaltest 는 state 항목 안 키 순서만 다르다(변경 요청
    model-runtime-001)."""
    equal: Counter[str] = Counter()
    different: Counter[str] = Counter()
    for path in _files("a"):
        for user, _ in _rows(path):
            payload = json.loads(user)
            text = serialize_extraction_input(payload, list(payload["state"]))
            assert json.loads(text) == payload, "글자는 달라도 내용은 같아야 한다"
            (equal if text == user else different)[path.parent.name] += 1
    print(f"\nA 입력 직렬화: 같음 {dict(equal)}, 다름 {dict(different)}")
    assert different["final"] == 0 and equal["final"] == 44563
    assert equal["finaltest"] + different["finaltest"] == 2092


def test_response_input_matches_training_user_message() -> None:
    """B 입력: 모든 수준 정렬이 학습 user 메시지와 같다. 정렬되지 않은 채 학습 파일에 들어간 행은 따로 센다."""
    same = unsorted = 0
    for path in _files("b"):
        for user, _ in _rows(path):
            payload = json.loads(user)
            text = serialize_response_input(payload)
            assert json.loads(text) == payload
            same += text == user
            unsorted += text != user
    print(f"\nB 입력 직렬화: 같음 {same}, 정렬되지 않은 학습 행 {unsorted}")
    assert same == 46764 and unsorted == 10


def test_gold_extraction_outputs_have_zero_violations() -> None:
    """학습 파일의 정답 출력 46655행이 모든 합격 조건을 지키고 고쳐 쓰기가 아무것도 바꾸지 않는다."""
    rows = violations = invalid = rewritten = 0
    codes: Counter[str] = Counter()
    for path in _files("a"):
        for user, output in _rows(path):
            payload = json.loads(user)
            result = check_extraction_output(output, context(payload["question_id"], payload["state"]))
            rows += 1
            violations += bool(result.violations)
            invalid += not result.valid
            rewritten += bool(result.rewrites)
            codes.update(v.code.value for v in result.violations)
            assert result.output is None or result.output == json.loads(output)
    print(
        f"\n정답 출력 {rows}행: 위반 {violations}행, 출력 불가 {invalid}행, "
        f"고쳐 쓰기 {rewritten}행, 위반 코드 {dict(codes)}"
    )
    assert (rows, violations, invalid, rewritten) == (46655, 0, 0, 0)
