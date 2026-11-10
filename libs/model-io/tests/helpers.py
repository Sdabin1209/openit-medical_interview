"""시험 공용 도구: 고정 문항 세트(tests/fixtures/question_bank_v1.json)로 검증 맥락을 만든다."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from model_io import GuardContext, build_field_index, build_flow_index

FIXTURES = Path(__file__).parent / "fixtures"


def bank() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((FIXTURES / "question_bank_v1.json").read_text(encoding="utf-8")))


def context(asked_item: str, state: Mapping[str, object] | None = None) -> GuardContext:
    data = bank()
    return GuardContext(asked_item, build_flow_index(data["flow"]), build_field_index(data["fields"]), state or {})


def value(
    key: str, val: object, status: str = "ANSWERED", precision: str = "exact", save: bool = True
) -> dict[str, object]:
    return {"key": key, "value": val, "precision": precision, "status": status, "save": save}


def gap(key: str, status: str = "MISSING") -> dict[str, object]:
    """값이 없는 칸(save 거짓)."""
    return {"key": key, "value": None, "precision": "unspecified", "status": status, "save": False}
