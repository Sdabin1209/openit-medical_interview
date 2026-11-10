"""학습 서버의 학습 파일로 직렬화와 출력 검증을 잰다(ssh 로 읽어 온 사본, 서버에는 아무것도 남기지 않는다).

`MODEL_IO_DATASET_DIR` 아래에 final/ 과 finaltest/ 의 lora_a_*.jsonl, lora_b_*.jsonl 이 있어야 한다.
돌리기: MODEL_IO_DATASET_DIR=<폴더> uv run pytest -m dataset -s
"""

import json
import os
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from helpers import bank, context
from model_io import (
    check_extraction_output,
    compose_extraction_input,
    compose_response_from_request,
    compose_response_input,
    compose_start_input,
    serialize_extraction_input,
    serialize_response_input,
)

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


def test_response_input_is_composed_from_structured_values_exactly() -> None:
    """LoRA-A 정답 출력과 입력 state 와 다음 질문 문장에서 만든 LoRA-B 입력이 학습 파일의 B 입력과 같다(내용,
    직렬화)."""
    pairs: dict[tuple[str, str], dict[str, tuple[str, str]]] = {}
    for kind in ("a", "b"):
        for path in _files(kind):
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                messages = record["messages"]
                key = (str(path.relative_to(str(ROOT))).replace(f"lora_{kind}_", "lora_x_"), record["scenario_id"])
                pairs.setdefault(key, {})[kind] = (messages[1]["content"], messages[2]["content"])
    composed = starts = different = bytes_equal = 0
    for sides in pairs.values():
        if "b" not in sides:
            continue
        expected = json.loads(sides["b"][0])
        if expected["action"] == "START":
            starts += 1
            assert compose_start_input(expected["next"]["text"]) == expected
            continue
        payload = json.loads(sides["a"][0])
        output = json.loads(sides["a"][1])
        result = compose_response_input(
            output, payload["question_id"], payload["user_utterance"], payload["state"], expected["next"].get("text")
        )
        composed += 1
        different += result != expected
        bytes_equal += serialize_response_input(result) == sides["b"][0]
    print(f"\nB 입력 만들기: 같음 {composed - different}/{composed}, 바이트까지 같음 {bytes_equal}, START {starts}")
    assert (composed, different) == (46655, 0) and bytes_equal == composed - 10


def _flow_positions() -> dict[str, int]:
    return {rule["item_id"]: index for index, rule in enumerate(bank()["flow"]["rules"])}


def _request_slots(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """학습 파일의 A 입력 state 에서 서비스가 보낼 저장된 칸 목록(대화 순서)과 직전 문항을 되만든다(시험용 되만들기).

    직전 문항은 학습 파일에 없어서, state 문항 중 지금 문항·참조 원천이 아닌 것 가운데 순서표에서 가장 뒤의 것으로
    정한다.
    """
    from model_io import reference_item

    order = _flow_positions()
    question = str(payload["question_id"])
    state: dict[str, Any] = payload["state"]
    entries = sorted(state.items(), key=lambda kv: order[str(kv[0]).split("[")[0].rsplit(".", 1)[0]])
    items = {str(key).split("[")[0].rsplit(".", 1)[0] for key in state}
    others = [i for i in items if i not in (question, reference_item(question)) and order[i] < order[question]]
    previous = max(others, key=lambda i: order[i]) if others else None
    return [{"key": key, "value": entry["value"], "status": entry["status"]} for key, entry in entries], previous


def test_extraction_input_is_composed_from_structured_values() -> None:
    """저장된 칸 목록에서 state 를 고르고 묶는 규칙의 재현율(학습 파일 A 입력 46655행, prev_state.py 의 시나리오 정보
    부분은 재현 불가)."""
    rows = {"final": [0, 0, 0], "finaltest": [0, 0, 0]}  # 행, 칸 집합 같음, 칸 순서까지 같음
    byte_equal = 0
    for path in _files("a"):
        for user, _ in _rows(path):
            payload = json.loads(user)
            slots, previous = _request_slots(payload)
            composed, order = compose_extraction_input(
                payload["question_id"], payload["current_question"], payload["user_utterance"], slots, previous
            )
            counts = rows[path.parent.name]
            counts[0] += 1
            counts[1] += set(composed["state"]) == set(payload["state"])
            same_order = list(composed["state"]) == list(payload["state"])
            counts[2] += same_order
            assert composed["state"] == {k: payload["state"][k] for k in composed["state"]}, "값과 상태는 그대로"
            byte_equal += same_order and serialize_extraction_input(composed, order) == user
    print(f"\nA 입력 만들기(칸 집합 같음 / 칸 순서까지 같음): {rows}, 바이트까지 같음 {byte_equal}")
    for counts in rows.values():
        assert counts[1] == counts[0]  # 고르는 규칙(지금·직전·참조 원천)은 모두 같다
    assert rows["final"][2] / rows["final"][0] >= 0.984  # 묶음 순서 재현율(측정 98.48%)


def test_response_input_is_composed_from_the_request_shape() -> None:
    """응답 생성 요청의 모양(저장된 칸, A 출력의 값·대상, 다음 자리)에서 만든 B 입력이 학습 파일의 B 입력과 같다."""
    pairs: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for kind in ("a", "b"):
        for path in _files(kind):
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                key = (str(path.relative_to(str(ROOT))).replace(f"lora_{kind}_", "lora_x_"), record["scenario_id"])
                pairs.setdefault(key, {})[kind] = {
                    "user": json.loads(record["messages"][1]["content"]),
                    "out": json.loads(record["messages"][2]["content"]) if kind == "a" else None,
                }
    composed = different = 0
    for sides in pairs.values():
        if "b" not in sides or sides["b"]["user"]["action"] == "START" or "a" not in sides:
            continue
        a_in, a_out, expected = sides["a"]["user"], sides["a"]["out"], sides["b"]["user"]
        slots, previous = _request_slots(a_in)
        request: dict[str, Any] = {
            "action": a_out["action"],
            "question_id": a_in["question_id"],
            "user_utterance": a_in["user_utterance"],
            "slots": slots,
            "values": a_out["values"],
            "next": expected["next"],
            **({"previous_question_id": previous} if previous else {}),
            **{name: a_out[name] for name in ("reason", "targets", "note") if name in a_out},
        }
        composed += 1
        different += compose_response_from_request(request) != expected
    print(f"\nB 입력 요청 모양에서 만들기: 같음 {composed - different}/{composed}")
    assert composed == 46655 and different / composed < 0.003
