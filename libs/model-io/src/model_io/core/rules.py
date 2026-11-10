"""LoRA-A 출력의 합격 조건 명세(계약 ActionExtractionRules)의 값. 데이터셋 정본(labels.py, IO_SPEC.md)이 정한다."""

from __future__ import annotations

from dataclasses import dataclass

from model_io.contract.models import ActionExtractionRules

DEFAULT_RULES = ActionExtractionRules.model_validate(
    {
        # 왜: IO_SPEC.md 2.2 와 SQL.md 6.1. ANSWERED·CORRECTION 만 DB 에 저장하는 확정값이다
        "saved_statuses": ["ANSWERED", "CORRECTION"],
        # 왜: 같은 문서. 이 네 상태는 값이 없다(null). 학습 서버 final·finaltest 실측에서 null 11992건 = 네 상태 건수의
        # 합(계약 x-basis)
        "null_value_statuses": ["MISSING", "UNCLEAR", "UNKNOWN", "REJECTED"],
        # 왜: labels.py a_target 이 targets 를 붙이는 action
        "actions_with_targets": ["REASK", "CONFIRM", "HOLD", "SKIP"],
        # 왜: labels.py a_target 의 next_item 규칙. REASK·CONFIRM 은 대상 칸의 문항, REDIRECT 는 지금 묻던 문항, 그 밖은
        # 순서상 다음 문항
        "next_item_rules": [
            {"action": "NEXT", "rule": "SEQUENCE_AFTER_SAVED"},
            {"action": "CORRECT", "rule": "SEQUENCE_AFTER_SAVED"},
            {"action": "REASK", "rule": "TARGET_ITEM"},
            {"action": "CONFIRM", "rule": "TARGET_ITEM"},
            {"action": "HOLD", "rule": "SEQUENCE_AFTER_SAVED"},
            {"action": "SKIP", "rule": "SEQUENCE_AFTER_SAVED"},
            {"action": "REDIRECT", "rule": "ASKED_ITEM"},
        ],
        # 왜: docs/design.md 4절(현재 문항의 계열)과 계약 CurrentItemRule. 정정(CORRECT, CORRECTION)은 앞 문항 값을
        # 고치므로 면제
        "current_item_rule": {
            "allowed_scopes": ["CURRENT_ITEM", "ITEM_RANGE_TO_NEXT_ITEM", "ITEM_FAMILY"],
            "exempt_actions": ["CORRECT"],
            "exempt_statuses": ["CORRECTION"],
        },
    }
)
"""운영과 평가가 같이 쓰는 합격 조건(D97). 요청이 싣지 않으므로 이 라이브러리가 값을 가진다."""


@dataclass(frozen=True)
class DisabledRule:
    """켜지 않은 값 고쳐 쓰기 규칙 하나: 이름, 무엇을 하는 규칙인지, 왜 켜지 않았는지."""

    name: str
    what: str
    reason: str


# 왜 비활성: 두 규칙은 데이터셋 정본(contracts/inputs)에 규칙 데이터가 없다. 없는 값은 지어내지 않는다.
# 계약 9.0.0 이 ActionExtractionRules 에 '명시적 비활성'으로 적었고 요청은 dataset-change-requests DC-11 이다.
# 정본이 데이터를 주면 켠다
DISABLED_RULES: tuple[DisabledRule, ...] = (
    DisabledRule(
        "R1",
        "횟수가 있으면 '마심'(Q7.does_not_drink 거짓)으로 고친다",
        "정본에 규칙 데이터가 없고 정답 사례가 0건이라 모양을 확인하지 못했다(정본 없음, DC-11)",
    ),
    DisabledRule(
        "R3",
        "최대 음주량이 평소 음주량보다 적으면 CONFIRM/CONFLICT_MAX_BELOW_USUAL 로 고친다",
        "술 종류별 mL 환산표가 정본에 없다(정본 없음, DC-11)",
    ),
)
"""D115 값 고쳐 쓰기 중 이 라이브러리가 켜지 않은 규칙들. 검증기(guard)는 이 규칙을 적용하지 않는다."""
