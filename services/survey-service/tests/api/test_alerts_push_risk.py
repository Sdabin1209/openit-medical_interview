"""위험 신호, 알림 목록·스트림, 웹 푸시 구독과 전달."""

import asyncio
import json
from dataclasses import replace
from typing import Any

import pytest
from tests.support.flows import activate, start
from tests.support.harness import Harness, build_harness, xfcc

from survey_service.components import alert as alert_component
from survey_service.contract.models import AlertKind
from survey_service.link.admin_api import stream_frames

pytestmark = pytest.mark.anyio
KIOSK = xfcc("kiosk-01")
ENDPOINT = "https://push.example.org/send/abc"
SUBSCRIPTION: dict[str, Any] = {"endpoint": ENDPOINT, "keys": {"p256dh": "B" + "A" * 86, "auth": "A" * 22}}


def signal(sid: str, category: str = "CHEST_PAIN", at: str = "2026-11-10T09:00:30+00:00") -> dict[str, str]:
    return {"session_id": sid, "category": category, "detected_at": at, "source": "risk-engine"}


async def test_risk_detection_is_off_by_default(harness: Harness) -> None:
    async with harness.client() as c:
        await activate(harness, c)
        sid = await start(harness, c)
        r = await c.post("/v1/risk-signals", json=signal(sid), headers=harness.machine("risk-engine"))
    assert r.status_code == 403 and r.json()["reason"] == "RISK_DETECTION_DISABLED"


async def test_risk_signal_pauses_session_and_is_idempotent(database_url: str) -> None:
    h = await build_harness(database_url, risk=True)
    try:
        async with h.client() as c:
            await activate(h, c)
            sid = await start(h, c)
            await c.post("/v1/push-subscriptions", json=SUBSCRIPTION, headers=h.human("staff", sub="nurse-1"))
            first = await c.post("/v1/risk-signals", json=signal(sid), headers=h.machine("risk-engine"))
            again = await c.post("/v1/risk-signals", json=signal(sid), headers=h.machine("risk-engine"))
            assert first.status_code == 201 and again.status_code == 200 and first.json() == again.json()
            assert first.json()["kind"] == "RISK"
            state = (await c.get(f"/v1/sessions/{sid}/state", headers=KIOSK)).json()
            assert state["status"] == "PAUSED" and state["pause_reason"] == "RISK_SIGNAL"
            other = await c.post(
                "/v1/risk-signals",
                json=signal(sid, "DYSPNEA", "2026-11-10T09:01:00+00:00"),
                headers=h.machine("risk-engine"),
            )
            assert other.status_code == 409 and other.json()["reason"] == "SESSION_NOT_ACTIVE"
            missing = await c.post(
                "/v1/risk-signals",
                json=signal("00000000-0000-4000-8000-0000000000aa"),
                headers=h.machine("risk-engine"),
            )
            assert missing.status_code == 404
            assert (
                len(h.notifier.sent) == 1 and h.notifier.sent[0][0].kind is AlertKind.RISK
            )  # 같은 신호는 한 번만 푸시
            resumed = await c.post(
                f"/v1/sessions/{sid}/intervention", json={"action": "RESUME"}, headers=h.human("staff")
            )
            assert resumed.json()["status"] == "ACTIVE"
    finally:
        await h.engine.dispose()


