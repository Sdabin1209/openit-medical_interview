"""question_bank: 문항 세트 검증·해시·조회와 순서표 계산.

입력은 올린 문항 세트(QuestionSetContent), 출력은 검증 결과·해시·다음 문항이다. 모델 호출이나 저장은 모르고,
순서표와 칸 규격을 제공하기만 한다(design.md 2절). 계약 스키마로 잡히는 모양(길이, 개수, 형식)은 올리는 쪽
요청 검증이 이미 마쳤으므로 여기서는 스키마로 표현되지 않는 문항 사이의 관계만 본다.
"""

import hashlib
import json
from collections.abc import Mapping
from typing import NamedTuple

from survey_service.contract.models import (
    FlowBranch,
    FlowComparison,
    QuestionFieldSpec,
    QuestionItem,
    QuestionSetContent,
    SlotDataType,
)
from survey_service.types import SlotValue, split_slot, unwrap

END = "END"
# 왜 104: 추출 요청(ExtractionRequest.fields)이 칸 규격을 한꺼번에 싣고 그 상한이 QuestionFieldSpecs 의 maxItems 다.
# 이 상한을 넘는 문항 세트는 올려도 추출 요청을 만들 수 없으므로 올릴 때 거절한다
MAX_REQUEST_FIELDS = 104


class Problem(NamedTuple):
    """문항 세트의 어긋난 곳 하나."""

    pointer: str
    detail: str


