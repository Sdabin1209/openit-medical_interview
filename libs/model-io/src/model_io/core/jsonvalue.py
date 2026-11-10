"""JSON 값의 타입과 좁히기 도구. 모델 출력과 요청 본문은 구조를 믿을 수 없는 JSON 이라 먼저 모양을 좁혀 읽는다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None
"""JSON(RFC 8259)이 담을 수 있는 값."""


def as_map(value: object) -> Mapping[str, object] | None:
    """객체(키가 글자인 표)면 그대로, 아니면 None."""
    if isinstance(value, Mapping):
        mapping: Mapping[object, object] = value  # pyright: ignore[reportUnknownVariableType]
        if all(isinstance(key, str) for key in mapping):
            return {str(key): item for key, item in mapping.items()}
    return None


def as_list(value: object) -> Sequence[object] | None:
    """배열이면 그대로, 아니면 None(글자는 배열로 보지 않는다)."""
    if isinstance(value, list):
        items: list[object] = value  # pyright: ignore[reportUnknownVariableType]
        return items
    return None


def as_str(value: object) -> str | None:
    """글자면 그대로, 아니면 None."""
    return value if isinstance(value, str) else None


def is_number(value: object) -> bool:
    """수인가(JSON 에서 참·거짓은 수가 아니다)."""
    return isinstance(value, int | float) and not isinstance(value, bool)
