"""문항 세트 올리기·활성화, 실패 사례 탐지·검토·내보내기, 결과 조회, 잡."""

import copy
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from tests.support.flows import activate, idem, start, turn_body
from tests.support.harness import UNAVAILABLE, Harness, extraction, question_set, value, xfcc

from survey_service.jobs import detect_failures, purge_expired
from survey_service.store.models import ResultAccessRow

pytestmark = pytest.mark.anyio
KIOSK = xfcc("kiosk-01")


async def test_question_set_validation_reports_pointers(harness: Harness) -> None:
    h = harness
    bad = question_set()
    bad["content"]["flow"]["start_item"] = "Q9"
    bad["content"]["flow"]["rules"][1]["branches"][1]["next_item"] = "Q7"
    bad["content"]["bank"]["items"][0]["fields"][0]["field_name"] = "on_medication"
    bad["content"]["flow"]["rules"].pop()
    async with h.client() as c:
        r = await c.post("/v1/question-set-versions", json=bad, headers={**h.human("author"), **idem()})
    assert r.status_code == 400
    pointers = {e["pointer"] for e in r.json()["errors"]}
    assert {
        "/content/flow/start_item",
        "/content/flow/rules/1/branches/1/next_item",
        "/content/bank/items/0/fields/1/field_name",
        "/content/flow/rules",
    } <= pointers


async def test_question_set_without_default_branch_and_option_rules(harness: Harness) -> None:
    h = harness
    bad = question_set()
    bad["content"]["flow"]["rules"][0]["branches"] = [
        {"when": {"slot": "Q1.diagnosed", "operator": "EQ", "value": True}, "next_item": "Q2"}
    ]
    bad["content"]["bank"]["items"][1]["fields"][0] = {"item_id": "Q2", "field_name": "answer", "data_type": "option"}
    async with h.client() as c:
        r = await c.post("/v1/question-set-versions", json=bad, headers={**h.human("author"), **idem()})
    pointers = {e["pointer"] for e in r.json()["errors"]}
    assert "/content/flow/rules/0/branches" in pointers and "/content/bank/items/1/fields/0/options" in pointers


async def test_versions_idempotency_and_activation(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        key = idem()
        first = await c.post("/v1/question-set-versions", json=question_set(), headers={**h.human("author"), **key})
        replay = await c.post("/v1/question-set-versions", json=question_set(), headers={**h.human("author"), **key})
        second = await c.post(
            "/v1/question-set-versions", json=question_set(), headers={**h.human("author", sub="u2"), **idem()}
        )
        assert first.json() == replay.json()
        assert (first.json()["version_number"], second.json()["version_number"]) == (1, 2)
        assert first.json()["content_hash"] == second.json()["content_hash"] and len(first.json()["content_hash"]) == 64
        assert (
            first.json()["uploaded_by"] == "user-1" and second.json()["uploaded_by"] == "u2"
        )  # 올린 사람은 인증된 사용자다
        assert (await c.get("/v1/questionnaires", headers=KIOSK)).json() == {
            "questionnaires": []
        }  # 저장만 하고 활성화하지 않는다
        listing = (
            await c.get(
                "/v1/question-set-versions",
                params={"questionnaire_id": "national-health", "limit": 1},
                headers=h.human("author"),
            )
        ).json()
        assert len(listing["items"]) == 1 and listing["items"][0]["version_number"] == 2 and "next_cursor" in listing
        got = await c.get(
            f"/v1/question-set-versions/{first.json()['question_set_version_id']}", headers=h.human("author")
        )
        assert got.json()["content"]["title"] == "국가건강검진 문진표"
        v1, v2 = first.json()["question_set_version_id"], second.json()["question_set_version_id"]
        a1 = await c.post(f"/v1/question-set-versions/{v1}/activation", headers=h.human("author"))
        again = await c.post(f"/v1/question-set-versions/{v1}/activation", headers=h.human("author"))
        assert (
            a1.status_code == 200
            and again.status_code == 200
            and a1.json()["activated_at"] == again.json()["activated_at"]
        )
        assert a1.json()["runtime_contract_version"] == 1
        # 진행 중인 세션은 시작할 때의 버전을 그대로 쓴다
        sid = await start(h, c)
        await c.post(f"/v1/question-set-versions/{v2}/activation", headers=h.human("author"))
        changed = copy.deepcopy(question_set())
        changed["content"]["bank"]["items"][0]["text"] = "새 질문입니다"
        await activate(h, c, changed)
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond("술은 드시나요?")
        await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK)
        sent_text = h.model.respond_requests[-1].next.text
        assert sent_text is not None and sent_text.root == "술을 드시나요?"
        assert (await c.get(f"/v1/question-set-versions/{uuid.uuid4()}", headers=h.human("author"))).status_code == 404
        assert (
            await c.post(f"/v1/question-set-versions/{uuid.uuid4()}/activation", headers=h.human("author"))
        ).status_code == 404


