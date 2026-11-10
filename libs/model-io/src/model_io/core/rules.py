"""LoRA-A 출력의 합격 조건 명세(계약 ActionExtractionRules)의 값. 데이터셋 정본(labels.py, IO_SPEC.md)이 정한다."""

from __future__ import annotations

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
