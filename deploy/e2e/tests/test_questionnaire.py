"""문항 세트 생성(SQL.md -> 계약 QuestionSetContent·문항 은행) 시험."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openit_e2e import questionnaire
from openit_e2e.contract import Contract

REPO = Path(__file__).resolve().parents[3]
BANK = questionnaire.load(REPO / "contracts" / "inputs" / "SQL.md")


def test_counts_follow_the_reference_data() -> None:
    assert len(BANK.items) == 31  # SQL.md 5.1 의 문항 31개
    assert len(BANK.fields) == 52  # 5.2 의 칸 52개
    assert BANK.item_ids[0] == "Q1.D01" and BANK.item_ids[-1] == "Q10"
    assert sum(len(field.get("options", [])) for field in BANK.fields) == 23  # 5.3 의 선택지 23개


def test_patient_text_names_the_target_with_the_right_particle() -> None:
    texts = {item["item_id"]: item["text"] for item in BANK.items}
    assert texts["Q1.D01"] == "뇌졸중(중풍)으로 진단을 받았거나, 현재 약물 치료 중이십니까?"  # IO_SPEC.md 5.1 의 예와 같다
    assert texts["Q1.D06"].startswith("폐결핵으로 ")  # 받침 ㄱ
    assert texts["Q1.D09"].startswith("C형간염으로 ")  # 받침 ㅁ
    assert texts["Q2.D03"] == "부모, 형제, 자매 중에 고혈압을 앓았거나 해당 질환으로 사망한 경우가 있으십니까?"
    assert texts["Q3"] == "B형간염 바이러스 보유자입니까?"  # 대상이 없으면 원문 그대로
    assert all(
        "다음" not in text for text in texts.values() if text.startswith(("뇌", "심", "고", "당", "이", "폐", "우", "조", "C", "만", "기"))
    )


def test_particles() -> None:
    assert questionnaire.with_particle("당뇨병", "으로") == "당뇨병으로"
    assert questionnaire.with_particle("우울증", "을") == "우울증을"
    assert questionnaire.with_particle("고혈압(알)", "으로") == "고혈압(알)로"  # 받침 ㄹ 은 '로'
    assert questionnaire.with_particle("감기", "을") == "감기를"
    with pytest.raises(ValueError, match="한글이 없다"):
        questionnaire.with_particle("COPD", "을")


def test_flow_skips_are_the_six_rules_of_next_after() -> None:
    nxt = BANK.next_item
    assert nxt("Q4", {"Q4.answer": False}) == "Q5"  # Q4_1 을 건너뜀
    assert nxt("Q4", {"Q4.answer": True}) == "Q4_1"
    assert nxt("Q6", {"Q6.answer": False}) == "Q7"
    assert nxt("Q7", {"Q7.does_not_drink": True}) == "Q8_1"
    assert nxt("Q7", {}) == "Q7_1"
    assert nxt("Q8_1", {"Q8_1.days": 0}) == "Q9_1"
    assert nxt("Q9_1", {"Q9_1.days": 0}) == "Q10"
    assert nxt("Q9_1", {"Q9_1.days": 3}) == "Q9_2"
    assert nxt("Q10", {"Q10.days": 3}) == "END"
    assert sum(1 for rule in BANK.flow["rules"] if len(rule["branches"]) == 2) == 6


def test_upload_and_bank_satisfy_the_contract() -> None:
    contract = Contract(REPO / "contracts")
    upload = contract.named("QuestionSetUpload")
    assert contract.schema_errors(upload, BANK.upload()) == []
    assert contract.schema_errors(contract.named("QuestionFlowTable"), BANK.bank()["flow"]) == []
    specs = contract.named("QuestionFieldSpecs")
    assert contract.schema_errors(specs, BANK.bank()["fields"]) == []


def test_same_input_gives_same_output() -> None:
    again = questionnaire.load(REPO / "contracts" / "inputs" / "SQL.md")
    assert questionnaire.dumps(again.upload()) == questionnaire.dumps(BANK.upload())


def _normalized(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for field in fields:
        field = dict(field)
        if "options" in field:
            field["options"] = sorted(field["options"], key=lambda option: option["option_code"])
        out.append(field)
    return sorted(out, key=lambda field: (field["item_id"], field["field_name"]))


def test_bank_equals_the_one_made_from_the_reference_db() -> None:
    """정적 일관성: 실제 참조 DB 에서 만든 model-runtime 의 시험 자료(question_bank_v1.json)와 순서표·칸 규격이 같다(선택지 순서만 다를 수 있다)."""
    fixture = REPO / "services" / "model-runtime" / "tests" / "fixtures" / "question_bank_v1.json"
    if not fixture.is_file():
        pytest.skip("model-runtime 의 시험 자료가 없다")
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    assert BANK.bank()["flow"] == expected["flow"]
    assert _normalized(BANK.bank()["fields"]) == _normalized(expected["fields"])
