"""LoRA-A 출력 검증(output_guard): 계약의 합격 조건 위반 코드 10개를 한 번에 검사하고 D115 값 고쳐 쓰기를 적용한다.

결과는 검증된 출력 또는 출력 불가다. 위반은 고쳐 쓰기 전 모델 출력으로 센다(계약 ViolationCode, D115).
운영(model-runtime)과 평가(model-lab)가 같은 이 검사기를 쓴다(D97).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import ValidationError

from model_io.contract.models import ActionExtraction, ViolationCode
from model_io.core.bank import END, FieldIndex, next_after
from model_io.core.jsonvalue import as_list, as_map, as_str, is_number
from model_io.core.slots import family_of, try_parse_slot
from model_io.core.types import GuardContext, GuardOutcome, Rewrite, Violation

# 왜 이 순서: 정본 IO_SPEC.md 1장의 action 표
_ACTIONS_WITHOUT_EXTRAS = {"NEXT", "CORRECT"}
_ACTIONS_WITH_REASON_AND_TARGETS = {"REASK", "CONFIRM", "HOLD", "SKIP"}


@dataclass(frozen=True)
class _Found:
    violation: Violation
    fixable: bool = False  # D115 고쳐 쓰기로 해소되는 위반인가


def _parse(raw: str) -> Mapping[str, object] | None:
    def reject(constant: str) -> object:
        raise ValueError(constant)  # 왜: NaN·Infinity 는 JSON(RFC 8259)이 아니다

    try:
        return as_map(json.loads(raw, parse_constant=reject))
    except ValueError:
        return None


def _schema_found(raw: str, out: Mapping[str, object]) -> list[_Found]:
    """OUTPUT_SCHEMA: 계약 ActionExtraction. 칸·형식은 생성 모델(strict), if/then 조건은 아래에서 본다."""
    found: list[_Found] = []

    def bad(path: str) -> None:
        found.append(_Found(Violation(ViolationCode.OUTPUT_SCHEMA, path)))

    try:
        ActionExtraction.model_validate_json(raw, strict=True)
    except ValidationError as error:
        # 왜 첫 오류 위치만: 오류 내용에는 모델이 낸 환자 관련 글자가 들어갈 수 있다. 위치만 쓴다
        first = error.errors(include_input=False)[0]
        bad(".".join(str(part) for part in first["loc"]) or "$")
    action = as_str(out.get("action"))
    has = {name: name in out for name in ("reason", "targets", "note")}
    if action in _ACTIONS_WITHOUT_EXTRAS and any(has.values()):
        bad("reason|targets|note")  # 계약: NEXT·CORRECT 에는 reason, targets, note 가 없다
    if action in _ACTIONS_WITH_REASON_AND_TARGETS and not (has["reason"] and has["targets"]):
        bad("reason,targets")
    if action == "REDIRECT" and (not has["reason"] or has["targets"]):
        bad("reason|targets")
    if "reason" in out:
        if out.get("reason") == "OUT_OF_SCHEMA" and not has["note"]:
            bad("note")
        if out.get("reason") != "OUT_OF_SCHEMA" and has["note"]:
            bad("note")
    for index, raw_value in enumerate(as_list(out.get("values")) or []):
        value = as_map(raw_value)
        if value is None or "value" not in value:
            continue
        precision = value.get("precision")
        if value["value"] is None and precision != "unspecified":
            bad(f"values[{index}].precision")
        if value["value"] is not None and precision not in ("exact", "approximate"):
            bad(f"values[{index}].precision")
    return found


def _item_scope(ctx: GuardContext, out: Mapping[str, object]) -> set[str]:
    """OUT_OF_CURRENT_ITEM 이 허용하는 문항들(계약 CurrentItemScope)."""
    allowed: set[str] = set()
    scopes = {scope.value for scope in ctx.rules.current_item_rule.allowed_scopes}
    if "CURRENT_ITEM" in scopes:
        allowed.add(ctx.asked_item)
    if "ITEM_FAMILY" in scopes:
        allowed.update(item for item in ctx.flow.order if family_of(item) == family_of(ctx.asked_item))
    if "ITEM_RANGE_TO_NEXT_ITEM" in scopes:
        start = ctx.flow.position(ctx.asked_item)
        target = as_str(out.get("next_item"))
        stop = len(ctx.flow.order) - 1 if target == END else (ctx.flow.position(target) if target else None)
        if start is not None and stop is not None:
            low, high = sorted((start, stop))
            allowed.update(ctx.flow.order[low : high + 1])
    return allowed


def _type_ok(data_type: str, value: object) -> bool:
    if data_type == "boolean":
        return isinstance(value, bool)
    if data_type == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and value.is_integer()
        )
    if data_type == "number":
        return is_number(value)
    return isinstance(value, str)  # option, text


def _out_of_range(fields: FieldIndex, item: str, field_name: str, value: object) -> tuple[bool, bool]:
    """(범위 밖인가, 최댓값을 넘은 것인가). 수 칸에서만 본다."""
    spec = fields.specs.get((item, field_name))
    if spec is None or not is_number(value) or not isinstance(value, int | float):
        return False, False
    number = float(value)
    above = spec.maximum is not None and number > spec.maximum
    below = (spec.minimum is not None and number < spec.minimum) or (
        spec.exclusive_minimum is not None and number <= spec.exclusive_minimum
    )
    return above or below, above and not below


def expected_next_item(action: str, out: Mapping[str, object], ctx: GuardContext) -> str | None:
    """계약 NextItemRule 이 정한 next_item. 정하지 못하면(순서표에 없는 문항 등) None."""
    kinds = {rule.action.value: rule.rule.value for rule in ctx.rules.next_item_rules}
    kind = kinds.get(action)
    values = [m for raw in (as_list(out.get("values")) or []) if (m := as_map(raw)) is not None]
    targets = [t for t in (as_list(out.get("targets")) or []) if isinstance(t, str)]
    target_items = [slot[0] for t in targets if (slot := try_parse_slot(t)) is not None]
    if kind == "ASKED_ITEM":
        return ctx.asked_item
    if kind == "TARGET_ITEM":
        return target_items[0] if target_items else ctx.asked_item
    if kind != "SEQUENCE_AFTER_SAVED":
        return None
    value_items = [slot[0] for m in values if (slot := try_parse_slot(m.get("key"))) is not None]
    saved: dict[tuple[str, str], object] = {}
    for m in values:
        slot = try_parse_slot(m.get("key"))
        if slot is not None and m.get("save") is True:
            saved[(slot[0], slot[2])] = m.get("value")
    # 왜 첫 값의 문항: 데이터셋 정본 labels.py a_target 이 base = (값의 문항 or 대상의 문항 or 묻던 문항)[0] 다음 문항을
    # 정한다.
    # 학습 서버 final·finaltest 정답 46655건에서 불일치 0건(계약의 '가장 뒤 저장 문항' 식은 168건 불일치, 변경 요청
    # model-runtime-001)
    base = (value_items or target_items or [ctx.asked_item])[0]
    return next_after(ctx.flow, ctx.fields, base, saved)


def _semantic_found(out: Mapping[str, object], ctx: GuardContext) -> list[_Found]:
    found: list[_Found] = []
    rules = ctx.rules
    saved_statuses = {status.value for status in rules.saved_statuses}
    null_statuses = {status.value for status in rules.null_value_statuses}
    exempt_actions = {action.value for action in rules.current_item_rule.exempt_actions}
    exempt_statuses = {status.value for status in rules.current_item_rule.exempt_statuses}
    action = as_str(out.get("action")) or ""
    scope: set[str] | None = None
    keys: set[str] = set()
    for index, raw_value in enumerate(as_list(out.get("values")) or []):
        value = as_map(raw_value)
        if value is None:
            continue
        where = f"values[{index}]"
        key = value.get("key")
        status = value.get("status")
        if isinstance(key, str):
            keys.add(key)
        if (
            isinstance(status, str)
            and isinstance(value.get("save"), bool)
            and (status in saved_statuses) != value["save"]
        ):
            found.append(_Found(Violation(ViolationCode.SAVE_RULE, f"{where}.save")))
        if isinstance(status, str) and "value" in value and (value["value"] is None) != (status in null_statuses):
            found.append(_Found(Violation(ViolationCode.SAVE_RULE, f"{where}.value")))
        slot = try_parse_slot(key)
        if slot is None:
            continue
        item, repeat, field_name = slot
        if item not in ctx.flow.branches:
            found.append(_Found(Violation(ViolationCode.UNKNOWN_ITEM, f"{where}.key")))
            continue
        spec = ctx.fields.specs.get((item, field_name))
        # 왜 빈 반복 키는 저장하지 않는 값에만: 술 종류를 모르는 보류·재질문 값은 키에 [술 종류]가 없고 저장하지 않는다(SQL.md 6장).
        # 학습 파일 정답 Q7_1·Q7_2 칸 값 중 키 없는 6842개가 모두 save 거짓이다(실측, 저장하는 키 없는 값은 0개)
        empty_key_allowed = repeat == "" and spec is not None and value.get("save") is False
        if spec is None or (repeat not in spec.repeat_keys and not empty_key_allowed):
            found.append(_Found(Violation(ViolationCode.UNKNOWN_SLOT, f"{where}.key")))
            continue
        actual = value.get("value")
        if actual is not None:
            if not _type_ok(spec.data_type, actual):
                found.append(_Found(Violation(ViolationCode.VALUE_TYPE_MISMATCH, f"{where}.value")))
            elif spec.data_type == "option" and actual not in spec.options:
                found.append(_Found(Violation(ViolationCode.VALUE_NOT_IN_OPTIONS, f"{where}.value")))
            else:
                outside, above_only = _out_of_range(ctx.fields, item, field_name, actual)
                if outside:
                    found.append(
                        _Found(Violation(ViolationCode.VALUE_OUT_OF_RANGE, f"{where}.value"), fixable=above_only)
                    )
        if value.get("save") is True and action not in exempt_actions and status not in exempt_statuses:
            scope = _item_scope(ctx, out) if scope is None else scope
            if item not in scope:
                found.append(_Found(Violation(ViolationCode.OUT_OF_CURRENT_ITEM, f"{where}.key")))
    targets = as_list(out.get("targets"))
    with_targets = action in {a.value for a in rules.actions_with_targets} and targets is not None
    if with_targets and targets is not None:
        named = {t for t in targets if isinstance(t, str)}
        if not named <= keys or len(named) != len(targets):
            found.append(_Found(Violation(ViolationCode.TARGET_NOT_IN_VALUES, "targets")))
    next_item = as_str(out.get("next_item"))
    if next_item is not None:
        if not ctx.flow.knows(next_item):
            found.append(_Found(Violation(ViolationCode.UNKNOWN_ITEM, "next_item"), fixable=True))
        expected = expected_next_item(action, out, ctx)
        if expected is not None and expected != next_item:
            found.append(_Found(Violation(ViolationCode.NEXT_ITEM_MISMATCH, "next_item"), fixable=True))
    return found


def find_violations(raw: str, ctx: GuardContext) -> tuple[Violation, ...]:
    """고쳐 쓰기 전 모델 출력(JSON 글자)의 위반 전부(코드와 위치). 평가의 의미 위반율이 이것으로 센다."""
    return tuple(found.violation for found in _all_found(raw, ctx)[1])


def _all_found(raw: str, ctx: GuardContext) -> tuple[Mapping[str, object] | None, list[_Found]]:
    out = _parse(raw)
    if out is None:
        return None, [_Found(Violation(ViolationCode.OUTPUT_SCHEMA, "$"))]
    return out, _schema_found(raw, out) + _semantic_found(out, ctx)


# 왜 이 값: 횟수가 기간의 날수를 넘으면 한 번도 거르지 않고 마셔도 불가능하다(COUNT_EXCEEDS_DAYS, D115 R2).
# 달력이 정하는 가장 긴 길이(주 7일, 달 31일, 해 366일)를 써서 가능한 답을 되묻지 않게 한다. 정본은 데이터셋
# 정규화기이고
# 이 저장소에 없어 측정하지 못했다(final·finaltest 정답에서 받아들인 최대 횟수: 주 7, 월 30, 년 15 — 위반 0). 변경 요청
# model-runtime-002
_DAYS_IN_PERIOD = {"week": 7, "month": 31, "year": 366}


def _blank(key: object) -> dict[str, object]:
    """데이터셋 정답 모양의 '다시 물을 칸': 값 없음, 정확도 없음, 불분명, 저장 안 함(U32)."""
    return {"key": key, "value": None, "precision": "unspecified", "status": "UNCLEAR", "save": False}


def _slot_of(value: Mapping[str, object]) -> tuple[str, str, str] | None:
    return try_parse_slot(value.get("key"))


def _rewrite(
    out: Mapping[str, object], found: list[_Found], ctx: GuardContext
) -> tuple[dict[str, object], list[Rewrite]]:
    """D115 고쳐 쓰기. 최댓값 초과(OUT_OF_RANGE), 횟수 > 날수(R2), 다음 문항 채우기 순서로 적용한다."""
    result: dict[str, object] = dict(out)
    kinds: list[Rewrite] = []
    values = [dict(m) for raw in (as_list(result.get("values")) or []) if (m := as_map(raw)) is not None]
    over = {
        int(f.violation.path.removeprefix("values[").split("]")[0])
        for f in found
        if f.violation.code is ViolationCode.VALUE_OUT_OF_RANGE and f.fixable
    }
    if over:
        values = [_blank(v["key"]) if index in over else v for index, v in enumerate(values)]
        targets = [str(values[index]["key"]) for index in sorted(over)]
        result.update(values=values, action="REASK", reason="OUT_OF_RANGE", targets=targets)
        result.pop("note", None)
        kinds.append(Rewrite.OUT_OF_RANGE)
    freq = next((v for v in values if _slot_of(v) == ("Q7", "", "frequency") and v.get("save") is True), None)
    unit_value = next((v for v in values if _slot_of(v) == ("Q7", "", "unit") and v.get("save") is True), None)
    unit = as_str(unit_value.get("value")) if unit_value else None
    if unit is None:
        entry = as_map(ctx.state.get("Q7.unit"))
        unit = as_str(entry.get("value")) if entry else None
    count = freq.get("value") if freq else None
    if (
        isinstance(count, int | float)
        and not isinstance(count, bool)
        and unit in _DAYS_IN_PERIOD
        and count > _DAYS_IN_PERIOD[unit]
    ):
        q7 = {("Q7", "", "does_not_drink"), ("Q7", "", "frequency"), ("Q7", "", "unit")}
        others = [v for v in values if _slot_of(v) not in q7]
        drinks = {"key": "Q7.does_not_drink", "value": False, "precision": "exact", "status": "ANSWERED", "save": True}
        values = [drinks, _blank("Q7.frequency"), _blank("Q7.unit"), *others]
        result.update(values=values, action="REASK", reason="COUNT_EXCEEDS_DAYS", targets=["Q7.frequency", "Q7.unit"])
        result.pop("note", None)
        kinds.append(Rewrite.COUNT_EXCEEDS_DAYS)
    expected = expected_next_item(as_str(result.get("action")) or "", result, ctx)
    if expected is not None and expected != result.get("next_item"):
        result["next_item"] = expected
        kinds.append(Rewrite.NEXT_ITEM_FILLED)
    return result, kinds


def check_extraction_output(raw: str, ctx: GuardContext) -> GuardOutcome:
    """모델 출력(JSON 글자)을 검증한다. 검증된 출력 또는 출력 불가를 낸다.

    1. 합격 조건 위반을 모두 센다(고쳐 쓰기 전).
    2. D115 로 해소되지 않는 위반이 있으면 출력 불가. 값을 지어내지 않는다(D74).
    3. 해소되는 것(다음 문항 채우기, 최댓값 초과, R2)은 고쳐 쓴다. 고친 출력이 다시 위반 0 이어야 낸다.
    """
    out, found = _all_found(raw, ctx)
    violations = tuple(f.violation for f in found)
    if out is None or any(not f.fixable for f in found):
        return GuardOutcome(None, violations)
    rewritten, kinds = _rewrite(out, found, ctx)
    if found or kinds:  # 왜 found 도: 해소되는 위반이 있었는데 채우지 못했으면(순서표에 없는 문항) 그대로 내지 않는다
        again = _schema_found(json.dumps(rewritten), rewritten) + _semantic_found(rewritten, ctx)
        if again:
            return GuardOutcome(None, violations)
    return GuardOutcome(rewritten, violations, tuple(kinds))
