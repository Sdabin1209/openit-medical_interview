"""store: 활성화·롤백 기록은 파일 하나에 덧붙이고, 덧붙이다 멈춘 마지막 줄만 버린다."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from model_runtime.store.release_log import ReleaseLogFile
from model_runtime.types import ReleaseEvent, ReleaseEventKind

pytestmark = pytest.mark.anyio
NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
DIGEST = "sha256:" + "a" * 64


async def test_append_and_read_round_trip_in_order(tmp_path: Path) -> None:
    log = ReleaseLogFile(tmp_path / "state")
    first = ReleaseEvent(ReleaseEventKind.ACTIVATE_REQUESTED, DIGEST, NOW, actor="사용자-1", reason="평가 확인")
    second = ReleaseEvent(ReleaseEventKind.LOADED, DIGEST, NOW, summary="{}")
    await log.append(first)
    await log.append(second)
    assert list(await log.read_all()) == [first, second]
    assert (tmp_path / "state" / "release-log.jsonl").read_text(encoding="utf-8").count("\n") == 2


async def test_missing_file_is_empty(tmp_path: Path) -> None:
    assert list(await ReleaseLogFile(tmp_path).read_all()) == []


async def test_unterminated_last_line_is_dropped(tmp_path: Path) -> None:
    log = ReleaseLogFile(tmp_path)
    await log.append(ReleaseEvent(ReleaseEventKind.LOADED, DIGEST, NOW))
    with (tmp_path / "release-log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"kind": "LOADED", "package_dig')
    assert len(await log.read_all()) == 1


async def test_corrupt_terminated_line_is_not_hidden(tmp_path: Path) -> None:
    log = ReleaseLogFile(tmp_path)
    await log.append(ReleaseEvent(ReleaseEventKind.LOADED, DIGEST, NOW))
    with (tmp_path / "release-log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("garbage\n")
    await log.append(ReleaseEvent(ReleaseEventKind.LOADED, DIGEST, NOW))
    with pytest.raises(ValueError, match="Expecting value"):
        await log.read_all()


async def test_file_is_private(tmp_path: Path) -> None:
    await ReleaseLogFile(tmp_path).append(ReleaseEvent(ReleaseEventKind.LOADED, DIGEST, NOW))
    assert (tmp_path / "release-log.jsonl").stat().st_mode & 0o077 == 0
