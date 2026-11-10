"""package_publish 도구: 문진 참조 DB 에서 순서표 만들기, 입력이 어긋나면 0 이 아닌 종료 코드."""

import json
import sqlite3
from pathlib import Path

import pytest

from model_runtime.publish import main, question_bank_from_reference_db, read_rows


def reference_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE question_items (item_id TEXT, sequence_no INTEGER);
        CREATE TABLE question_fields (field_id TEXT, item_id TEXT, field_name TEXT, data_type TEXT, unit TEXT,
                                      constraints_json TEXT, repeat_keys_json TEXT);
        CREATE TABLE field_options (field_id TEXT, option_code TEXT, label TEXT);
        INSERT INTO question_items VALUES ('Q4', 1), ('Q4_1', 2), ('Q3', 3);
        INSERT INTO question_fields VALUES ('Q4.answer', 'Q4', 'answer', 'boolean', NULL, '{}', '[""]');
        INSERT INTO question_fields VALUES ('Q4_1.status', 'Q4_1', 'status', 'option', NULL, '{}', '[""]');
        INSERT INTO question_fields VALUES ('Q3.days', 'Q3', 'days', 'integer', 'day/week',
                                           '{"maximum":7,"minimum":0}', '["a","b",""]');
        INSERT INTO field_options VALUES ('Q4_1.status', 'current', '현재 피움'), ('Q4_1.status', 'former', '과거');
        """
    )
    conn.commit()
    conn.close()
    return path


def test_question_bank_has_skip_branch_default_path_and_field_specs(tmp_path: Path) -> None:
    bank = question_bank_from_reference_db(reference_db(tmp_path / "ref.sqlite3"))
    assert bank["flow"]["start_item"] == "Q4"
    rules = {rule["item_id"]: rule["branches"] for rule in bank["flow"]["rules"]}
    assert rules["Q4"] == [
        {"when": {"slot": "Q4.answer", "operator": "EQ", "value": False}, "next_item": "Q5"},
        {"next_item": "Q4_1"},
    ]
    assert rules["Q3"] == [{"next_item": "END"}]
    specs = {(s["item_id"], s["field_name"]): s for s in bank["fields"]}
    assert specs[("Q3", "days")] == {
        "item_id": "Q3",
        "field_name": "days",
        "data_type": "integer",
        "unit": "day/week",
        "maximum": 7,
        "minimum": 0,
        "repeat_keys": ["a", "b"],
    }  # 빈 반복 키는 계약 RepeatKey 가 받지 않아 뺀다
    assert specs[("Q4_1", "status")]["options"][0] == {"option_code": "current", "label": "현재 피움"}


def test_question_bank_command_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "bank.json"
    assert (
        main(["question-bank", "--reference-db", str(reference_db(tmp_path / "ref.sqlite3")), "--out", str(out)]) == 0
    )
    assert json.loads(out.read_text(encoding="utf-8"))["flow"]["start_item"] == "Q4"


def test_read_rows_applies_limit(tmp_path: Path) -> None:
    lines = [
        json.dumps(
            {
                "messages": [
                    {"role": "system", "content": "s"},
                    {"role": "user", "content": json.dumps({"n": n})},
                    {"role": "assistant", "content": "a"},
                ]
            }
        )
        for n in range(5)
    ]
    path = tmp_path / "rows.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert [row[0]["n"] for row in read_rows(path, 3)] == [0, 1, 2] and len(read_rows(path, None)) == 5


def test_publish_with_a_folder_that_is_not_an_adapter_fails_with_nonzero_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from scenario.world import world

    with world(tmp_path) as w:
        root = tmp_path / "bad"
        (root / "a").mkdir(parents=True)
        (root / "b").mkdir()
        for name in ("p.txt", "bank.json", "e.jsonl"):
            (root / name).write_text("{}", encoding="utf-8")
        code = main(
            [
                "publish",
                "--adapter-a",
                str(root / "a"),
                "--adapter-b",
                str(root / "b"),
                "--system-prompt-a",
                str(root / "p.txt"),
                "--system-prompt-b",
                str(root / "p.txt"),
                "--question-bank",
                str(root / "bank.json"),
                "--eval-a",
                str(root / "e.jsonl"),
                "--eval-b",
                str(root / "e.jsonl"),
                "--engine-url",
                w.engine_url,
                "--registry-url",
                w.registry_url,
                "--repository",
                "x/y",
                "--credentials-file",
                str(tmp_path / "publisher.credentials"),
                "--base-model",
                "Qwen/Qwen3-8B",
                "--dataset-version-id",
                "3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90",
                "--training-run-a",
                "3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90",
                "--training-run-b",
                "3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90",
                "--runtime-contract-version",
                "1",
                "--workdir",
                str(root / "work"),
            ]
        )
    assert code == 1 and "게시 실패" in capsys.readouterr().err
