"""모델 입출력 v3 학습 파일(dataset1118)로 직렬화·출력 검증·B 입력 만들기를 잰다.

ssh 로 읽어 온 사본을 쓰고 학습 서버에는 아무것도 남기지 않는다.

`MODEL_IO_DATASET_DIR_V3` 에 lora_a_{train,val,test}.jsonl, lora_b_{train,val,test}.jsonl 이 있어야 한다(학습 서버
~/taehyeon/data/dataset1118/lora_a_*.jsonl 과 ~/dataset/dataset1118/{train,validation,test}/lora_b.jsonl).
돌리기: MODEL_IO_DATASET_DIR_V3=<폴더> uv run pytest -m dataset -s tests/dataset/test_training_files_v3.py
"""

import json
import os
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from helpers import context
from model_io import (
    check_extraction_output,
    compose_response_from_request,
    compose_response_input,
    compose_start_input,
    serialize_extraction_input,
)

pytestmark = pytest.mark.dataset
SPLITS = ("train", "val", "test")
CARRIED = ("ask", "previous", "current")


def _root() -> Path:
    root = os.environ.get("MODEL_IO_DATASET_DIR_V3")
    if not root:
        pytest.fail("MODEL_IO_DATASET_DIR_V3 가 없다")
    return Path(root)


def _records(kind: str) -> Iterator[tuple[str, dict[str, Any]]]:
    for split in SPLITS:
        for line in (_root() / f"lora_{kind}_{split}.jsonl").read_text(encoding="utf-8").splitlines():
            yield split, json.loads(line)


def test_a_input_is_byte_equal_with_sorted_keys() -> None:
    counts: Counter[bool] = Counter()
    for _, record in _records("a"):
        user = record["messages"][1]["content"]
        payload = json.loads(user)
        counts[serialize_extraction_input(payload, list(payload["state"]), model_io_version="model-io-v3") == user] += 1
    print(f"\nv3 A 입력 직렬화: {dict(counts)}")
    assert counts == Counter({True: 68817})


def test_gold_outputs_have_zero_violations() -> None:
    counts: Counter[tuple[bool, bool, bool]] = Counter()
    for _, record in _records("a"):
        payload = json.loads(record["messages"][1]["content"])
        result = check_extraction_output(
            record["messages"][2]["content"], context(payload["question_id"], payload["state"], "model-io-v3")
        )
        counts[(bool(result.violations), result.valid, bool(result.rewrites))] += 1
    print(f"\nv3 정답 출력(위반, 유효, 고쳐 쓰기): {dict(counts)}")
    assert counts == Counter({(False, True, False): 68817})


def test_b_inputs_are_composed_exactly() -> None:
    """A 정답·입력에서 만든 B 입력이 학습 B 입력과 같다.

    설명 요청의 이어 받기(직전 턴이 필요)는 이어 받은 칸만 다르다.
    """
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for kind in ("a", "b"):
        for split, record in _records(kind):
            pairs.setdefault((split, record["scenario_id"]), {})[kind] = record
    result: Counter[str] = Counter()
    for (_, scenario), sides in pairs.items():
        if "b" not in sides:
            continue
        b = json.loads(sides["b"]["messages"][1]["content"])
        if b["action"] == "START":
            got = compose_start_input(b["next"]["text"])
        elif b.get("reason") == "LIMIT_REACHED":
            item = scenario[2 : scenario.index("_P22")]  # scenario_id c_{문항}_P22_... (fixaug.py)
            got = compose_response_from_request(
                {
                    "runtime_contract_version": 1,
                    "action": "SKIP",
                    "reason": "LIMIT_REACHED",
                    "question_id": item,
                    "user_utterance": b["user_utterance"],
                    "slots": [],
                    "values": [],
                    "next": b["next"],
                }
            )
        else:
            a_in = json.loads(sides["a"]["messages"][1]["content"])
            a_out = json.loads(sides["a"]["messages"][2]["content"])
            got = compose_response_input(
                a_out, a_in["question_id"], a_in["user_utterance"], a_in["state"], b["next"].get("text")
            )
        if got == b:
            result["같음"] += 1
        elif b["action"] == "REDIRECT" and {k: v for k, v in b.items() if k not in CARRIED} == got:
            result["이어 받은 칸만 다름"] += 1
        else:
            result["다름"] += 1
    print(f"\nv3 B 입력 만들기(scenario_id 짝 기준): {dict(result)}")
    # 왜 1499: 직전 되묻기·확인의 내용을 이어 받은 설명 요청 행 수(dataset1118 실측). 그 밖은 모두 같아야 한다
    assert result["다름"] == 0 and result["이어 받은 칸만 다름"] == 1499 and result["같음"] > 0