async def test_push_subscription_and_gone_cleanup(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        config = await c.get("/v1/push-config", headers=h.human("staff"))
        assert config.json() == {"vapid_public_key": h.runtime.vapid_public_key}
        saved = await c.post("/v1/push-subscriptions", json=SUBSCRIPTION, headers=h.human("staff", sub="nurse-1"))
        assert saved.status_code == 201
        await activate(h, c)
        sid = await start(h, c)
        h.notifier.gone = (ENDPOINT,)  # 푸시 서비스가 구독이 사라졌다고 답한다
        await c.post(f"/v1/sessions/{sid}/staff-calls", headers=KIOSK)
        assert len(h.notifier.sent) == 1 and h.notifier.sent[0][1][0].endpoint.root.unicode_string() == ENDPOINT
        h.notifier.gone = ()
        await c.post(f"/v1/sessions/{sid}/intervention", json={"action": "ACKNOWLEDGE"}, headers=h.human("staff"))
        await c.post(f"/v1/sessions/{sid}/end", headers=KIOSK)  # 의사 구독은 없으니 보낼 대상이 없다
        assert len(h.notifier.sent) == 1
        async with h.runtime.store.transaction() as tx:
            assert await tx.push_subscriptions_for(AlertKind.CALL_STAFF) == ()  # 정리됐다
        bad = await c.post(
            "/v1/push-subscriptions",
            json={**SUBSCRIPTION, "keys": {"p256dh": "x", "auth": "y"}},
            headers=h.human("staff"),
        )
        assert bad.status_code == 400


async def test_alert_pages_use_cursors(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sids: list[str] = []
        for device in ("kiosk-01", "kiosk-02", "kiosk-03"):
            sid = await start(h, c, device=device)
            await c.post(f"/v1/sessions/{sid}/staff-calls", headers=xfcc(device))
            sids.append(sid)
            h.clock.advance(1)
        seen: list[str] = []
        cursor: str | None = None
        for _ in range(5):
            params: dict[str, str | int] = {"limit": 2}
            if cursor:
                params["cursor"] = cursor
            page = (await c.get("/v1/staff-alerts", params=params, headers=h.human("staff"))).json()
            seen += [a["session_id"] for a in page["items"]]
            cursor = page.get("next_cursor")
            if cursor is None:
                break
        assert seen == list(reversed(sids))  # 최근 것이 먼저, 중복·누락 없음
        bad = await c.get("/v1/staff-alerts", params={"cursor": "zzz"}, headers=h.human("staff"))
        assert bad.status_code == 400
        assert (await c.get("/v1/staff-alerts", params={"limit": 101}, headers=h.human("staff"))).status_code == 400


async def test_stream_sends_new_events_heartbeat_and_resync(harness: Harness) -> None:
    h = harness
    async with h.client() as c:
        await activate(h, c)
        sid = await start(h, c)
        stream = stream_frames(h.runtime, alert_component.STAFF_KINDS, None, poll_seconds=0.05)
        pending = asyncio.ensure_future(anext(stream))
        await asyncio.sleep(0.2)
        await c.post(f"/v1/sessions/{sid}/staff-calls", headers=KIOSK)
        frame = await asyncio.wait_for(pending, 5)
        lines = frame.strip().split("\n")
        assert lines[0] == "event: alert" and lines[1].startswith("id: ")
        data = json.loads(lines[2].removeprefix("data: "))
        assert (
            data["event"] == "alert" and data["alert"]["kind"] == "CALL_STAFF" and data["sequence"] == int(lines[1][4:])
        )
        await c.post(f"/v1/sessions/{sid}/intervention", json={"action": "ACKNOWLEDGE"}, headers=h.human("staff"))
        resolved = await asyncio.wait_for(anext(stream), 5)
        assert resolved.startswith("event: resolved\nid: ")
        await stream.aclose()
        # 이어 받기: 앞 순번 뒤의 이벤트부터
        resumed = stream_frames(h.runtime, alert_component.STAFF_KINDS, 0, poll_seconds=0.05)
        assert (await asyncio.wait_for(anext(resumed), 5)).startswith("event: alert\nid: 1\n")
        await resumed.aclose()
        # 서버가 모르는 순번이면 resync 가 먼저 오고 id 는 없다
        lost = stream_frames(h.runtime, alert_component.STAFF_KINDS, 999, poll_seconds=0.05)
        frame = await asyncio.wait_for(anext(lost), 5)
        assert frame.startswith("event: resync\ndata: ") and "id:" not in frame
        await lost.aclose()
        # 의사는 직원 알림을 받지 않는다
        doctor = stream_frames(h.runtime, alert_component.CLINICIAN_KINDS, 0, poll_seconds=0.05)
        short = replace(h.runtime, limits=replace(h.runtime.limits, heartbeat_seconds=0))
        beat = stream_frames(short, alert_component.CLINICIAN_KINDS, None, poll_seconds=0.01)
        frame = await asyncio.wait_for(anext(beat), 5)
        assert frame.startswith("event: heartbeat\ndata: ") and "id:" not in frame
        await beat.aclose()
        await doctor.aclose()


async def test_stream_route_requires_staff_or_clinician(harness: Harness) -> None:
    async with harness.client() as c:
        assert (await c.get("/v1/staff-alerts/stream")).status_code == 401
        assert (await c.get("/v1/staff-alerts/stream", headers=harness.human("author"))).status_code == 403
        assert (
            await c.get("/v1/staff-alerts/stream", headers={**harness.human("staff"), "Last-Event-ID": "x"})
        ).status_code == 400
