# pyright: basic
# ruff: noqa
"""데이터셋 정본 `contracts/inputs/taxonomy.py` 의 참조 원천 문항 표(REF_SOURCE)를 글자 그대로 옮긴 파일.

LoRA-A 입력의 state 에 넣을 문항(지금 문항, 직전에 물은 문항, 참조 원천 문항)을 고르는 데 쓴다(IO_SPEC.md 2.1, SQL.md 7.1).
정본과 같은지는 `tests/contract/test_phrases_match_labels.py` 가 정본 파일을 직접 읽어 소스까지 대조한다.
"""

# fmt: off
# 이전 정보 참조(P07): 문진표에서 먼저 묻는 문항 중 칸 구조가 같은 문항만 참조 원천으로 둔다(2026-10-11 확정).
# 예: Q9_2 "고강도 할 때랑 똑같이 해요" -> Q8_2 저장 값, Q7_2 "평소랑 같아요" -> Q7_1 저장 값.
# 참조한 값은 LoRA-A 입력의 relevant_state에만 넣는다. 원천이 없는 문항(Q1.D01, Q3 등)에는 P07을 배정하지 않는다.
REF_SOURCE = {
    **{f"Q1.D{i:02d}": f"Q1.D{i - 1:02d}" for i in range(2, 12)},
    **{f"Q2.D{i:02d}": f"Q2.D{i - 1:02d}" for i in range(2, 6)},
    "Q5": "Q4", "Q6": "Q5", "Q5_1": "Q4_1", "Q7_2": "Q7_1",
    "Q9_1": "Q8_1", "Q10": "Q9_1", "Q9_2": "Q8_2",
}
# fmt: on
