"""output_guard 컴포넌트: 규칙은 libs/model-io 시험이 보고, 여기는 연결(요청 값 → 검증 결과)만 본다."""

import json
from typing import Any

from model_runtime.components.output_guard import guard
from model_runtime.types import GuardRequest
from scenario.world import A_NEXT_GOLD, bank


def request(raw: str, state: dict[str, Any] | None = None) -> GuardRequest:
    return GuardRequest(raw, "Q1.D01", bank()["flow"], bank()["fields"], state or {})


def test_valid_output_passes() -> None:
    result = guard(request(json.dumps(A_NEXT_GOLD)))
    assert result.output == A_NEXT_GOLD and result.violation_codes == [] and result.rewrites == []


def test_violations_are_reported_before_rewrite() -> None:
    result = guard(request(json.dumps({**A_NEXT_GOLD, "next_item": "Q5"})))
    assert result.violation_codes == ["NEXT_ITEM_MISMATCH"] and result.rewrites == ["NEXT_ITEM_FILLED"]
    assert result.output is not None and result.output["next_item"] == "Q1.D02"


def test_unavailable_output_is_none() -> None:
    result = guard(request("not json"))
    assert result.output is None and result.violation_codes == ["OUTPUT_SCHEMA"]
