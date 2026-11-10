"""문진 한 건 시나리오: 시작 코드 발급 → 시작 → 턴 여러 번(가짜 model-runtime) → 한도 건너뛰기 → 종료 →
결과·FHIR 조회 → 확인 표시.

임시 SQLite 와 PostgreSQL 16(`-m postgres`) 둘에서 같은 시나리오를 돈다. HTTP 는 실제 앱(ASGI)을 부르고
이웃은 가짜 model-runtime 이다.
"""

import uuid

import pytest

from tests.support.harness import Harness, extraction, question_set, value, xfcc

pytestmark = pytest.mark.anyio


async def _ready(h: Harness) -> None:
    """문항 세트를 올려 활성화한다."""
    async with h.client() as c:
        key = {"Idempotency-Key": str(uuid.uuid4())}
        up = await c.post("/v1/question-set-versions", json=question_set(), headers={**h.human("author"), **key})
        assert up.status_code == 201, up.text
        act = await c.post(
            f"/v1/question-set-versions/{up.json()['question_set_version_id']}/activation", headers=h.human("author")
        )
        assert act.status_code == 200, act.text


async def test_one_survey_end_to_end(harness: Harness) -> None:
    h = harness
    await _ready(h)
    device = xfcc("kiosk-01")
    async with h.client() as c:
        # 1. 직원이 대상자 참조값으로 시작 코드를 발급한다
        issued = await c.post(
            "/v1/start-codes",
            json={"subject_ref": "subj-000123"},
            headers={**h.human("staff"), "Idempotency-Key": str(uuid.uuid4())},
        )
        assert issued.status_code == 201, issued.text
        code = issued.json()["code"]
        assert len(code) == 6 and code.isdigit()

        # 2. 키오스크가 시작한다(LoRA-B 만 부른다)
        h.model.will_respond("안녕하세요. 먼저 뇌졸중 진단을 받으셨는지 여쭤볼게요.")
        started = await c.post("/v1/sessions", json={"start_code": code}, headers=device)
        assert started.status_code == 201, started.text
        sid = started.json()["session_id"]
        assert started.json()["current_item_id"] == "Q1"
        assert h.model.respond_requests[0].input.action.value == "START"
        assert not h.model.extract_requests

        # 3. 같은 기기가 같은 코드로 다시 시작하면 같은 세션을 200 으로 받는다
        again = await c.post("/v1/sessions", json={"start_code": code}, headers=device)
        assert again.status_code == 200 and again.json()["session_id"] == sid

        # 4. 정상 턴: Q1 답을 받고 Q2 로
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True), value("Q1.on_medication", False)]))
        h.model.will_respond("진단은 받으셨군요. 술은 드시나요?")
        turn1 = await c.post(
            f"/v1/sessions/{sid}/turns",
            json={"turn_id": str(uuid.uuid4()), "utterance": "진단은 받았고 약은 안 먹어요"},
            headers=device,
        )
        assert turn1.status_code == 200, turn1.text
        assert turn1.json()["current_item_id"] == "Q2" and turn1.json()["response_text"].startswith("진단은")

        # 5. Q2 에서 되묻기 한도: 처음 질문 1회 + 되묻기 2회 뒤 세 번째 REASK 가 오면 서비스가 건너뛴다(직원 알림 없음)
        for n in range(2):
            h.model.will_extract(
                extraction(
                    "REASK",
                    "Q2",
                    [value("Q2.answer", None, "UNCLEAR", "unspecified")],
                    reason="MISSING",
                    targets=["Q2.answer"],
                )
            )
            h.model.will_respond(f"다시 여쭤볼게요 {n}")
            reply = await c.post(
                f"/v1/sessions/{sid}/turns", json={"turn_id": str(uuid.uuid4()), "utterance": "글쎄요"}, headers=device
            )
            assert reply.json()["current_item_id"] == "Q2"
        h.model.will_extract(
            extraction(
                "REASK",
                "Q2",
                [value("Q2.answer", None, "UNCLEAR", "unspecified")],
                reason="MISSING",
                targets=["Q2.answer"],
            )
        )
        before = len(h.model.respond_requests)
        skipped = await c.post(
            f"/v1/sessions/{sid}/turns",
            json={"turn_id": str(uuid.uuid4()), "utterance": "음 잘 모르겠어요"},
            headers=device,
        )
        body = skipped.json()
        assert skipped.status_code == 200, skipped.text
        # Q2 의 기본 분기는 Q2_1 이다. 한도로 건너뛰면 Q2 의 답이 비어 조건이 맞지 않아 기본 분기로 간다
        assert body["current_item_id"] == "Q2_1"
        assert "건너뛸게요" in body["response_text"]
        assert len(h.model.respond_requests) == before  # 한도로 건너뛸 때 LoRA-B 에 거짓 사유를 보내지 않는다
        alerts = await c.get("/v1/staff-alerts", headers=h.human("staff"))
        assert alerts.json()["items"] == []

        # 6. 마지막 문항을 답하고 끝낸다
        h.model.will_extract(extraction("NEXT", "END", [value("Q2_1.amount", 3)]))
        h.model.will_respond("3잔이시군요. 문진이 모두 끝났어요.")
        last = await c.post(
            f"/v1/sessions/{sid}/turns", json={"turn_id": str(uuid.uuid4()), "utterance": "세 잔요"}, headers=device
        )
        assert last.json()["status"] == "ENDED_COMPLETE" and "current_item_id" not in last.json()

        ended = await c.post(f"/v1/sessions/{sid}/end", headers=device)
        assert ended.status_code == 200 and ended.json()["status"] == "ENDED_COMPLETE"

        # 7. 의사 화면: 결과 도착 알림, 목록, 상세, FHIR
        ready = await c.get("/v1/staff-alerts", headers=h.human("clinician"))
        assert [a["kind"] for a in ready.json()["items"]] == ["RESULT_READY"]
        listing = await c.get("/v1/results", params={"subject_ref": "subj-000123"}, headers=h.human("clinician"))
        assert [r["session_id"] for r in listing.json()["items"]] == [sid]
        detail = await c.get(f"/v1/results/{sid}", headers=h.machine("hospital"))
        assert detail.status_code == 200
        result = detail.json()
        assert result["status"] == "ENDED_COMPLETE" and result["subject_ref"] == "subj-000123"
        assert {a["key"] for a in result["answers"]} == {"Q1.diagnosed", "Q1.on_medication", "Q2_1.amount"}
        blank = [b for b in result["blanks"] if b["item_id"] == "Q2"]
        assert blank and blank[0]["reason"] == "REASK_LIMIT"
        fhir = await c.get(f"/v1/results/{sid}/fhir", headers=h.machine("hospital"))
        assert fhir.status_code == 200 and fhir.headers["content-type"].startswith("application/fhir+json")
        assert fhir.json()["status"] == "completed" and fhir.json()["subject"] == {
            "identifier": {"value": "subj-000123"}
        }
        text = fhir.text
        assert "asked-unknown" in text and "valueBoolean" in text and "valueInteger" in text

        # 8. 확인 표시(같은 의사가 다시 보내도 처음 기록)
        first = await c.post(f"/v1/results/{sid}/acknowledgements", headers=h.human("clinician", sub="doctor-1"))
        h.clock.advance(60)
        second = await c.post(f"/v1/results/{sid}/acknowledgements", headers=h.human("clinician", sub="doctor-1"))
        assert first.status_code == 200 and first.json() == second.json()
        assert first.json()["acknowledged_by"] == "doctor-1"
        shown = await c.get(f"/v1/results/{sid}", headers=h.human("clinician"))
        assert shown.json()["acknowledged_by"] == "doctor-1"
