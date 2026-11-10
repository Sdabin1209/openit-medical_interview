"""출력 검증: 위반 코드 10개마다 위반 사례, 고쳐 쓰기(D115), 출력 불가."""

import json
from collections.abc import Mapping

import pytest

from helpers import context, gap, value
from model_io import DISABLED_RULES, GuardContext, Rewrite, check_extraction_output, find_violations
from model_io.contract.models import ViolationCode


def out(
    action: str = "NEXT", next_item: str = "Q1.D02", values: list[dict[str, object]] | None = None, **extra: object
) -> str:
    body: dict[str, object] = {"action": action, "next_item": next_item, "values": values if values is not None else []}
    body.update(extra)
    return json.dumps(body, ensure_ascii=False)


def codes(raw: str, ctx: GuardContext) -> set[ViolationCode]:
    return {violation.code for violation in find_violations(raw, ctx)}


GOOD = out(values=[value("Q1.D01.diagnosed", True), value("Q1.D01.on_medication", False)])


def test_valid_output_passes_unchanged() -> None:
    result = check_extraction_output(GOOD, context("Q1.D01"))
    assert result.valid and result.violations == () and result.rewrites == ()
    assert result.output == json.loads(GOOD)


@pytest.mark.parametrize("raw", ["", "[]", "not json", '{"action": NaN}', '"x"'])
def test_non_object_is_output_schema(raw: str) -> None:
    result = check_extraction_output(raw, context("Q1.D01"))
    assert not result.valid and {v.code for v in result.violations} == {ViolationCode.OUTPUT_SCHEMA}


@pytest.mark.parametrize(
    "raw",
    [
        out(action="JUMP"),  # 모르는 action
        out(extra_key=1),  # 모르는 칸
        out(reason="MISSING"),  # NEXT 에 reason
        out(action="REASK", targets=["Q1.D01.diagnosed"], values=[gap("Q1.D01.diagnosed")]),  # REASK 에 reason 없음
        out(
            action="REDIRECT", next_item="Q1.D01", reason="OFF_TOPIC", targets=["Q1.D01.diagnosed"]
        ),  # REDIRECT 에 targets
        out(action="REDIRECT", next_item="Q1.D01", reason="OUT_OF_SCHEMA"),  # OUT_OF_SCHEMA 에 note 없음
        out(action="REDIRECT", next_item="Q1.D01", reason="OFF_TOPIC", note="잡담"),  # note 는 OUT_OF_SCHEMA 에서만
        out(
            values=[{**value("Q1.D01.diagnosed", True), "precision": "unspecified"}]
        ),  # 값이 있는데 precision unspecified
        out(values=[{**gap("Q1.D01.diagnosed"), "precision": "exact"}]),  # 값이 없는데 precision exact
        out(values=[{**value("Q1.D01.diagnosed", True), "save": "yes"}]),  # save 가 참·거짓이 아님
        out(values=[{"key": "Q1.D01.diagnosed", "value": True}]),  # 칸 빠짐
    ],
)
def test_output_schema_violations(raw: str) -> None:
    assert ViolationCode.OUTPUT_SCHEMA in codes(raw, context("Q1.D01"))
    assert not check_extraction_output(raw, context("Q1.D01")).valid


def test_save_rule_status_and_save_must_pair() -> None:
    wrong_save = out(values=[value("Q1.D01.diagnosed", True, save=False)])
    assert codes(wrong_save, context("Q1.D01")) == {ViolationCode.SAVE_RULE}
    missing_with_save = out(values=[{**gap("Q1.D01.diagnosed"), "save": True}])
    assert ViolationCode.SAVE_RULE in codes(missing_with_save, context("Q1.D01"))


def test_save_rule_null_value_must_match_status() -> None:
    answered_null = out(values=[{**value("Q1.D01.diagnosed", True), "value": None, "precision": "unspecified"}])
    assert ViolationCode.SAVE_RULE in codes(answered_null, context("Q1.D01"))
    unknown_with_value = out(values=[value("Q1.D01.diagnosed", True, status="UNKNOWN", save=False)])
    assert ViolationCode.SAVE_RULE in codes(unknown_with_value, context("Q1.D01"))


