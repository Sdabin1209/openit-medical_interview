"""평가 지표: 정답과 같은 출력, 틀린 출력, 호출 실패, 위반이 지표에 어떻게 잡히는지."""

import json
from datetime import UTC, datetime

from helpers import context, gap, value
from model_io import ExtractionSample, ResponseSample, build_report, evaluate_extraction, evaluate_responses
from model_io.contract.models import EvaluationMetric, ExtraMetricName

GOLD = {
    "action": "REASK",
    "next_item": "Q1.D01",
    "reason": "MISSING",
    "targets": ["Q1.D01.on_medication"],
    "values": [value("Q1.D01.diagnosed", True), gap("Q1.D01.on_medication")],
}


def metrics(
    samples: list[ExtractionSample], constrained: bool = False
) -> dict[tuple[str, str | None], tuple[float, int]]:
    result: dict[tuple[str, str | None], tuple[float, int]] = {}
    for m in evaluate_extraction(samples, constrained):
        slice_ = m.get("slice")
        result[(str(m["name"]), None if slice_ is None else str(slice_))] = (
            float(str(m["value"])),
            int(str(m["sample_count"])),
        )
    return result


def sample(raw: str | None, seconds: float = 0.5) -> ExtractionSample:
    return ExtractionSample(context("Q1.D01"), GOLD, raw, seconds)


def test_gold_output_scores_perfectly() -> None:
    result = metrics([sample(json.dumps(GOLD))])
    assert result[("value_precision", None)] == (1.0, 2)
    assert result[("value_recall", None)] == (1.0, 2)
    assert result[("precision_match_rate", None)] == (1.0, 2)
    assert result[("next_item_accuracy", "action=REASK")] == (1.0, 1)
    assert result[("semantic_violation_rate", None)] == (0.0, 1)
    assert result[("schema_valid_raw", "constrained_decoding=off")] == (1.0, 1)
    assert result[("schema_valid_raw", "constrained_decoding=on")] == (0.0, 0)  # 이 실행에서 켜지 않았다


def test_wrong_value_and_wrong_precision_are_counted_separately() -> None:
    wrong = {
        **GOLD,
        "values": [value("Q1.D01.diagnosed", False), {**gap("Q1.D01.on_medication"), "precision": "unspecified"}],
    }
    approx = {**GOLD, "values": [value("Q1.D01.diagnosed", True, precision="approximate"), gap("Q1.D01.on_medication")]}
    result = metrics([sample(json.dumps(wrong)), sample(json.dumps(approx))])
    assert result[("value_precision", None)] == (0.75, 4)  # 4개 중 맞은 것 3개
    assert result[("precision_match_rate", None)] == (2 / 3, 3)  # 맞은 3개 중 정확도까지 맞은 것 2개


def test_violations_are_counted_per_code_and_failed_calls_are_violations() -> None:
    bad_next = {**GOLD, "next_item": "Q3"}
    result = metrics([sample(json.dumps(bad_next)), sample(None), sample("not json")])
    assert result[("semantic_violation_rate", None)] == (1.0, 3)
    assert result[("semantic_violation_rate", "violation_code=NEXT_ITEM_MISMATCH")][0] == 1 / 3
    assert result[("semantic_violation_rate", "violation_code=OUTPUT_SCHEMA")][0] == 1 / 3
    assert result[("next_item_accuracy", "action=REASK")] == (0.0, 3)


def test_p95_is_nearest_rank() -> None:
    samples = [sample(json.dumps(GOLD), seconds=n / 100) for n in range(1, 101)]
    assert metrics(samples)[("length_p95_seconds", None)] == (0.95, 100)


def test_empty_denominators_report_zero_samples() -> None:
    result = metrics([])
    assert result[("value_recall", None)] == (0.0, 0) and result[("length_p95_seconds", None)] == (0.0, 0)


def test_response_metrics() -> None:
    payload = {"action": "NEXT", "known": "하루 15분", "topic": "t", "next": {"type": "END"}}
    grounded = ResponseSample(payload, "하루 15분 하시는군요.", 1.0)
    invented = ResponseSample(payload, "하루 20분 하시는군요.", 2.0)
    plain = ResponseSample(payload, "알겠습니다.", 1.5)
    result = {
        (m["name"]): (m["value"], m["sample_count"])
        for m in evaluate_responses([grounded, invented, plain, ResponseSample(payload, None, 1.0)])
    }
    assert result["ungrounded_number_rate"] == (0.5, 2)
    assert result["forbidden_expression_rate"] == (0.0, 0)
    assert result["response_call_p95_seconds"] == (2.0, 4)


def _name(metric: EvaluationMetric) -> str:
    root = metric.name.root
    return root.root if isinstance(root, ExtraMetricName) else root.value


def test_report_is_a_valid_contract_report_with_the_required_metrics() -> None:
    gold_sample = sample(json.dumps(GOLD))
    report = build_report(
        "3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90",
        datetime(2026, 11, 10, tzinfo=UTC),
        evaluate_extraction([gold_sample], False),
    )
    required = {"value_precision", "value_recall", "precision_match_rate", "next_item_accuracy", "schema_valid_raw"}
    assert required | {"semantic_violation_rate", "length_p95_seconds"} <= {_name(m) for m in report.metrics}
