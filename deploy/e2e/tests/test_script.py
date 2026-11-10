"""대본 시험: 대본이 순서표·칸 규격과 맞고, 평가 집합이 학습 형식이다."""

from __future__ import annotations

import json
from pathlib import Path

from openit_e2e import questionnaire, script
from openit_e2e.contract import Contract

REPO = Path(__file__).resolve().parents[3]
BANK = questionnaire.load(REPO / "contracts" / "inputs" / "SQL.md")


def test_script_walks_the_flow_to_the_end_with_skips() -> None:
    order = script.walk(BANK)
    assert order[0] == "Q1.D01" and order[-1] == "Q10"
    assert not {"Q4_1", "Q5_1", "Q6_1", "Q7_1", "Q7_2", "Q8_2"} & set(order)  # 대본의 답이 건너뛰기를 일으킨다
    assert len(order) == len(script.SCRIPT) == 25
    assert len({turn.item for turn in script.SCRIPT}) == len(script.SCRIPT)


def test_expected_keys_are_fields_of_the_item_with_values_of_the_right_type() -> None:
    types = {"boolean": bool, "integer": int, "number": (int, float), "option": str}
    specs = {f"{field['item_id']}.{field['field_name']}": field for field in BANK.fields}
    for turn in script.SCRIPT:
        for key, value in turn.expected.items():
            assert key.startswith(f"{turn.item}."), (turn.item, key)
            spec = specs[key]
            assert isinstance(value, types[spec["data_type"]]), key
            if spec["data_type"] == "option":
                assert value in {option["option_code"] for option in spec["options"]}, key
            if "minimum" in spec:
                assert value >= spec["minimum"], key
            if "maximum" in spec:
                assert value <= spec["maximum"], key


def test_every_utterance_fits_the_contract_limit() -> None:
    contract = Contract(REPO / "contracts")
    validator = contract.named("TurnRequest")
    for turn in script.SCRIPT:
        assert contract.schema_errors(validator, {"turn_id": "11111111-2222-4333-8444-555555555555", "utterance": turn.utterance}) == [], (
            turn.item
        )


def test_evaluation_rows_are_training_format_with_contract_shaped_outputs() -> None:
    eval_a, eval_b = script.evaluation_rows(BANK, "시스템 A", "시스템 B")
    contract = Contract(REPO / "contracts")
    extraction = contract.named("ActionExtraction")
    rows_a = [json.loads(line) for line in eval_a.splitlines()]
    rows_b = [json.loads(line) for line in eval_b.splitlines()]
    assert len(rows_a) == 4 and len(rows_b) == 3
    for row in rows_a + rows_b:
        assert [message["role"] for message in row["messages"]] == ["system", "user", "assistant"]
    for row in rows_a:
        user = json.loads(row["messages"][1]["content"])
        assert sorted(user) == ["current_question", "question_id", "state", "user_utterance"]
        assert contract.schema_errors(extraction, json.loads(row["messages"][2]["content"])) == []
    assert json.loads(rows_a[2]["messages"][2]["content"])["next_item"] == "Q5"  # Q4 아니요: Q4_1 건너뜀
    assert json.loads(rows_a[3]["messages"][2]["content"])["next_item"] == "END"
    assert json.loads(rows_b[0]["messages"][1]["content"])["action"] == "START"