def test_target_must_be_in_values() -> None:
    raw = out(
        action="REASK",
        next_item="Q1.D01",
        reason="MISSING",
        targets=["Q1.D01.on_medication"],
        values=[value("Q1.D01.diagnosed", True)],
    )
    assert codes(raw, context("Q1.D01")) == {ViolationCode.TARGET_NOT_IN_VALUES}
    assert not check_extraction_output(raw, context("Q1.D01")).valid


def test_next_item_mismatch_is_filled_from_the_flow() -> None:
    raw = out(next_item="Q1.D05", values=[value("Q1.D01.diagnosed", True), value("Q1.D01.on_medication", True)])
    result = check_extraction_output(raw, context("Q1.D01"))
    assert {v.code for v in result.violations} == {ViolationCode.NEXT_ITEM_MISMATCH}
    assert result.output is not None and result.output["next_item"] == "Q1.D02"
    assert result.rewrites == (Rewrite.NEXT_ITEM_FILLED,)


def test_unknown_next_item_is_counted_then_filled() -> None:
    raw = out(next_item="Q99", values=[value("Q1.D01.diagnosed", True), value("Q1.D01.on_medication", True)])
    result = check_extraction_output(raw, context("Q1.D01"))
    assert {v.code for v in result.violations} == {ViolationCode.UNKNOWN_ITEM, ViolationCode.NEXT_ITEM_MISMATCH}
    assert result.output is not None and result.output["next_item"] == "Q1.D02"


def test_skip_rules_are_applied_to_next_item() -> None:
    no_smoking = out(next_item="Q5", values=[value("Q4.answer", False)])
    assert check_extraction_output(no_smoking, context("Q4")).output is not None
    wrong = out(next_item="Q4_1", values=[value("Q4.answer", False)])
    assert ViolationCode.NEXT_ITEM_MISMATCH in codes(wrong, context("Q4"))


def test_everything_stored_in_one_turn_skips_later_items() -> None:
    values = [value("Q8_1.days", 0), value("Q9_1.days", 0), value("Q10.days", 0)]
    assert check_extraction_output(out(next_item="END", values=values), context("Q8_1")).valid


def test_redirect_and_reask_next_items() -> None:
    redirect = out(action="REDIRECT", next_item="Q8_2", reason="ASK_PURPOSE")
    assert check_extraction_output(redirect, context("Q8_2")).valid
    reask = out(
        action="REASK",
        next_item="Q7_1",
        reason="MISSING",
        targets=["Q7_1[soju].amount"],
        values=[value("Q7_1[soju].unit", "bottle"), gap("Q7_1[soju].amount")],
    )
    assert check_extraction_output(reask, context("Q7_1")).valid


def test_unknown_item_in_key_is_unavailable() -> None:
    raw = out(values=[value("Q99.answer", True)])
    result = check_extraction_output(raw, context("Q1.D01"))
    assert ViolationCode.UNKNOWN_ITEM in {v.code for v in result.violations} and not result.valid


def test_unknown_slot_and_repeat_key() -> None:
    assert ViolationCode.UNKNOWN_SLOT in codes(out(values=[value("Q1.D01.nope", True)]), context("Q1.D01"))
    bad_repeat = out(action="NEXT", next_item="Q7_2", values=[value("Q7_1[gin].amount", 1)])
    assert ViolationCode.UNKNOWN_SLOT in codes(bad_repeat, context("Q7_1"))
    no_repeat_slot = out(next_item="Q8_1", values=[value("Q3.answer[x]", "yes")])
    assert ViolationCode.OUTPUT_SCHEMA in codes(no_repeat_slot, context("Q3"))
    repeat_on_plain_slot = out(next_item="Q4", values=[value("Q3[soju].answer", "yes")])
    assert ViolationCode.UNKNOWN_SLOT in codes(repeat_on_plain_slot, context("Q3"))


def test_empty_repeat_key_is_only_for_values_that_are_not_saved() -> None:
    """술 종류를 모르는 재질문의 칸은 키에 [술 종류]가 없고 저장하지 않는다. 저장하는 값에 키가 없으면 위반이다."""
    reask = out(
        action="REASK",
        next_item="Q7_1",
        reason="MISSING",
        targets=["Q7_1.amount"],
        values=[gap("Q7_1.amount")],
    )
    assert check_extraction_output(reask, context("Q7_1")).valid
    saved_without_key = out(next_item="Q7_2", values=[value("Q7_1.amount", 2)])
    assert ViolationCode.UNKNOWN_SLOT in codes(saved_without_key, context("Q7_1"))


