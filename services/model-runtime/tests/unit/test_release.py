"""release: 활성 패키지는 기록에서 구한다. 적재 중에는 이전 패키지가 계속 쓰이고, 실패하면 이전 패키지를 유지한다."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from model_runtime.components.release import Release
from model_runtime.contract.models import ModelLoadState
from model_runtime.types import ActivationOutcome, ReleaseEvent, ReleaseEventKind

pytestmark = pytest.mark.anyio
T0 = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
A, B, C = (f"sha256:{ch * 64}" for ch in "abc")


class MemoryStore:
    def __init__(self, events: Sequence[ReleaseEvent] = ()) -> None:
        self.events = list(events)

    async def append(self, event: ReleaseEvent) -> None:
        self.events.append(event)

    async def read_all(self) -> Sequence[ReleaseEvent]:
        return list(self.events)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


async def activate(release: Release, digest: str, minutes: int, actor: str = "u1") -> None:
    assert (
        await release.request(ReleaseEventKind.ACTIVATE_REQUESTED, digest, actor, "사유", at(minutes))
        is ActivationOutcome.STARTED
    )
    await release.loaded(digest, "{}", at(minutes))


async def test_empty_log_is_not_loaded() -> None:
    release = Release(MemoryStore())
    assert await release.open() is None
    assert release.view().state is ModelLoadState.NOT_LOADED and release.view().package_digest is None


async def test_activation_records_who_when_why_and_tracks_previous() -> None:
    store = MemoryStore()
    release = Release(store)
    await release.open()
    await activate(release, A, 1, "user-1")
    await activate(release, B, 2, "user-2")
    view = release.view()
    assert (view.state, view.package_digest, view.previous_package_digest) == (ModelLoadState.READY, B, A)
    assert (view.activated_by, view.activated_at) == ("user-2", at(2))
    requested = [e for e in store.events if e.kind is ReleaseEventKind.ACTIVATE_REQUESTED]
    assert [(e.actor, e.reason, e.at) for e in requested] == [("user-1", "사유", at(1)), ("user-2", "사유", at(2))]


async def test_loading_keeps_serving_old_and_shows_target() -> None:
    release = Release(MemoryStore())
    await release.open()
    await activate(release, A, 1)
    assert await release.request(ReleaseEventKind.ACTIVATE_REQUESTED, B, "u", "r", at(2)) is ActivationOutcome.STARTED
    view = release.view()
    assert (view.state, view.package_digest, view.previous_package_digest) == (ModelLoadState.LOADING, B, A)
    assert release.serving_digest == A
    assert (
        await release.request(ReleaseEventKind.ACTIVATE_REQUESTED, B, "u", "r", at(3))
        is ActivationOutcome.ALREADY_ACTIVE
    )  # 같은 요청은 멱등
    assert await release.request(ReleaseEventKind.ACTIVATE_REQUESTED, C, "u", "r", at(3)) is ActivationOutcome.BUSY


async def test_failed_load_keeps_previous_package() -> None:
    store = MemoryStore()
    release = Release(store)
    await release.open()
    await activate(release, A, 1)
    await release.request(ReleaseEventKind.ACTIVATE_REQUESTED, B, "u", "r", at(2))
    await release.failed(B, "받은 파일의 digest 가 다르다", at(3))
    view = release.view()
    assert (view.state, view.package_digest) == (ModelLoadState.FAILED, A) and release.serving_digest == A
    assert store.events[-1].kind is ReleaseEventKind.LOAD_FAILED
    assert not release.was_active(B)  # 적재에 실패한 패키지는 롤백 대상이 아니다


async def test_already_active_digest_is_idempotent_and_writes_nothing() -> None:
    store = MemoryStore()
    release = Release(store)
    await release.open()
    await activate(release, A, 1)
    count = len(store.events)
    assert (
        await release.request(ReleaseEventKind.ACTIVATE_REQUESTED, A, "u", "r", at(2))
        is ActivationOutcome.ALREADY_ACTIVE
    )
    assert len(store.events) == count


async def test_rollback_targets_are_previously_active_packages_except_current() -> None:
    release = Release(MemoryStore())
    await release.open()
    await activate(release, A, 1)
    await activate(release, B, 2)
    assert release.was_active(A) and not release.was_active(B) and not release.was_active(C)


async def test_open_restores_the_last_loaded_package_from_the_log() -> None:
    events = [
        ReleaseEvent(ReleaseEventKind.ACTIVATE_REQUESTED, A, at(1), actor="u1", reason="r"),
        ReleaseEvent(ReleaseEventKind.LOADED, A, at(1)),
        ReleaseEvent(ReleaseEventKind.ACTIVATE_REQUESTED, B, at(2), actor="u2", reason="r"),
        ReleaseEvent(ReleaseEventKind.LOADED, B, at(2)),
        ReleaseEvent(ReleaseEventKind.ACTIVATE_REQUESTED, C, at(3), actor="u3", reason="r"),  # 적재 도중에 멈췄다
    ]
    release = Release(MemoryStore(events))
    assert await release.open() == B
    release.restored(B)
    view = release.view()
    assert (view.state, view.package_digest, view.previous_package_digest, view.activated_by) == (
        ModelLoadState.READY,
        B,
        A,
        "u2",
    )
