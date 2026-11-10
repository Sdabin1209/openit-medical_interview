"""칸 키(`문항.칸`, 술은 `문항[반복키].칸`)와 문항 계열을 읽는 규칙.

정본은 데이터셋 labels.py 의 parse_key 이다(계약 D43).
"""

from __future__ import annotations

import re

_FAMILY_SPLIT = re.compile(r"[_.]")


def parse_slot(key: str) -> tuple[str, str, str]:
    """`Q7_1[soju].amount` -> (`Q7_1`, `soju`, `amount`), `Q1.D01.diagnosed` -> (`Q1.D01`, ``, `diagnosed`).

    왜 마지막 점에서 나누나: 문항 식별자 자체에 점이 있다(Q1.D01). 반복 키가 있으면 `].` 에서 나눈다(labels.py
    parse_key, D43).
    """
    if "[" in key:
        item, rest = key.split("[", 1)
        repeat, field = rest.split("].", 1)
        return item, repeat, field
    item, field = key.rsplit(".", 1)
    return item, "", field


def family_of(item: str) -> str:
    """문항 계열: 문항 식별자에서 첫 `_` 또는 `.` 앞 부분(Q7_1·Q7_2 -> Q7, Q1.D01 -> Q1). 정본은 docs/design.md 4절."""
    return _FAMILY_SPLIT.split(item, maxsplit=1)[0]


def try_parse_slot(key: object) -> tuple[str, str, str] | None:
    """parse_slot 인데 모양이 틀린 키에는 None 을 준다(검증 전의 모델 출력을 읽을 때)."""
    if not isinstance(key, str):
        return None
    try:
        return parse_slot(key)
    except ValueError:
        return None
