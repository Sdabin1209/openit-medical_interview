"""옮긴 사람 말 표와 문장 규칙(core/labels_port.py)이 데이터셋 정본(contracts/inputs/labels.py)과 글자까지 같은지 본다.

정본 파일을 직접 읽어 같은 이름의 함수·표의 소스를 견준다. 정본이 바뀌면 이 시험이 먼저 깨진다.
"""

import ast
from pathlib import Path

import model_io.core.labels_port as port

CANON = Path(__file__).resolve().parents[4] / "contracts" / "inputs" / "labels.py"


def _segments(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    result: dict[str, str] = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef):
            result[node.name] = ast.get_source_segment(text, node) or ""
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            result[node.targets[0].id] = ast.get_source_segment(text, node) or ""
    return result


def test_every_ported_definition_equals_the_canonical_source() -> None:
    canon, ported = _segments(CANON), _segments(Path(port.__file__))
    skipped = {"END", "FIRST_ITEM"}  # 옮긴 파일 머리에서 다시 선언한 상수
    different = [name for name, source in ported.items() if name not in skipped and canon.get(name) != source]
    assert different == []
    assert len(ported) - len(skipped) > 25, "표와 함수를 모두 옮겼다"


def test_the_two_constants_have_the_canonical_values() -> None:
    assert (port.END, port.FIRST_ITEM) == ("END", "Q1.D01")
    assert 'END = "END"' in CANON.read_text(encoding="utf-8") and 'FIRST_ITEM = "Q1.D01"' in CANON.read_text(
        encoding="utf-8"
    )
