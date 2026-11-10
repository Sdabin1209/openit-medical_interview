"""요청의 순서표(QuestionFlowTable)와 칸 규격(QuestionFieldSpecs)을 찾아보기 쉬운 모양으로 바꾸고 다음 문항을 계산한다.

입력은 요청이 싣고 온 계약 값(JSON 으로 푼 모양)이다. 계약 값은 낸 쪽이 검증했으므로 여기서 다시 검증하지 않는다(R7).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from model_io.core.jsonvalue import as_list, as_map, as_str, is_number
from model_io.core.slots import try_parse_slot

END = "END"
"""순서표와 LoRA-A 출력이 끝을 가리키는 값(계약 FlowTarget)."""


@dataclass(frozen=True)
class Branch:
    """순서표의 분기 하나. 조건이 없으면 기본 경로다."""

    next_item: str
    slot: tuple[str, str] | None = None  # (문항, 칸 이름). 조건이 없으면 None
    operator: str = ""
    value: object = None


@dataclass(frozen=True)
class FlowIndex:
    """순서표 색인. order 는 기본 경로를 따라 걸은 문항 순서다."""

    order: tuple[str, ...]
    branches: Mapping[str, tuple[Branch, ...]]

    def position(self, item: str) -> int | None:
        """문항의 순서 번호(없으면 None)."""
        try:
            return self.order.index(item)
        except ValueError:
            return None

    def knows(self, target: str) -> bool:
        """순서표에 있는 문항이거나 끝(END)인가."""
        return target == END or target in self.branches


@dataclass(frozen=True)
class FieldSpec:
    """칸 규격 하나(계약 QuestionFieldSpec 에서 필요한 칸만)."""

    data_type: str
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: float | None = None
    repeat_keys: tuple[str, ...] = ("",)
    options: frozenset[str] = frozenset()


@dataclass(frozen=True)
class FieldIndex:
    """칸 규격 색인. (문항, 칸 이름)으로 찾는다."""

    specs: Mapping[tuple[str, str], FieldSpec] = field(default_factory=lambda: dict[tuple[str, str], FieldSpec]())

    def fields_of(self, item: str) -> tuple[str, ...]:
        """문항에 속한 칸 이름들."""
        return tuple(name for (owner, name) in self.specs if owner == item)


def _number(value: object) -> float | None:
    return float(value) if is_number(value) and isinstance(value, int | float) else None


def build_flow_index(flow: Mapping[str, object]) -> FlowIndex:
    """`QuestionFlowTable` 을 색인으로. 순서는 시작 문항에서 기본 경로(조건 없는 분기)를 따라 걷는다.

    왜 기본 경로: 순서표가 문항 번호를 따로 갖지 않고 분기만 가진다. 기본 경로가 문항의 순서다(계약 FlowBranch).
    """
    branches: dict[str, tuple[Branch, ...]] = {}
    for raw_rule in as_list(flow.get("rules")) or []:
        rule = as_map(raw_rule)
        item = as_str(rule.get("item_id")) if rule else None
        if rule is None or item is None:
            continue
        built: list[Branch] = []
        for raw_branch in as_list(rule.get("branches")) or []:
            branch = as_map(raw_branch)
            target = as_str(branch.get("next_item")) if branch else None
            if branch is None or target is None:
                continue
            when = as_map(branch.get("when"))
            slot = try_parse_slot(when.get("slot")) if when else None
            if when is not None and slot is not None:
                built.append(Branch(target, (slot[0], slot[2]), as_str(when.get("operator")) or "", when.get("value")))
            else:
                built.append(Branch(target))
        branches[item] = tuple(built)
    order: list[str] = []
    current = as_str(flow.get("start_item"))
    while current is not None and current != END and current in branches and current not in order:
        order.append(current)
        default = [branch for branch in branches[current] if branch.slot is None]
        current = default[0].next_item if default else None
    return FlowIndex(tuple(order), branches)


def build_field_index(fields: Sequence[Mapping[str, object]]) -> FieldIndex:
    """`QuestionFieldSpecs` 를 색인으로."""
    specs: dict[tuple[str, str], FieldSpec] = {}
    for raw in fields:
        item = as_str(raw.get("item_id"))
        name = as_str(raw.get("field_name"))
        data_type = as_str(raw.get("data_type"))
        if item is None or name is None or data_type is None:
            continue
        repeat = tuple(key for key in (as_list(raw.get("repeat_keys")) or []) if isinstance(key, str))
        options = frozenset(
            code
            for option in (as_list(raw.get("options")) or [])
            if (mapped := as_map(option)) is not None and (code := as_str(mapped.get("option_code"))) is not None
        )
        specs[(item, name)] = FieldSpec(
            data_type=data_type,
            minimum=_number(raw.get("minimum")),
            maximum=_number(raw.get("maximum")),
            exclusive_minimum=_number(raw.get("exclusive_minimum")),
            repeat_keys=repeat or ("",),
            options=options,
        )
    return FieldIndex(specs)


def _same(left: object, right: object) -> bool:
    """참·거짓과 수를 섞어 같다고 보지 않는 비교(JSON 의 자료형은 서로 다르다)."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if is_number(left) and is_number(right):
        return float(left) == float(right)  # pyright: ignore[reportArgumentType]
    return left == right