@pytest.mark.parametrize(
    ("key", "wrong"),
    [("Q1.D01.diagnosed", "yes"), ("Q8_1.days", 2.5), ("Q8_1.days", True), ("Q3.answer", 3), ("Q4.answer", 1)],
)
def test_value_type_mismatch(key: str, wrong: object) -> None:
    result = check_extraction_output(
        out(values=[value(key, wrong)]), context(key.split(".")[0] if "D" not in key else "Q1.D01")
    )
    assert ViolationCode.VALUE_TYPE_MISMATCH in {v.code for v in result.violations} and not result.valid


def test_value_not_in_options() -> None:
    raw = out(next_item="Q4", values=[value("Q3.answer", "maybe")])
    assert codes(raw, context("Q3")) >= {ViolationCode.VALUE_NOT_IN_OPTIONS}
    assert not check_extraction_output(raw, context("Q3")).valid
    assert check_extraction_output(out(next_item="Q4", values=[value("Q3.answer", "yes")]), context("Q3")).valid


def test_below_minimum_is_unavailable_not_rewritten() -> None:
    raw = out(next_item="Q8_2", values=[value("Q8_1.days", -1)])
    result = check_extraction_output(raw, context("Q8_1"))
    assert {v.code for v in result.violations} == {ViolationCode.VALUE_OUT_OF_RANGE} and not result.valid


def test_exclusive_minimum_zero_frequency_is_unavailable() -> None:
    raw = out(
        next_item="Q7_1", values=[value("Q7.does_not_drink", False), value("Q7.frequency", 0), value("Q7.unit", "week")]
    )
    assert not check_extraction_output(raw, context("Q7")).valid


def test_above_maximum_is_rewritten_to_reask_out_of_range() -> None:
    raw = out(next_item="Q8_2", values=[value("Q8_1.days", 14)])
    result = check_extraction_output(raw, context("Q8_1"))
    assert {v.code for v in result.violations} == {ViolationCode.VALUE_OUT_OF_RANGE}
    assert result.rewrites == (Rewrite.OUT_OF_RANGE, Rewrite.NEXT_ITEM_FILLED)
    assert result.output == {
        "action": "REASK",
        "reason": "OUT_OF_RANGE",
        "targets": ["Q8_1.days"],
        "next_item": "Q8_1",
        "values": [gap("Q8_1.days", "UNCLEAR")],
    }


def test_count_exceeds_days_is_rewritten() -> None:
    raw = out(
        next_item="Q7_1",
        values=[value("Q7.does_not_drink", False), value("Q7.frequency", 10), value("Q7.unit", "week")],
    )
    result = check_extraction_output(raw, context("Q7"))
    assert result.violations == () and result.rewrites == (Rewrite.COUNT_EXCEEDS_DAYS, Rewrite.NEXT_ITEM_FILLED)
    assert result.output == {
        "action": "REASK",
        "reason": "COUNT_EXCEEDS_DAYS",
        "targets": ["Q7.frequency", "Q7.unit"],
        "next_item": "Q7",
        "values": [value("Q7.does_not_drink", False), gap("Q7.frequency", "UNCLEAR"), gap("Q7.unit", "UNCLEAR")],
    }


def test_count_within_days_is_untouched_and_state_unit_is_used() -> None:
    ok = out(
        next_item="Q7_1", values=[value("Q7.does_not_drink", False), value("Q7.frequency", 7), value("Q7.unit", "week")]
    )
    assert check_extraction_output(ok, context("Q7")).rewrites == ()
    state: Mapping[str, object] = {"Q7.unit": {"value": "week", "status": "ANSWERED"}}
    only_freq = out(next_item="Q7_1", values=[value("Q7.does_not_drink", False), value("Q7.frequency", 8)])
    assert Rewrite.COUNT_EXCEEDS_DAYS in check_extraction_output(only_freq, context("Q7", state)).rewrites


def test_out_of_current_item() -> None:
    far = out(next_item="Q1.D02", values=[value("Q2.D05.family_history", True)])
    result = check_extraction_output(far, context("Q1.D01"))
    assert ViolationCode.OUT_OF_CURRENT_ITEM in {v.code for v in result.violations} and not result.valid