async def _failed_session(h: Harness) -> str:
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        h.model.will_extract(UNAVAILABLE)
        h.model.will_extract(UNAVAILABLE)
        await c.post(f"/v1/sessions/{sid}/turns", json=turn_body("환자가 한 말입니다"), headers=KIOSK)
        return sid


async def test_failure_detection_review_export(harness: Harness) -> None:
    h = harness
    await _failed_session(h)
    assert await detect_failures(h.runtime.store, h.clock()) == 1
    assert await detect_failures(h.runtime.store, h.clock()) == 0  # 멱등
    async with h.client() as c:
        reviewer = h.human("reviewer", sub="rev-1")
        page = (await c.get("/v1/cases", headers=reviewer)).json()
        case = page["items"][0]
        cid = case["case_id"]
        assert case["kind"] == "EXTRACT_FAILED" and case["review_status"] == "UNREVIEWED"
        assert case["utterance"] == "환자가 한 말입니다"  # 원문은 검토자에게만
        trace = (await c.get(f"/v1/deidentified-traces/{cid}", headers=reviewer)).json()
        assert (
            trace["failure_signal"] == "EXTRACTION_UNAVAILABLE" and "utterance" not in trace
        )  # 자동 비식별은 하지 않는다
        assert (await c.get("/v1/case-exports", headers=h.machine("model-lab"))).json()[
            "items"
        ] == []  # CONFIRMED 만 내보낸다
        expected = extraction("NEXT", "Q2", [value("Q1.diagnosed", True)])
        review = {
            "base_case_version": 1,
            "review_status": "CONFIRMED",
            "expected": expected,
            "reviewed_input": "진단 받았어요",
        }
        done = await c.post(f"/v1/cases/{cid}/reviews", json=review, headers=reviewer)
        same = await c.post(f"/v1/cases/{cid}/reviews", json={**review, "base_case_version": 2}, headers=reviewer)
        stale = await c.post(f"/v1/cases/{cid}/reviews", json=review, headers=reviewer)
        assert done.status_code == 201 and done.json()["case_version"] == 2 and done.json()["reviewed_by"] == "rev-1"
        assert same.status_code == 200 and same.json() == done.json()  # 같은 내용은 변화 없음
        assert stale.status_code == 409 and stale.json()["reason"] == "CASE_VERSION_MISMATCH"
        exported = (await c.get("/v1/case-exports", headers=h.machine("model-lab"))).json()["items"]
        assert (
            len(exported) == 1
            and exported[0]["reviewed_input"] == "진단 받았어요"
            and exported[0]["expected"]["action"] == "NEXT"
        )
        assert "utterance" not in exported[0] and "model_output" not in exported[0]  # 원문과 모델 출력은 나가지 않는다
        dismissed = {"base_case_version": 2, "review_status": "DISMISSED"}
        assert (await c.post(f"/v1/cases/{cid}/reviews", json=dismissed, headers=reviewer)).status_code == 201
        assert (await c.get("/v1/case-exports", headers=h.machine("model-lab"))).json()["items"] == []
        assert (
            await c.get("/v1/case-exports", params={"review_status": "UNREVIEWED"}, headers=h.machine("model-lab"))
        ).json() == {"items": []}
        assert (await c.get("/v1/cases", params={"review_status": "DISMISSED"}, headers=reviewer)).json()["items"][0][
            "case_id"
        ] == cid
        assert (await c.get(f"/v1/cases/{uuid.uuid4()}", headers=reviewer)).status_code == 404
        assert (await c.post(f"/v1/cases/{uuid.uuid4()}/reviews", json=review, headers=reviewer)).status_code == 404


