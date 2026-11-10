"""OUTPUT_SCHEMA 검사가 계약 ActionExtraction 스키마(JSON Schema 2020-12)와 같은 판정을 내는지 본다.

왜 이 시험이 있나: 생성 모델은 스키마의 if/then 조건을 담지 못해 검사기가 그 조건을 코드로 갖는다.
계약이 바뀌어 둘이 어긋나면 이 시험이 먼저 깨진다(계약 값을 복사해 두지 않고 계약 파일을 직접 읽는다).
"""

import itertools
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from helpers import context
from model_io import find_violations
from model_io.contract.models import ViolationCode

COMPONENTS = Path(__file__).resolve().parents[4] / "contracts" / "components.yaml"


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    document = yaml.safe_load(COMPONENTS.read_text(encoding="utf-8"))
    schema = {"$ref": "#/components/schemas/ActionExtraction", "components": document["components"]}
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _value(key: str, val: object, precision: str, status: str, save: bool) -> dict[str, object]:
    return {"key": key, "value": val, "precision": precision, "status": status, "save": save}


def _candidates() -> list[dict[str, Any]]:
    base_value = _value("Q1.D01.diagnosed", True, "exact", "ANSWERED", True)
    gap = _value("Q1.D01.on_medication", None, "unspecified", "MISSING", False)
    cases: list[dict[str, Any]] = []
    actions = ["NEXT", "CORRECT", "REASK", "CONFIRM", "HOLD", "SKIP", "REDIRECT", "JUMP", None, 3]
    reasons = [None, "MISSING", "OUT_OF_SCHEMA", "OFF_TOPIC", "NOPE"]
    for action, reason, targets, note in itertools.product(
        actions, reasons, [None, ["Q1.D01.on_medication"], []], [None, "손이 저림"]
    ):
        body: dict[str, Any] = {"next_item": "Q1.D01", "values": [base_value, gap]}
        for name, item in (("action", action), ("reason", reason), ("targets", targets), ("note", note)):
            if item is not None or (name == "action" and action is None):
                body[name] = item
        cases.append(body)
    for precision, val in itertools.product(
        ["exact", "approximate", "unspecified", "x"], [None, True, 3, 2.5, "yes", "x" * 301]
    ):
        cases.append(
            {
                "action": "NEXT",
                "next_item": "Q2",
                "values": [_value("Q1.D01.diagnosed", val, precision, "ANSWERED", True)],
            }
        )
    for key in ["action", "next_item", "values"]:
        body = {"action": "NEXT", "next_item": "Q2", "values": [base_value]}
        del body[key]
        cases.append(body)
    cases += [
        {"action": "NEXT", "next_item": "Q2", "values": [base_value], "extra": 1},
        {"action": "NEXT", "next_item": "Q2" * 7, "values": []},
        {"action": "NEXT", "next_item": "Q2", "values": [base_value] * 9},
        {"action": "NEXT", "next_item": "END", "values": [{**base_value, "key": "bad key"}]},
        {"action": "NEXT", "next_item": "END", "values": [{**base_value, "save": 1}]},
        {"action": "NEXT", "next_item": "END", "values": [{**base_value, "status": "DONE"}]},
        {"action": "NEXT", "next_item": 5, "values": []},
        {"action": "NEXT", "next_item": "END", "values": "no"},
    ]
    return cases


def test_output_schema_verdict_matches_contract_schema(validator: Draft202012Validator) -> None:
    mismatches: list[str] = []
    cases = _candidates()
    assert len(cases) > 300
    for case in cases:
        schema_valid: bool = validator.is_valid(case)  # pyright: ignore[reportUnknownMemberType]
        found = ViolationCode.OUTPUT_SCHEMA in {v.code for v in find_violations(json.dumps(case), context("Q1.D01"))}
        if found == schema_valid:
            mismatches.append(json.dumps(case, ensure_ascii=False)[:160])
    assert mismatches == [], f"{len(mismatches)}건 판정이 다르다: {mismatches[:3]}"
