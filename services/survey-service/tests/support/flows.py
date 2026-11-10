"""시험이 쓰는 흐름 조각: 문항 세트 활성화, 시작 코드 발급, 세션 시작, 턴 보내기."""

import uuid
from typing import Any

import httpx
from tests.support.harness import Harness, question_set, xfcc


def idem() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def activate(h: Harness, c: httpx.AsyncClient, body: dict[str, Any] | None = None) -> str:
    """문항 세트를 올려 활성화하고 버전 식별자를 돌려준다."""
    up = await c.post("/v1/question-set-versions", json=body or question_set(), headers={**h.human("author"), **idem()})
    assert up.status_code == 201, up.text
    qsv = up.json()["question_set_version_id"]
    act = await c.post(f"/v1/question-set-versions/{qsv}/activation", headers=h.human("author"))
    assert act.status_code == 200, act.text
    return qsv


async def issue(h: Harness, c: httpx.AsyncClient, subject: str = "subj-1", questionnaire: str | None = None) -> str:
    body: dict[str, Any] = {"subject_ref": subject}
    if questionnaire:
        body["questionnaire_id"] = questionnaire
    r = await c.post("/v1/start-codes", json=body, headers={**h.human("staff"), **idem()})
    assert r.status_code == 201, r.text
    return str(r.json()["code"])


async def start(h: Harness, c: httpx.AsyncClient, device: str = "kiosk-01", subject: str = "subj-1") -> str:
    """코드를 발급해 세션을 시작하고 세션 식별자를 돌려준다(문항 세트는 이미 활성이어야 한다)."""
    code = await issue(h, c, subject)
    h.model.will_respond("안녕하세요. 먼저 질환부터 여쭤볼게요.")
    r = await c.post("/v1/sessions", json={"start_code": code}, headers=xfcc(device))
    assert r.status_code == 201, r.text
    return str(r.json()["session_id"])


def turn_body(text: str = "네") -> dict[str, str]:
    return {"turn_id": str(uuid.uuid4()), "utterance": text}
