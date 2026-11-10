"""model-io 공유 라이브러리의 공개 API. 여기 `__all__` 에 적은 것만 밖에서 쓴다(ADR 0020).

구현은 `core/`, 계약에서 생성한 타입은 `contract/` 에 있다. 밖(영역)은 `core`·`contract` 를 직접 import 하지 않는다.
"""

from model_io.core.bank import END, FieldIndex, FlowIndex, build_field_index, build_flow_index
from model_io.core.compose import compose_response_input, compose_start_input
from model_io.core.evaluate import (
    ExtractionSample,
    ResponseSample,
    build_report,
    evaluate_extraction,
    evaluate_responses,
)
from model_io.core.guard import check_extraction_output, expected_next_item, find_violations
from model_io.core.rules import DEFAULT_RULES
from model_io.core.serialize import serialize_extraction_input, serialize_response_input
from model_io.core.types import GuardContext, GuardOutcome, Rewrite, Violation

__all__ = [
    "DEFAULT_RULES",
    "END",
    "ExtractionSample",
    "FieldIndex",
    "FlowIndex",
    "GuardContext",
    "GuardOutcome",
    "ResponseSample",
    "Rewrite",
    "Violation",
    "build_field_index",
    "build_flow_index",
    "build_report",
    "check_extraction_output",
    "compose_response_input",
    "compose_start_input",
    "evaluate_extraction",
    "evaluate_responses",
    "expected_next_item",
    "find_violations",
    "serialize_extraction_input",
    "serialize_response_input",
]
