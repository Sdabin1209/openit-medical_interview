"""평가 보고서 지표 계산(계약 RequiredMetricName 의 아홉 지표). model-lab 의 평가와 package_publish 가 같은 계산을
쓴다(D97).

추론은 이 라이브러리 밖이다(실제 엔진이 필요하다). 여기는 모은 출력으로 지표를 셀 뿐이라 GPU 가 없어도 돈다.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from model_io.contract.models import EvaluationReport, ViolationCode
from model_io.core.guard import find_violations
from model_io.core.jsonvalue import as_list, as_map
from model_io.core.types import GuardContext

_GROUP = "ACCURACY"  # 왜: 계약 D97 의 그룹 이름
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class ExtractionSample:
    """LoRA-A 평가 표본 하나: 검증 맥락, 정답 출력, 모델이 낸 글자(호출이 실패했으면 None), 호출 시간(초)."""

    context: GuardContext
    gold: Mapping[str, object]
    raw: str | None
    seconds: float


@dataclass(frozen=True)
class ResponseSample:
    """LoRA-B 평가 표본 하나: 모델 입력(JSON 으로 푼 모양), 모델이 낸 문장(호출이 실패했으면 None), 호출 시간(초)."""

    payload: Mapping[str, object]
    text: str | None
    seconds: float


def _metric(name: str, value: float, unit: str, count: int, slice_: str | None = None) -> dict[str, object]:
    body: dict[str, object] = {"name": name, "group": _GROUP, "value": value, "unit": unit, "sample_count": count}
    if slice_ is not None:
        body["slice"] = slice_
    return body


def _ratio(name: str, numerator: int, denominator: int, slice_: str | None = None) -> dict[str, object]:
    # 왜 분모 0 이면 값 0: 계약 D96 이 n=0 도 보고하라고 한다. 표본 수 0 이 '재지 못했다'를 말한다
    return _metric(name, numerator / denominator if denominator else 0.0, "ratio", denominator, slice_)


def _triples(output: Mapping[str, object] | None) -> dict[tuple[str, str, str], str]:
    """(키, 값, 상태) -> 정확도. 값은 자료형까지 구분하는 JSON 글자로 비교한다(참·거짓과 1 은 다르다)."""
    result: dict[tuple[str, str, str], str] = {}
    for raw in (as_list(output.get("values")) if output else None) or []:
        entry = as_map(raw)
        if entry is not None:
            triple = (str(entry.get("key")), json.dumps(entry.get("value")), str(entry.get("status")))
            result[triple] = str(entry.get("precision"))
    return result


def _parsed(raw: str | None) -> Mapping[str, object] | None:
    if raw is None:
        return None
    try:
        return as_map(json.loads(raw))
    except ValueError:
        return None


def p95(seconds: Sequence[float]) -> float:
    """95 백분위수(최근접 순위법). 표본이 없으면 0."""
    if not seconds:
        return 0.0
    ordered = sorted(seconds)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def evaluate_extraction(samples: Sequence[ExtractionSample], constrained_decoding: bool) -> list[dict[str, object]]:
    """LoRA-A 지표들. `constrained_decoding` 은 이 실행이 제약 디코딩을 켰는지다.

    켠 값과 끈 값은 실행이 따로다(D96(4)).
    """
    predicted = matched = gold_total = precision_hits = 0
    next_ok: Counter[str] = Counter()
    next_all: Counter[str] = Counter()
    schema_ok = violating = 0
    by_code: Counter[ViolationCode] = Counter()
    for sample in samples:
        out = _parsed(sample.raw)
        want, got = _triples(sample.gold), _triples(out)
        predicted += len(got)
        gold_total += len(want)
        for triple, precision in got.items():
            if triple in want:
                matched += 1
                precision_hits += precision == want[triple]
        action = str(sample.gold.get("action"))
        next_all[action] += 1
        next_ok[action] += out is not None and out.get("next_item") == sample.gold.get("next_item")
        violations = find_violations(sample.raw, sample.context) if sample.raw is not None else ()
        codes = {v.code for v in violations}
        schema_ok += sample.raw is not None and ViolationCode.OUTPUT_SCHEMA not in codes
        violating += bool(codes) or sample.raw is None
        by_code.update(codes)
    total = len(samples)
    metrics = [
        _ratio("value_precision", matched, predicted),
        _ratio("value_recall", matched, gold_total),
        _ratio("precision_match_rate", precision_hits, matched),
    ]
    metrics += [_ratio("next_item_accuracy", next_ok[a], next_all[a], f"action={a}") for a in sorted(next_all)]
    for flag in ("on", "off"):
        used = flag == ("on" if constrained_decoding else "off")
        metrics.append(
            _ratio("schema_valid_raw", schema_ok if used else 0, total if used else 0, f"constrained_decoding={flag}")
        )
    metrics.append(_ratio("semantic_violation_rate", violating, total))
    metrics += [
        _ratio("semantic_violation_rate", by_code[code], total, f"violation_code={code.value}")
        for code in ViolationCode
    ]
    metrics.append(_metric("length_p95_seconds", p95([s.seconds for s in samples]), "seconds", total))
    return metrics


def evaluate_responses(samples: Sequence[ResponseSample]) -> list[dict[str, object]]:
    """LoRA-B 지표들. 금지 표현 목록은 아직 없어 forbidden_expression_rate 는 표본 수 0 으로 보고한다(D96(5))."""
    with_numbers = ungrounded = 0
    for sample in samples:
        if sample.text is None:
            continue
        numbers = _NUMBER.findall(sample.text)
        if numbers:
            with_numbers += 1
            material = set(_NUMBER.findall(json.dumps(sample.payload, ensure_ascii=False)))
            ungrounded += any(number not in material for number in numbers)
    return [
        _ratio("ungrounded_number_rate", ungrounded, with_numbers),
        _ratio("forbidden_expression_rate", 0, 0),
        # 왜 다른 이름: length_p95_seconds 는 A 호출 시간이다. 같은 이름을 쓰면 보고서에서 둘을 가를 수 없다(계약
        # MetricName 은 자유 이름도 허용)
        _metric("response_call_p95_seconds", p95([s.seconds for s in samples]), "seconds", len(samples)),
    ]


def build_report(
    dataset_version_id: str, created_at: datetime, metrics: Sequence[Mapping[str, object]]
) -> EvaluationReport:
    """지표 목록을 계약 EvaluationReport 로 만든다(계약 검증을 거친다)."""
    return EvaluationReport.model_validate(
        {"dataset_version_id": dataset_version_id, "created_at": created_at, "metrics": list(metrics)}
    )
