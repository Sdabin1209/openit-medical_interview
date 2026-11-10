"""활성화·롤백 기록을 JSON Lines 파일 하나에 덧붙여 저장한다(ReleaseStore 의 구현, ADR 0002).

한 줄 = 기록 하나. 덧붙인 뒤 fsync 로 디스크에 닿고서야 돌아온다. 지우거나 고치지 않는다.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from model_runtime.types import ReleaseEvent, ReleaseEventKind


def _encode(event: ReleaseEvent) -> str:
    body: dict[str, str] = {
        "kind": event.kind.value,
        "package_digest": event.package_digest,
        "at": event.at.isoformat(),
    }
    for name in ("actor", "reason", "summary"):
        value = getattr(event, name)
        if value is not None:
            body[name] = value
    return json.dumps(body, ensure_ascii=False, sort_keys=True)


def _decode(line: str) -> ReleaseEvent:
    body = json.loads(line)
    return ReleaseEvent(
        kind=ReleaseEventKind(body["kind"]),
        package_digest=body["package_digest"],
        at=datetime.fromisoformat(body["at"]),
        actor=body.get("actor"),
        reason=body.get("reason"),
        summary=body.get("summary"),
    )


class ReleaseLogFile:
    """`<폴더>/release-log.jsonl` 에 기록을 덧붙인다."""

    def __init__(self, folder: Path) -> None:
        self._path = folder / "release-log.jsonl"
        self._lock = asyncio.Lock()

    def _append_sync(self, line: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # 왜 O_APPEND + fsync: 덧붙이는 쓰기는 다른 쓰기와 섞이지 않고, 돌아온 뒤에는 전원이 나가도 남는다
        descriptor = os.open(self._path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(descriptor, (line + "\n").encode("utf-8"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    async def append(self, event: ReleaseEvent) -> None:
        """기록을 덧붙인다. 디스크에 닿은 뒤에 돌아온다."""
        async with self._lock:
            await asyncio.to_thread(self._append_sync, _encode(event))

    def _read_sync(self) -> list[ReleaseEvent]:
        if not self._path.is_file():
            return []
        events: list[ReleaseEvent] = []
        lines = self._path.read_text(encoding="utf-8").splitlines(keepends=True)
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                events.append(_decode(line))
            except (ValueError, KeyError):
                # 왜: 줄바꿈 없이 끝난 마지막 줄만 덧붙이는 중에 멈춘 흔적으로 보고 버린다. 줄바꿈으로 끝난 줄이
                # 깨졌으면 숨기지 않고 멈춘다
                if index == len(lines) - 1 and not line.endswith("\n"):
                    continue
                raise
        return events

    async def read_all(self) -> Sequence[ReleaseEvent]:
        """저장된 기록을 순서대로 읽는다."""
        return await asyncio.to_thread(self._read_sync)
