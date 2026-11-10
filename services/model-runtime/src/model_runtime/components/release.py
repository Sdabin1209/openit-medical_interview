"""release: 활성 모델 패키지와 활성화·롤백 기록(승인자, 시각, 사유)을 맡는다.

활성 패키지는 따로 저장하지 않고 덧붙이기만 하는 기록에서 구한다(마지막으로 적재에 성공한 패키지). 그래서 기록과
활성 포인터가 어긋날 수 없다. 입력은 승인된 활성화·롤백 요청, 출력은 활성 패키지와 지금 상태다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from model_runtime.contract.models import ModelLoadState
from model_runtime.types import (
    ActivationOutcome,
    ReleaseEvent,
    ReleaseEventKind,
    ReleaseStore,
    ReleaseView,
)

_REQUESTS = (ReleaseEventKind.ACTIVATE_REQUESTED, ReleaseEventKind.ROLLBACK_REQUESTED)


@dataclass(frozen=True)
class _Activation:
    digest: str
    actor: str | None
    at: datetime


class Release:
    """활성 패키지 포인터와 기록. 한 번에 하나의 적재만 진행한다."""

    def __init__(self, store: ReleaseStore) -> None:
        self._store = store
        self._loaded: list[str] = []  # 적재에 성공한 순서(같은 패키지가 다시 나올 수 있다)
        self._activations: dict[str, _Activation] = {}  # 패키지 -> 가장 최근 활성화 요청(누가, 언제)
        self._serving: str | None = None
        self._target: _Activation | None = None
        self._state = ModelLoadState.NOT_LOADED
        self._failed_digest: str | None = None

    async def open(self) -> str | None:
        """저장된 기록을 읽어 활성 패키지를 구한다. 적재해야 할 패키지의 digest 를 돌려준다(없으면 None).

        마지막 줄이 도중에 끊겼으면 저장소가 그 줄을 버린 채 돌려준다(덧붙이는 중에 멈춘 흔적).
        적재 결과 없이 끝난 요청(적재 도중 멈춤)은 활성으로 보지 않는다.
        """
        events: Sequence[ReleaseEvent] = await self._store.read_all()
        for event in events:
            if event.kind in _REQUESTS:
                self._activations[event.package_digest] = _Activation(event.package_digest, event.actor, event.at)
            elif event.kind is ReleaseEventKind.LOADED:
                self._loaded.append(event.package_digest)
        if not self._loaded:
            return None
        self._state = ModelLoadState.LOADING
        self._target = self._activations.get(self._loaded[-1]) or _Activation(self._loaded[-1], None, events[-1].at)
        return self._loaded[-1]

    def view(self) -> ReleaseView:
        """지금 상태. package_digest 는 효력이 있는 활성화(적재 중이면 목표), 적재 실패면 유지된 이전 패키지다."""
        if self._state is ModelLoadState.NOT_LOADED and self._serving is None:
            return ReleaseView(ModelLoadState.NOT_LOADED)
        if self._state is ModelLoadState.LOADING and self._target is not None:
            shown, previous = self._target.digest, self._serving or self._previous_of(self._target.digest)
        elif self._state is ModelLoadState.FAILED and self._serving is None:
            shown, previous = self._failed_digest, self._previous_of(self._failed_digest)
        else:
            shown, previous = self._serving, self._previous_of(self._serving)
        activation = self._activations.get(shown) if shown else None
        return ReleaseView(
            state=self._state,
            package_digest=shown,
            previous_package_digest=previous,
            activated_by=activation.actor if activation else None,
            activated_at=activation.at if activation else None,
        )

    def _previous_of(self, digest: str | None) -> str | None:
        """digest 가 활성이 되기 직전에 활성이었던 패키지(적재에 성공한 기록에서 가장 가까운 다른 패키지)."""
        if digest is None:
            return None
        last = max((i for i, d in enumerate(self._loaded) if d == digest), default=len(self._loaded))
        return next((d for d in reversed(self._loaded[:last]) if d != digest), None)

    @property
    def serving_digest(self) -> str | None:
        """지금 추론에 쓰는 패키지(적재를 마친 것). 적재 중에도 이전 패키지가 계속 쓰인다."""
        return self._serving

    def was_active(self, digest: str) -> bool:
        """digest 가 이전에 활성이었던(적재에 성공한) 패키지이고 지금 활성이 아닌가(롤백 대상이 될 수 있는가)."""
        return digest in self._loaded and digest != self._serving

    def is_loading(self, digest: str) -> bool:
        """digest 의 패키지를 지금 적재하는 중인가(같은 롤백 요청을 다시 받았을 때 멱등으로 답한다)."""
        return self._state is ModelLoadState.LOADING and self._target is not None and self._target.digest == digest

    def preview(self, digest: str) -> ActivationOutcome:
        """요청을 받으면 어떻게 되는지(기록하지 않는다). 같은 패키지가 이미 활성이거나 적재 중이면 같은 결과(멱등),
        다른 적재 중이면 BUSY."""
        if self._state is ModelLoadState.LOADING:
            same = self._target is not None and self._target.digest == digest
            return ActivationOutcome.ALREADY_ACTIVE if same else ActivationOutcome.BUSY
        if digest == self._serving and self._state is ModelLoadState.READY:
            return ActivationOutcome.ALREADY_ACTIVE
        return ActivationOutcome.STARTED

    async def request(
        self, kind: ReleaseEventKind, digest: str, actor: str, reason: str, now: datetime
    ) -> ActivationOutcome:
        """활성화·롤백 요청을 받아 기록한다(preview 가 STARTED 일 때만 기록하고 적재 중 상태가 된다)."""
        decided = self.preview(digest)
        if decided is not ActivationOutcome.STARTED:
            return decided
        await self._store.append(ReleaseEvent(kind, digest, now, actor=actor, reason=reason))
        self._target = self._activations[digest] = _Activation(digest, actor, now)
        self._state = ModelLoadState.LOADING
        return ActivationOutcome.STARTED

    async def loaded(self, digest: str, summary: str, now: datetime) -> None:
        """적재에 성공했다. 이 패키지가 활성이 되고 기록에 남는다."""
        await self._store.append(ReleaseEvent(ReleaseEventKind.LOADED, digest, now, summary=summary))
        self._loaded.append(digest)
        self._serving, self._target, self._state, self._failed_digest = digest, None, ModelLoadState.READY, None

    def restored(self, digest: str) -> None:
        """시작할 때 기록에서 구한 활성 패키지를 다시 적재했다(기록은 이미 있으므로 덧붙이지 않는다)."""
        self._serving, self._target, self._state, self._failed_digest = digest, None, ModelLoadState.READY, None

    async def failed(self, digest: str, detail: str, now: datetime) -> None:
        """적재에 실패했다. 이전 패키지가 있으면 계속 쓰고(D46) 상태만 FAILED 로 둔다."""
        await self._store.append(ReleaseEvent(ReleaseEventKind.LOAD_FAILED, digest, now, reason=detail))
        self._failed_digest, self._target, self._state = digest, None, ModelLoadState.FAILED