def content_hash(content: QuestionSetContent) -> str:
    """내용의 SHA-256. 키를 정렬한 JSON 이라 같은 내용이면 같은 값이다."""
    canonical = json.dumps(
        content.model_dump(mode="json", exclude_none=True), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _items(content: QuestionSetContent) -> list[QuestionItem]:
    return list(content.bank.items.root)


def validate(content: QuestionSetContent) -> list[Problem]:
    """스키마로 표현되지 않는 관계를 본다: 문항 식별자 유일, 순서표가 가리키는 문항 존재, 칸 규격의 일관성."""
    problems: list[Problem] = []
    items = _items(content)
    ids: dict[str, QuestionItem] = {}
    for index, item in enumerate(items):
        item_id = item.item_id.root
        if item_id in ids:
            problems.append(Problem(f"/content/bank/items/{index}/item_id", "문항 식별자가 겹친다"))
        ids[item_id] = item
        names: set[str] = set()
        for number, spec in enumerate(item.fields.root):
            where = f"/content/bank/items/{index}/fields/{number}"
            if spec.item_id.root != item_id:
                problems.append(Problem(f"{where}/item_id", "칸 규격의 문항이 소속 문항과 다르다"))
            if spec.field_name.root in names:
                problems.append(Problem(f"{where}/field_name", "같은 문항 안에서 칸 이름이 겹친다"))
            names.add(spec.field_name.root)
            problems.extend(_spec_problems(spec, where))
    if sum(len(item.fields.root) for item in items) > MAX_REQUEST_FIELDS:
        problems.append(
            Problem("/content/bank/items", f"칸 규격의 합이 추출 요청의 상한 {MAX_REQUEST_FIELDS} 을 넘는다")
        )
    flow = content.flow
    if flow.start_item.root not in ids:
        problems.append(Problem("/content/flow/start_item", "첫 문항이 문항 은행에 없다"))
    seen: set[str] = set()
    for index, rule in enumerate(flow.rules):
        where = f"/content/flow/rules/{index}"
        rule_item = rule.item_id.root
        if rule_item not in ids:
            problems.append(Problem(f"{where}/item_id", "순서표의 문항이 문항 은행에 없다"))
        if rule_item in seen:
            problems.append(Problem(f"{where}/item_id", "문항 하나에 규칙이 둘이다"))
        seen.add(rule_item)
        problems.extend(_rule_problems(rule.branches, where, ids, content))
    for item_id in ids:
        if item_id not in seen:
            problems.append(Problem("/content/flow/rules", f"문항 {item_id} 의 다음 규칙이 없다"))
    return problems


def _spec_problems(spec: QuestionFieldSpec, where: str) -> list[Problem]:
    problems: list[Problem] = []
    options = spec.options.root if spec.options is not None else []
    if spec.data_type is SlotDataType.option and not options:
        problems.append(Problem(f"{where}/options", "선택지 칸에는 선택지가 있어야 한다"))
    if spec.data_type is not SlotDataType.option and options:
        problems.append(Problem(f"{where}/options", "선택지 칸이 아닌데 선택지가 있다"))
    codes = [option.option_code.root for option in options]
    if len(codes) != len(set(codes)):
        problems.append(Problem(f"{where}/options", "선택지 코드가 겹친다"))
    low = spec.minimum.root if spec.minimum is not None else None
    high = spec.maximum.root if spec.maximum is not None else None
    if low is not None and high is not None and low > high:
        problems.append(Problem(f"{where}/minimum", "최솟값이 최댓값보다 크다"))
    return problems


def _rule_problems(
    branches: list[FlowBranch], where: str, ids: Mapping[str, QuestionItem], content: QuestionSetContent
) -> list[Problem]:
    problems: list[Problem] = []
    unconditional_at: int | None = None
    for number, branch in enumerate(branches):
        spot = f"{where}/branches/{number}"
        target = branch.next_item.root
        if target != END and target not in ids:
            problems.append(Problem(f"{spot}/next_item", "다음 자리가 문항 은행에 없다"))
        if unconditional_at is not None:
            problems.append(Problem(spot, "조건 없는 분기 뒤에 분기가 있다(닿지 않는다)"))
        if branch.when is None:
            unconditional_at = number
            continue
        parts = split_slot(branch.when.slot.root)
        if parts is None or parts[0] not in ids or not _has_field(ids[parts[0]], parts[2]):
            problems.append(Problem(f"{spot}/when/slot", "조건의 칸이 문항 은행에 없다"))
    if unconditional_at is None:
        problems.append(Problem(f"{where}/branches", "조건 없는 기본 분기가 없다"))
    return problems


def _has_field(item: QuestionItem, name: str) -> bool:
    return any(spec.field_name.root == name for spec in item.fields.root)


def item_of(content: QuestionSetContent, item_id: str) -> QuestionItem | None:
    """문항 하나. 없으면 None."""
    for item in _items(content):
        if item.item_id.root == item_id:
            return item
    return None


def question_text(content: QuestionSetContent, item_id: str) -> str | None:
    """문항의 질문 문장."""
    item = item_of(content, item_id)
    return None if item is None else item.text.root


def all_field_specs(content: QuestionSetContent) -> list[QuestionFieldSpec]:
    """추출 요청에 싣는 칸 규격 전체(문항 순서대로)."""
    return [spec for item in _items(content) for spec in item.fields.root]


def _compare(operator: FlowComparison, left: SlotValue, right: bool | float | str) -> bool:
    if left is None:
        return False
    if isinstance(left, bool) != isinstance(right, bool):
        return False  # 왜: 예·아니오와 수는 서로 비교하지 않는다(True == 1 로 새는 것을 막는다)
    if operator is FlowComparison.EQ:
        return left == right
    if operator is FlowComparison.NE:
        return left != right
    if isinstance(left, str) or isinstance(right, str) or isinstance(left, bool) or isinstance(right, bool):
        return False  # 왜: 크기 비교는 수끼리만 뜻이 있다
    return {
        FlowComparison.LT: left < right,
        FlowComparison.LE: left <= right,
        FlowComparison.GT: left > right,
        FlowComparison.GE: left >= right,
    }[operator]


def next_after(content: QuestionSetContent, item_id: str, answers: Mapping[str, SlotValue]) -> str:
    """문항 다음 자리. 분기를 앞에서부터 보고 처음 맞는 것을 쓴다. 맞는 것이 없으면 END."""
    for rule in content.flow.rules:
        if rule.item_id.root != item_id:
            continue
        for branch in rule.branches:
            if branch.when is None:
                return branch.next_item.root
            right = unwrap(branch.when.value)
            if right is not None and _compare(branch.when.operator, answers.get(branch.when.slot.root), right):
                return branch.next_item.root
    return END