async def test_reask_limit_makes_a_case_and_purge_removes_old_utterances(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        for _ in range(3):
            h.model.will_extract(
                extraction(
                    "REASK",
                    "Q1",
                    [value("Q1.diagnosed", None, "UNCLEAR", "unspecified")],
                    reason="MISSING",
                    targets=["Q1.diagnosed"],
                )
            )
            h.model.will_respond("다시 말씀해 주세요")
            await c.post(f"/v1/sessions/{sid}/turns", json=turn_body("글쎄요"), headers=KIOSK)
    assert await detect_failures(h.runtime.store, h.clock()) == 1
    async with h.client() as c:
        case = (await c.get("/v1/cases", headers=h.human("reviewer"))).json()["items"][0]
        assert case["kind"] == "REASK_STREAK" and case["model_output"]["action"] == "REASK"
    later = h.clock() + timedelta(days=181)
    changed = await purge_expired(h.runtime.store, later, retention_days=180, idle_seconds=60)
    assert changed >= 2  # 원문 두 곳(턴 기록, 실패 사례)과 만료된 세션
    async with h.client() as c:
        case = (await c.get(f"/v1/cases/{case['case_id']}", headers=h.human("reviewer"))).json()
        assert "utterance" not in case
        status = (await c.get(f"/v1/results/{sid}", headers=h.human("clinician"))).json()["status"]
        assert status == "EXPIRED"  # 유휴로 끝난 세션은 잡이 만료로 바꾼다
        ready = (await c.get("/v1/staff-alerts", headers=h.human("clinician"))).json()["items"]
        assert [a["kind"] for a in ready] == ["RESULT_READY"]  # 만료로 생긴 부분 결과도 의사에게 알린다


async def test_results_filters_fhir_errors_and_access_log(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        a = await start(h, c, "kiosk-01", "subj-a")
        b = await start(h, c, "kiosk-02", "subj-b")
        await c.post(f"/v1/sessions/{a}/end", headers=KIOSK)
        reader = h.machine("hospital")
        only_a = (await c.get("/v1/results", params={"subject_ref": "subj-a"}, headers=reader)).json()["items"]
        assert [r["session_id"] for r in only_a] == [a] and only_a[0]["status"] == "ENDED_PARTIAL"
        active = (await c.get("/v1/results", params={"status": "ACTIVE"}, headers=reader)).json()["items"]
        assert [r["session_id"] for r in active] == [b]
        # FHIR 의 오류는 OperationOutcome 이다(인증 실패와 없음 모두)
        missing = await c.get(f"/v1/results/{uuid.uuid4()}/fhir", headers=reader)
        assert missing.status_code == 404 and missing.json()["resourceType"] == "OperationOutcome"
        assert missing.json()["issue"][0]["code"] == "not-found"
        noauth = await c.get(f"/v1/results/{a}/fhir")
        assert noauth.status_code == 401 and noauth.json()["issue"][0]["code"] == "login"
        assert (await c.get(f"/v1/results/{a}/fhir", headers=h.human("staff"))).json()["issue"][0][
            "code"
        ] == "forbidden"
        partial = (await c.get(f"/v1/results/{a}/fhir", headers=reader)).json()
        assert (
            partial["status"] == "stopped"
            and partial["questionnaire"] == "https://example.org/fhir/Questionnaire/national-health"
        )
        assert all(
            "answer" not in child for item in partial["item"] for child in item["item"]
        )  # 빈칸은 answer 없이 사유 확장만
        assert (await c.get(f"/v1/results/{uuid.uuid4()}", headers=reader)).status_code == 404
        assert (
            await c.post(f"/v1/results/{uuid.uuid4()}/acknowledgements", headers=h.human("clinician"))
        ).status_code == 404
        assert (
            await c.post(f"/v1/results/{a}/acknowledgements", headers=reader)
        ).status_code == 403  # 확인 표시는 의사만
    async with h.engine.connect() as connection:
        # 읽은 호출자와 때가 접근 기록에 남는다: 성공한 읽기(부분 결과 FHIR 한 번)만 남고 거절·없음은 남지 않는다
        rows = (await connection.execute(select(ResultAccessRow.reader_kind, ResultAccessRow.reader))).all()
    assert [tuple(r) for r in rows] == [("MACHINE", "hospital")]