def _compare(operator: str, actual: object, expected: object) -> bool:
    if operator == "EQ":
        return _same(actual, expected)
    if operator == "NE":
        return not _same(actual, expected)
    if not (is_number(actual) and is_number(expected)):
        return False
    left, right = float(actual), float(expected)  # pyright: ignore[reportArgumentType]
    return {"LT": left < right, "LE": left <= right, "GT": left > right, "GE": left >= right}.get(operator, False)


def skipped_items(flow: FlowIndex, saved: Mapping[tuple[str, str], object]) -> set[str]:
    """이번에 저장한 값으로 건너뛰는 문항들: 조건이 맞은 분기가 뛰어넘는 문항(순서표 순서 사이).

    왜 모든 문항의 분기를 보나: 정본 labels.py 의 next_after 가 이번 턴에 저장한 값 전체로 건너뛸 문항을 정한다
    (한 턴에 앞 문항 칸과 뒤 문항 칸이 함께 저장되는 경우, 예: '운동은 전혀 안 해요').
    """
    skipped: set[str] = set()
    for item in flow.order:
        for branch in flow.branches.get(item, ()):
            if branch.slot is None:
                break  # 앞 분기가 모두 맞지 않을 때의 기본 경로. 뛰어넘는 것이 없다
            if branch.slot in saved and _compare(branch.operator, saved[branch.slot], branch.value):
                start = flow.order.index(item) + 1
                end = flow.position(branch.next_item)
                stop = len(flow.order) if end is None else end
                skipped.update(flow.order[start:stop])
                break
    return skipped


def next_after(
    flow: FlowIndex,
    fields: FieldIndex,
    base_item: str,
    saved: Mapping[tuple[str, str], object],
) -> str | None:
    """`base_item` 다음에 물을 문항(건너뛰기 적용, 끝이면 END). 순서표에 base_item 이 없으면 None.

    정본 labels.py next_after 와 같다: 이번 턴에 칸이 모두 저장된 뒤 문항도 묻지 않는다. 칸 일부만 저장된 문항은 남은
    칸을 물어야 하므로 건너뛰지 않는다.
    """
    position = flow.position(base_item)
    if position is None:
        return None
    skip = skipped_items(flow, saved)
    for later in flow.order:
        names = fields.fields_of(later)
        if names and all((later, name) in saved for name in names):
            skip.add(later)
    index = position + 1
    while index < len(flow.order) and flow.order[index] in skip:
        index += 1
    return flow.order[index] if index < len(flow.order) else END