def test_current_item_scopes_and_correction_exemption() -> None:
    family = out(
        next_item="Q1.D03",
        values=[value("Q1.D01.diagnosed", True), value("Q1.D02.diagnosed", True), value("Q1.D02.on_medication", True)],
    )
    assert check_extraction_output(family, context("Q1.D01")).valid  # 같은 계열
    correction = out(
        action="CORRECT", next_item="Q3", values=[value("Q2.D05.family_history", True, status="CORRECTION")]
    )
    assert check_extraction_output(correction, context("Q2.D05")).valid
    correction_far = out(
        action="CORRECT", next_item="Q4", values=[value("Q1.D01.diagnosed", True, status="CORRECTION")]
    )
    assert check_extraction_output(correction_far, context("Q3")).valid  # 정정은 예외
    skipped_range = out(next_item="Q5", values=[value("Q4.answer", False)])
    assert check_extraction_output(skipped_range, context("Q4")).valid


def test_rewrite_that_cannot_be_checked_again_is_unavailable() -> None:
    raw = out(next_item="Q99", values=[])
    assert not check_extraction_output(raw, context("Nope")).valid


def test_violations_are_counted_before_rewrite_even_when_output_is_unavailable() -> None:
    raw = out(next_item="Q99", values=[value("Q1.D01.nope", True)])
    result = check_extraction_output(raw, context("Q1.D01"))
    assert not result.valid
    assert {v.code for v in result.violations} >= {ViolationCode.UNKNOWN_SLOT, ViolationCode.UNKNOWN_ITEM}


# ---- 켜지 않은 규칙(R1, R3)과 R2 날수 ------------------------------------------------------


def test_r1_and_r3_are_disabled_with_name_and_reason() -> None:
    """정본에 규칙 데이터가 없어 켜지 않았다(DC-11). 켜는 일은 이 시험을 바꾸는 일이라 눈에 띈다."""
    assert [rule.name for rule in DISABLED_RULES] == ["R1", "R3"]
    for rule in DISABLED_RULES:
        assert rule.what and "정본 없음" in rule.reason and "DC-11" in rule.reason


def test_the_guard_has_exactly_the_three_rewrites_and_none_of_them_is_r1_or_r3() -> None:
    assert {kind.value for kind in Rewrite} == {"NEXT_ITEM_FILLED", "OUT_OF_RANGE", "COUNT_EXCEEDS_DAYS"}


def test_r1_is_not_applied_a_count_with_does_not_drink_true_is_left_as_the_model_wrote_it() -> None:
    raw = out(
        next_item="Q7_1",
        values=[value("Q7.does_not_drink", True), value("Q7.frequency", 3), value("Q7.unit", "week")],
    )
    result = check_extraction_output(raw, context("Q7"))
    assert Rewrite.COUNT_EXCEEDS_DAYS not in result.rewrites
    assert result.output is None or {v["key"]: v["value"] for v in result.output["values"]}["Q7.does_not_drink"] is True  # type: ignore[index]


def test_r3_is_not_applied_a_max_below_usual_is_not_turned_into_a_confirm() -> None:
    """최대 음주량(1잔)이 평소 음주량(5잔)보다 적어도 검증기는 CONFIRM 으로 고치지 않는다(환산표가 정본에 없다)."""
    raw = out(
        next_item="Q7_2",
        values=[value("Q7_1[soju].unit", "glass"), value("Q7_1[soju].amount", 5), value("Q7_2[soju].amount", 1)],
    )
    result = check_extraction_output(raw, context("Q7_1"))
    assert all(kind is not Rewrite.COUNT_EXCEEDS_DAYS for kind in result.rewrites)
    assert result.output is None or result.output.get("reason") != "CONFLICT_MAX_BELOW_USUAL"


@pytest.mark.parametrize(("unit", "longest", "over"), [("week", 7, 8), ("month", 31, 32), ("year", 366, 367)])
def test_r2_uses_the_longest_calendar_values(unit: str, longest: int, over: int) -> None:
    """주 7일, 달 31일, 해 366일: 가장 긴 값까지는 가능한 답이라 되묻지 않고, 넘으면 되묻는다."""

    def checked(count: int) -> tuple[Rewrite, ...]:
        raw = out(
            next_item="Q7_1",
            values=[value("Q7.does_not_drink", False), value("Q7.frequency", count), value("Q7.unit", unit)],
        )
        return check_extraction_output(raw, context("Q7")).rewrites

    assert Rewrite.COUNT_EXCEEDS_DAYS not in checked(longest)
    assert Rewrite.COUNT_EXCEEDS_DAYS in checked(over)
