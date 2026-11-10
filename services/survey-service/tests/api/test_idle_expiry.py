"""유휴 만료는 서버다(계약 9.0.0 kiosk-frontend-002): 활동은 startSession·submitTurn·requestStaffCall 이다."""

from datetime import timedelta

import pytest
from tests.support.flows import activate, start, turn_body
from tests.support.harness import UNAVAILABLE, Harness, extraction, value, xfcc

from survey_service.jobs import purge_expired

pytestmark = pytest.mark.anyio
KIOSK = xfcc("kiosk-01")


async def state(h: Harness, sid: str) -> str:
    async with h.client() as c:
        return str((await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)).json()["status"])


async def test_a_turn_is_an_activity_even_when_it_ends_in_a_failure_signal(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        h.clock.advance(50)
        h.model.will_extract(UNAVAILABLE)
        h.model.will_extract(UNAVAILABLE)
        failed = await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK)
        assert failed.json()["failure_signal"] == "EXTRACTION_UNAVAILABLE"
        h.clock.advance(50)  # 시작에서 100초, 마지막 활동(실패한 턴)에서 50초
        assert await state(h, sid) == "ACTIVE"
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond("술은 드시나요?")
        h.clock.advance(5)
        assert (await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK)).status_code == 200
        h.clock.advance(59)
        assert await state(h, sid) == "ACTIVE"  # 상태 읽기는 활동이 아니다
        h.clock.advance(2)
        assert await state(h, sid) == "EXPIRED"


async def test_expiry_boundary_is_exactly_the_idle_seconds(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
    h.clock.advance(59.9)
    assert await state(h, sid) == "ACTIVE"
    h.clock.advance(0.1)
    assert await state(h, sid) == "EXPIRED"


async def test_a_turn_after_idle_is_judged_first_and_answered_like_an_ended_session(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        h.clock.advance(61)
        late = await c.post(f"/v1/sessions/{sid}/turns", json=turn_body(), headers=KIOSK)
        assert (
            late.status_code == 409 and late.json()["reason"] == "SESSION_NOT_ACTIVE" and not h.model.extract_requests
        )
        ended = await c.post(f"/v1/sessions/{sid}/end", headers=KIOSK)
        assert ended.status_code == 200 and ended.json()["status"] == "EXPIRED"


async def test_end_session_judges_idle_too(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        h.clock.advance(61)
        assert (await c.post(f"/v1/sessions/{sid}/end", headers=KIOSK)).json()["status"] == "EXPIRED"


async def test_a_staff_call_is_an_activity_and_a_paused_session_never_expires(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        h.clock.advance(50)
        assert (await c.post(f"/v1/sessions/{sid}/staff-calls", headers=KIOSK)).status_code == 201
        h.clock.advance(3600)  # 멈춘 세션은 만료하지 않는다
        assert await state(h, sid) == "PAUSED"
        resumed = await c.post(f"/v1/sessions/{sid}/intervention", json={"action": "RESUME"}, headers=h.human("staff"))
        assert resumed.json()["status"] == "ACTIVE"
        h.clock.advance(30)  # 재개한 때부터 다시 잰다
        assert await state(h, sid) == "ACTIVE"
        h.clock.advance(31)
        assert await state(h, sid) == "EXPIRED"


async def test_purge_job_expires_with_the_same_boundary_and_only_active_sessions(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        active = await start(h, c, device="kiosk-01", subject="s1")
        paused = await start(h, c, device="kiosk-02", subject="s2")
        assert (await c.post(f"/v1/sessions/{paused}/staff-calls", headers=xfcc("kiosk-02"))).status_code == 201
    started = h.clock()
    h.clock.advance(59)
    assert (
        await purge_expired(h.runtime.store, started + timedelta(seconds=59), retention_days=180, idle_seconds=60) == 0
    )
    h.clock.advance(1)
    now = started + timedelta(seconds=60)
    assert await purge_expired(h.runtime.store, now, retention_days=180, idle_seconds=60) == 1  # 경계: 60초 지난 것
    assert await state(h, active) == "EXPIRED"
    assert await purge_expired(h.runtime.store, now, retention_days=180, idle_seconds=60) == 0  # 멱등
    async with h.client() as c:
        got = await c.get(f"/v1/sessions/{paused}/state", headers=xfcc("kiosk-02"))
        assert got.json()["status"] == "PAUSED"


async def test_failure_signal_turn_id_is_not_recorded_but_success_is_replayed(harness: Harness) -> None:
    """kiosk-frontend-003: 실패 신호를 준 turn_id 는 다시 보내면 다시 처리하고, 성공한 turn_id 는 같은 결과다."""
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        body = turn_body("진단 받았어요")
        for _ in range(2):  # 실패 신호를 두 번 받아도 매번 모델을 다시 부른다
            h.model.will_extract(UNAVAILABLE)
            h.model.will_extract(UNAVAILABLE)
            failed = await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)
            assert failed.json()["failure_signal"] == "EXTRACTION_UNAVAILABLE"
        assert len(h.model.extract_requests) == 4
        h.model.will_extract(extraction("NEXT", "Q2", [value("Q1.diagnosed", True)]))
        h.model.will_respond("술은 드시나요?")
        ok = await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)
        assert "failure_signal" not in ok.json()
        calls = len(h.model.extract_requests)
        replay = await c.post(f"/v1/sessions/{sid}/turns", json=body, headers=KIOSK)
        assert replay.json() == ok.json() and len(h.model.extract_requests) == calls
