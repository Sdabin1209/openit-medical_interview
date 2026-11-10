"""한 건의 문진을 위한 환자 발화 대본과 기대 값, 게시 도구가 평가에 쓰는 작은 평가 집합.

출처: 데이터셋 정본 문서 `contracts/inputs/IO_SPEC.md` 의 예(5.1 시작, 5.2 정상, 5.3 건너뛰기, 5.9 끝)와 `PIPELINE_LOGIC.md` 의 사례(운동 40분)를 가져왔고, 나머지는 같은 형식으로
썼다. 학습 서버의 학습 데이터는 읽지 못했으므로(서버 접속 금지) 대본의 발화가 학습한 분포 안에 있는지는 확인하지 않았다. 대본은 환자가 문항마다 말한 칸을 명시적으로
말하게 써서(진단과 약을 둘 다 말한다) 기대 값이 모호하지 않게 한다.

대본은 문항 식별자로 찾는다. 서비스가 알려 주는 지금 문항(`current_item_id`)의 발화를 보낸다. 건너뛰기가 일어나면 대본의 순서와 상관없이 서비스의 순서를 따른다.
기대 값은 product 모드가 결과(getResult)에 저장되었는지 본다. 값의 키는 `<문항>.<칸>` 이다(계약 SlotRefString).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .questionnaire import END, Questionnaire


@dataclass(frozen=True)
class ScriptTurn:
    item: str
    utterance: str
    expected: dict[str, Any]


def _no_disease(item: str) -> ScriptTurn:
    return ScriptTurn(item, "아니요 진단받은 적도 없고 약도 안 먹어요", {f"{item}.diagnosed": False, f"{item}.on_medication": False})


def _no_family(item: str) -> ScriptTurn:
    return ScriptTurn(item, "가족 중에 그런 분은 없어요", {f"{item}.family_history": False})


SCRIPT: list[ScriptTurn] = [
    ScriptTurn("Q1.D01", "네 오년 전에 진단받고 지금 약 먹어요", {"Q1.D01.diagnosed": True, "Q1.D01.on_medication": True}),  # IO_SPEC 5.2
    _no_disease("Q1.D02"),
    ScriptTurn("Q1.D03", "고혈압은 진단받았고 지금도 약 먹고 있어요", {"Q1.D03.diagnosed": True, "Q1.D03.on_medication": True}),
    *[_no_disease(f"Q1.D{n:02d}") for n in range(4, 12)],
    _no_family("Q2.D01"),
    _no_family("Q2.D02"),
    ScriptTurn("Q2.D03", "아버지가 고혈압이 있으세요", {"Q2.D03.family_history": True}),
    _no_family("Q2.D04"),
    _no_family("Q2.D05"),
    ScriptTurn("Q3", "B형간염은 아니에요", {"Q3.answer": "no"}),
    ScriptTurn("Q4", "담배는 평생 안 피웠어요", {"Q4.answer": False}),  # IO_SPEC 5.3: Q4_1 을 건너뛴다
    ScriptTurn("Q5", "가열식 전자담배도 안 써 봤어요", {"Q5.answer": False}),
    ScriptTurn("Q6", "액상 전자담배도 안 써 봤어요", {"Q6.answer": False}),
    ScriptTurn("Q7", "술은 아예 안 마셔요", {"Q7.does_not_drink": True}),  # Q7_1·Q7_2 를 건너뛴다
    ScriptTurn("Q8_1", "힘든 운동은 일주일에 하나도 안 해요", {"Q8_1.days": 0}),  # Q8_2 를 건너뛴다
    ScriptTurn("Q9_1", "숨이 조금 찰 정도의 운동은 일주일에 사흘 해요", {"Q9_1.days": 3}),
    ScriptTurn("Q9_2", "그런 날은 하루에 사십 분쯤 해요", {"Q9_2.duration_minutes": 40}),  # PIPELINE_LOGIC.md 의 운동 40분
    ScriptTurn("Q10", "일주일에 세 번 아령 해요", {"Q10.days": 3}),  # IO_SPEC 5.9: 마지막 문항, 다음은 END
]
BY_ITEM = {turn.item: turn for turn in SCRIPT}

# 시스템 프롬프트: pipeline 모드의 중립 어댑터는 학습한 프롬프트가 없다. 학습하지 않은 기반 모델이 입출력 형식을 알아듣도록 적은 것이고 품질을 겨냥하지 않았다.
# 왜 /no_think: Qwen3 는 기본으로 <think> 로 생각 과정을 길게(실측: B 시작 입력에 1281자) 내서 응답 문장의 계약 길이 상한(344자)을 넘고 모델 서비스가 503 으로 거른다.
# Qwen3 공식 소프트 스위치 /no_think 는 생각 블록을 비운다(실측: 41자, `<think>` 와 `</think>` 사이가 비어 있다). 학습된 어댑터의 프롬프트는 product 모드에서 호출자가 준다.
PIPELINE_SYSTEM_A = "/no_think 건강검진 문진 상담의 값 추출기다. 입력 JSON 을 읽고 출력 JSON 하나만 답한다."
PIPELINE_SYSTEM_B = "/no_think 건강검진 문진 상담원이다. 입력 JSON 을 읽고 환자에게 할 응답 문장 하나만 100자 안으로 답한다."


def walk(questionnaire: Questionnaire) -> list[str]:
    """대본을 순서표대로 따라간 문항 순서(마지막은 END). 대본에 없는 문항을 만나면 ValueError."""
    order: list[str] = []
    item = questionnaire.flow["start_item"]
    while item != END:
        if item not in BY_ITEM:
            raise ValueError(f"대본에 {item} 의 발화가 없다")
        order.append(item)
        item = questionnaire.next_item(item, BY_ITEM[item].expected)
    return order


def _a_row(questionnaire: Questionnaire, turn: ScriptTurn, texts: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload: dict[str, Any] = {
        "current_question": texts[turn.item],
        "question_id": turn.item,
        "state": {},
        "user_utterance": turn.utterance,
    }
    gold: dict[str, Any] = {
        "action": "NEXT",
        "next_item": questionnaire.next_item(turn.item, turn.expected),
        "values": [
            {"key": key, "value": value, "precision": "exact", "status": "ANSWERED", "save": True} for key, value in turn.expected.items()
        ],
    }
    return payload, gold


def evaluation_rows(questionnaire: Questionnaire, system_a: str, system_b: str) -> tuple[str, str]:
    """게시 도구(package-publish)의 평가 집합 두 개(학습 형식의 JSON Lines: system, user, assistant 메시지). 점검용 작은 집합이다(품질 평가가 아니다).

    A: 대본의 네 문항(정상, 건너뛰기, 마지막). B: 시작과 다음 문항, 끝(IO_SPEC.md 5.1, 5.2, 5.9). B 입력의 topic·known 은 IO_SPEC 의 예와 labels.py 의 topic 틀을 따른다.
    """
    texts = {item["item_id"]: item["text"] for item in questionnaire.items}

    def line(system: str, user: dict[str, Any], assistant: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            {"role": "assistant", "content": assistant},
        ]
        return json.dumps({"messages": messages}, ensure_ascii=False)

    a_lines: list[str] = []
    for item in ("Q1.D01", "Q1.D03", "Q4", "Q10"):
        payload, gold = _a_row(questionnaire, BY_ITEM[item], texts)
        a_lines.append(line(system_a, payload, json.dumps(gold, ensure_ascii=False)))
    b_rows: list[tuple[dict[str, Any], str]] = [
        (
            {"action": "START", "next": {"type": "NEXT", "question_id": "Q1.D01", "text": texts["Q1.D01"]}},
            "안녕하세요. 지금부터 건강검진 문진표를 같이 작성해 볼게요.",
        ),
        (
            {
                "action": "NEXT",
                "known": "진단: 받음, 지금 약: 먹음",
                "next": {"type": "NEXT", "question_id": "Q1.D02", "text": texts["Q1.D02"]},
                "topic": "뇌졸중(중풍) 진단을 받았는지와 지금 약을 먹는지",
                "user_utterance": BY_ITEM["Q1.D01"].utterance,
            },
            "진단받으시고 지금 약도 드시는군요.",
        ),
        (
            {
                "action": "NEXT",
                "known": "근력 운동: 일주일에 3일",
                "next": {"type": "END"},
                "topic": "최근 1주일 동안 근력 운동을 한 날 수",
                "user_utterance": BY_ITEM["Q10"].utterance,
            },
            "일주일에 3일 하시는군요. 이걸로 문진은 다 끝났어요.",
        ),
    ]
    return "\n".join(a_lines) + "\n", "\n".join(line(system_b, user, text) for user, text in b_rows) + "\n"
