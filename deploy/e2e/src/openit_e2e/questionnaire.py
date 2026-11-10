"""문항 세트(문진표 한 벌)를 데이터셋 정본에서 만든다.

정본에 문항 은행 원본(DB 파일 questionnaire_reference.sqlite3)은 이 리포에 없다. 그 DB 의 참조 데이터를 읽기 전용으로 옮겨 적은 문서가
`contracts/inputs/SQL.md` 5.1(문항), 5.2(칸), 5.3(선택지)이다. 이 모듈이 그 표를 읽어 계약의 QuestionSetContent(survey-service 에 올리는 것)와
model-runtime 게시 도구의 문항 은행(순서표·칸 규격)을 만든다. 같은 입력이면 같은 출력이다.

생성 규칙(ADR 0025)
1. 문항: 5.1 의 표 순서가 문항 순서다(31개). 질문 문장은 '질문 원문'이고, '대상'이 있는 문항(Q1.D01~D11, Q2.D01~D05)은 원문의 '다음과 같은 질병'(Q1)·'다음 질환'(Q2)을
   대상 이름(조사를 붙여)으로 바꾼다. 원문이 대상을 가리키는 '다음'이라 대상 없이는 환자에게 무엇을 묻는지 정해지지 않기 때문이다.
2. 칸: 5.2 의 한 줄이 칸 하나다. 칸 식별자 `<문항>.<칸>` 에서 마지막 '.' 앞이 문항, 뒤가 칸 이름이다. 범위(minimum·maximum·exclusive_minimum)와 반복 키(비어 있지 않은 것만)와
   선택지(5.3)를 계약 QuestionFieldSpec 으로 옮긴다.
3. 순서표: 문항 순서의 다음 문항이 기본 경로이고, 건너뛰기 여섯 가지는 데이터셋 정본 `labels.py` 의 `next_after` 와 같다(Q4·Q5·Q6 의 answer 가 거짓이면 Q4_1·Q5_1·Q6_1 을 건너뛰고,
   Q7 의 does_not_drink 가 참이면 Q7_1·Q7_2 를, Q8_1·Q9_1 의 days 가 0 이면 Q8_2·Q9_2 를 건너뛴다). 마지막 문항 다음은 END 다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

QUESTIONNAIRE_ID = "national-health-2026-v1"  # SQL.md 의 문진표 버전 national_health_2026_v1 (계약 QuestionnaireId 는 밑줄·하이픈 허용)
TITLE = "국가건강검진 문진표"
# 왜 1: 계약 RuntimeContractVersion 의 시작 값이고 호환이 깨질 때만 올린다(D79). 모델 패키지를 게시할 때 같은 값을 쓴다
RUNTIME_CONTRACT_VERSION = 1
# labels.py next_after 의 건너뛰기: 문항 -> (칸, 값, 건너뛰어 가는 문항). 계약 FlowRule 의 조건 분기로 옮긴 것
SKIPS: dict[str, tuple[str, Any, str]] = {
    "Q4": ("Q4.answer", False, "Q5"),
    "Q5": ("Q5.answer", False, "Q6"),
    "Q6": ("Q6.answer", False, "Q7"),
    "Q7": ("Q7.does_not_drink", True, "Q8_1"),
    "Q8_1": ("Q8_1.days", 0, "Q9_1"),
    "Q9_1": ("Q9_1.days", 0, "Q10"),
}
END = "END"


def _rows(text: str, heading: str) -> list[list[str]]:
    """SQL.md 에서 `### <heading>` 아래 첫 표의 데이터 줄들(머리글·구분선 제외)."""
    start = text.index(f"### {heading}")
    rows: list[list[str]] = []
    seen_table = False
    for line in text[start:].splitlines()[1:]:
        if line.startswith("|"):
            seen_table = True
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            rows.append(cells)
        elif seen_table:
            break
    return [row for row in rows[2:]]  # 머리글과 구분선


def _hangul_final(text: str) -> str | None:
    """마지막 한글 글자의 받침(없으면 빈 문자열). 한글이 없으면 None."""
    for char in reversed(text):
        if "가" <= char <= "힣":
            return [
                "",
                "ㄱ",
                "ㄲ",
                "ㄳ",
                "ㄴ",
                "ㄵ",
                "ㄶ",
                "ㄷ",
                "ㄹ",
                "ㄺ",
                "ㄻ",
                "ㄼ",
                "ㄽ",
                "ㄾ",
                "ㄿ",
                "ㅀ",
                "ㅁ",
                "ㅂ",
                "ㅄ",
                "ㅅ",
                "ㅆ",
                "ㅇ",
                "ㅈ",
                "ㅊ",
                "ㅋ",
                "ㅌ",
                "ㅍ",
                "ㅎ",
            ][(ord(char) - 0xAC00) % 28]
    return None


def with_particle(name: str, kind: str) -> str:
    """이름에 조사를 붙인다(kind: '으로' 는 으로/로, '을' 은 을/를)."""
    final = _hangul_final(name)
    if final is None:
        raise ValueError(f"조사를 고를 수 없다(한글이 없다): {name}")
    if kind == "으로":
        return name + ("로" if final in ("", "ㄹ") else "으로")
    return name + ("를" if final == "" else "을")


def item_text(original: str, target: str) -> str:
    """질문 문장(생성 규칙 1)."""
    if not target:
        return original
    if "다음과 같은 질병으로" in original:
        return original.replace("다음과 같은 질병으로", with_particle(target, "으로"))
    if "다음 질환을" in original:
        return original.replace("다음 질환을", with_particle(target, "을"))
    raise ValueError(f"대상 '{target}' 을 넣을 자리가 원문에 없다: {original}")


def _constraints(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for part in filter(None, (piece.strip() for piece in text.split(","))):
        name, _, value = part.partition("=")
        number = float(value)
        result[name] = int(number) if number == int(number) else number
    return result


@dataclass(frozen=True)
class Questionnaire:
    items: list[dict[str, Any]]  # 계약 QuestionItem
    flow: dict[str, Any]  # 계약 QuestionFlowTable

    @property
    def item_ids(self) -> list[str]:
        return [item["item_id"] for item in self.items]

    @property
    def fields(self) -> list[dict[str, Any]]:
        return [field for item in self.items for field in item["fields"]]

    def content(self) -> dict[str, Any]:
        """계약 QuestionSetContent."""
        return {"title": TITLE, "bank": {"items": self.items}, "flow": self.flow}

    def upload(self) -> dict[str, Any]:
        """계약 QuestionSetUpload(survey-service 의 uploadQuestionSet 본문)."""
        return {"questionnaire_id": QUESTIONNAIRE_ID, "runtime_contract_version": RUNTIME_CONTRACT_VERSION, "content": self.content()}

    def bank(self) -> dict[str, Any]:
        """model-runtime 의 package-publish 가 읽는 문항 은행(순서표와 칸 규격, 계약 QuestionFlowTable·QuestionFieldSpec)."""
        return {"flow": self.flow, "fields": self.fields}

    def next_item(self, item: str, saved: dict[str, Any]) -> str:
        """item 다음에 물을 문항. saved 는 `<문항>.<칸>` -> 이번 턴에 저장된 값."""
        rule = next(rule for rule in self.flow["rules"] if rule["item_id"] == item)
        for branch in rule["branches"]:
            when = branch.get("when")
            if when is None:
                return str(branch["next_item"])
            if when["slot"] in saved and saved[when["slot"]] == when["value"]:
                return str(branch["next_item"])
        raise ValueError(f"{item} 의 순서표에 기본 경로가 없다")


def build(sql_md: str) -> Questionnaire:
    options: dict[str, list[dict[str, str]]] = {}
    for field_id, code, label in ((r[0], r[1].strip("`"), r[2]) for r in _rows(sql_md, "5.3 선택지 (field_options)")):
        options.setdefault(field_id, []).append({"option_code": code, "label": label})
    items: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    for _order, item_id, _number, _section, target, _period, original in _rows(sql_md, "5.1 문항 (question_items, 순서대로)"):
        item: dict[str, Any] = {"item_id": item_id, "text": item_text(original, target), "fields": []}
        items.append(item)
        index[item_id] = item
    for field_id, data_type, unit, constraints, repeat, _column in _rows(sql_md, "5.2 칸 (question_fields)"):
        item_id, _, name = field_id.rpartition(".")
        spec: dict[str, Any] = {"item_id": item_id, "field_name": name, "data_type": data_type}
        if unit:
            spec["unit"] = unit
        spec.update(_constraints(constraints))
        keys = [
            key.strip() for key in repeat.split(",") if re.fullmatch(r"[a-z]+", key.strip())
        ]  # 빈 키 표기 "(빈 키 '')" 는 키가 없다는 뜻
        if keys:
            spec["repeat_keys"] = keys
        if field_id in options:
            spec["options"] = options[field_id]
        index[item_id]["fields"].append(spec)
    ids = [item["item_id"] for item in items]
    rules: list[dict[str, Any]] = []
    for position, item_id in enumerate(ids):
        following = ids[position + 1] if position + 1 < len(ids) else END
        branches: list[dict[str, Any]] = []
        if item_id in SKIPS:
            slot, value, target_item = SKIPS[item_id]
            branches.append({"when": {"slot": slot, "operator": "EQ", "value": value}, "next_item": target_item})
        branches.append({"next_item": following})
        rules.append({"item_id": item_id, "branches": branches})
    return Questionnaire(items, {"start_item": ids[0], "rules": rules})


def load(sql_md: Path) -> Questionnaire:
    return build(sql_md.read_text(encoding="utf-8"))


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
