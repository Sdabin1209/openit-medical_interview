"""문진 참조 DB(데이터셋 db/questionnaire_reference.sqlite3, SQL.md 5절)에서 시험용 순서표와 칸 규격 JSON 을 만든다.

사용: python build_question_bank.py <참조 DB 경로> <출력 JSON 경로>
왜 JSON 으로 두나: 시험이 학습 서버 파일 없이도 도는 고정 문항 세트(합성 시험용)가 필요하다.
건너뛰기 분기는 데이터셋 정본 labels.py 의 next_after 가 정한 규칙(Q4·Q5·Q6 아니요, Q7 안 마심, Q8_1·Q9_1 0일)을 옮긴
것이다.
"""

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

SKIPS: dict[str, tuple[str, Any, str]] = {
    # 문항: (조건 칸, 같다고 볼 값, 조건이 맞을 때 가는 문항)
    "Q4": ("Q4.answer", False, "Q5"),
    "Q5": ("Q5.answer", False, "Q6"),
    "Q6": ("Q6.answer", False, "Q7"),
    "Q7": ("Q7.does_not_drink", True, "Q8_1"),
    "Q8_1": ("Q8_1.days", 0, "Q9_1"),
    "Q9_1": ("Q9_1.days", 0, "Q10"),
}


def build(db_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    items = [row[0] for row in conn.execute("SELECT item_id FROM question_items ORDER BY sequence_no")]
    rules: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        following = items[index + 1] if index + 1 < len(items) else "END"
        branches: list[dict[str, Any]] = []
        if item in SKIPS:
            slot, value, target = SKIPS[item]
            branches.append({"when": {"slot": slot, "operator": "EQ", "value": value}, "next_item": target})
        branches.append({"next_item": following})
        rules.append({"item_id": item, "branches": branches})
    options: dict[str, list[dict[str, str]]] = {}
    for field_id, code, label in conn.execute("SELECT field_id, option_code, label FROM field_options"):
        options.setdefault(field_id, []).append({"option_code": code, "label": label})
    fields: list[dict[str, Any]] = []
    query = (
        "SELECT field_id, item_id, field_name, data_type, unit, constraints_json, repeat_keys_json FROM question_fields"
    )
    for field_id, item, name, data_type, unit, constraints, repeat in conn.execute(query):
        spec: dict[str, Any] = {"item_id": item, "field_name": name, "data_type": data_type}
        if unit:
            spec["unit"] = unit
        for key, value in json.loads(constraints).items():
            spec[key] = value
        # 왜 빈 키를 뺀다: 계약 RepeatKey 는 소문자 글자만 받고(빈 글자 없음), SQL.md 5.2 도 반복 키를 술 종류 다섯으로 적는다
        keys = [key for key in json.loads(repeat) if key]
        if keys:
            spec["repeat_keys"] = keys
        if field_id in options:
            spec["options"] = options[field_id]
        fields.append(spec)
    return {"flow": {"start_item": items[0], "rules": rules}, "fields": fields}


if __name__ == "__main__":
    Path(sys.argv[2]).write_text(
        json.dumps(build(Path(sys.argv[1])), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
