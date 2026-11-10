"""출력 검증의 입력과 결과 값. 영역 밖 계약 값은 아니고 이 라이브러리의 공개 값이다."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from model_io.contract.models import ActionExtractionRules, ViolationCode
from model_io.core.bank import FieldIndex, FlowIndex
from model_io.core.rules import DEFAULT_RULES


@dataclass(frozen=True)
class Violation:
    """위반 하나. 코드는 계약 ViolationCode, path 는 어디서 어겼는지(예: `values[1].key`)다. 환자 발화는 싣지 않는다."""

    code: ViolationCode
    path: str


class Rewrite(StrEnum):
    """값 고쳐 쓰기(D115)의 종류."""

    NEXT_ITEM_FILLED = "NEXT_ITEM_FILLED"  # 다음 문항을 순서표로 채웠다(U74)
    OUT_OF_RANGE = "OUT_OF_RANGE"  # 칸 규격의 최댓값을 넘은 값을 비우고 다시 묻는다
    COUNT_EXCEEDS_DAYS = "COUNT_EXCEEDS_DAYS"  # 횟수가 기간의 날수보다 커서 다시 묻는다(R2)


@dataclass(frozen=True)
class GuardContext:
    """출력 검증이 필요로 하는 요청 정보: 지금 묻는 문항, 순서표, 칸 규격, 입력 state."""

    asked_item: str
    flow: FlowIndex
    fields: FieldIndex
    state: Mapping[str, object] = field(default_factory=lambda: dict[str, object]())
    rules: ActionExtractionRules = field(default_factory=lambda: DEFAULT_RULES)


@dataclass(frozen=True)
class GuardOutcome:
    """출력 검증 결과: 검증된 출력(또는 출력 불가), 고쳐 쓰기 전 모델 출력의 위반, 한 고쳐 쓰기들.

    output 이 None 이면 출력 불가다(OUTPUT_INVALID). violations 는 항상 고쳐 쓰기 전 출력으로 센 것이다(D115, 계약
    ViolationCode).
    """

    output: Mapping[str, object] | None
    violations: tuple[Violation, ...]
    rewrites: tuple[Rewrite, ...] = ()

    @property
    def valid(self) -> bool:
        """검증된 출력이 있는가."""
        return self.output is not None
