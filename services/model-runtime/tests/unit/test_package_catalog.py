"""package_catalog: 게시된 패키지 목록(계약 ModelPackageList)의 정렬·쪽 나누기·활성 표시."""

from pathlib import Path

import pytest

from model_runtime.components.package_catalog import CursorError, PackageCatalog, decode_cursor, encode_cursor
from model_runtime.contract.models import ModelPackageList, PageCursor
from model_runtime.types import RawManifest
from package_factory import MemorySource, publish_memory

pytestmark = pytest.mark.anyio


def three(tmp_path: Path) -> tuple[MemorySource, list[str]]:
    """만든 때가 다른 패키지 셋(오래된 것부터)."""
    source = MemorySource()
    digests = [
        publish_memory(source, tmp_path / name, seed=name, created_at=f"2026-11-0{day}T09:00:00+00:00")
        for name, day in (("old", 1), ("mid", 2), ("new", 3))
    ]
    return source, digests


async def test_newest_first_and_active_flag_follow_the_release_record(tmp_path: Path) -> None:
    source, (old, mid, new) = three(tmp_path)
    page = await PackageCatalog(source, tmp_path / "w").page(mid, None, None)
    ModelPackageList.model_validate(page)  # 낸 값은 계약을 지킨다
    assert [(i["package_digest"], i["is_active"]) for i in page["items"]] == [(new, False), (mid, True), (old, False)]
    assert "next_cursor" not in page


async def test_pages_follow_the_cursor_without_gaps_or_repeats(tmp_path: Path) -> None:
    source, digests = three(tmp_path)
    catalog = PackageCatalog(source, tmp_path / "w")
    first = await catalog.page(None, 2, None)
    assert [i["package_digest"] for i in first["items"]] == [digests[2], digests[1]]
    PageCursor.model_validate(first["next_cursor"])  # 계약 PageCursor(96자 이하)
    second = await catalog.page(None, 2, first["next_cursor"])
    assert [i["package_digest"] for i in second["items"]] == [digests[0]] and "next_cursor" not in second


async def test_new_package_between_pages_does_not_shift_the_next_page(tmp_path: Path) -> None:
    source, digests = three(tmp_path)
    catalog = PackageCatalog(source, tmp_path / "w")
    first = await catalog.page(None, 1, None)
    publish_memory(source, tmp_path / "newest", seed="newest", created_at="2026-11-09T09:00:00+00:00")
    second = await catalog.page(None, 1, first["next_cursor"])
    assert [i["package_digest"] for i in second["items"]] == [digests[1]]  # 위치가 아니라 digest 를 이어받는다


async def test_items_that_are_not_packages_are_skipped(tmp_path: Path) -> None:
    source, digests = three(tmp_path)
    source.manifests["sha256:" + "f" * 64] = b'{"not": "a package"}'
    page = await PackageCatalog(source, tmp_path / "w").page(None, None, None)
    assert {i["package_digest"] for i in page["items"]} == set(digests)


async def test_unknown_cursor_is_refused(tmp_path: Path) -> None:
    source, _ = three(tmp_path)
    catalog = PackageCatalog(source, tmp_path / "w")
    with pytest.raises(CursorError):
        await catalog.page(None, None, encode_cursor("sha256:" + "a" * 64))
    with pytest.raises(CursorError):
        decode_cursor("!!!")


async def test_created_at_is_read_once_per_package(tmp_path: Path) -> None:
    source, _ = three(tmp_path)
    catalog = PackageCatalog(source, tmp_path / "w")
    await catalog.page(None, None, None)
    reads = len(source.downloads)
    await catalog.page(None, None, None)
    assert len(source.downloads) == reads  # 패키지는 digest 로 불변이라 다시 받지 않는다


async def test_empty_repository_gives_an_empty_page(tmp_path: Path) -> None:
    class Empty(MemorySource):
        async def list_manifests(self) -> list[RawManifest]:
            return []

    assert await PackageCatalog(Empty(), tmp_path).page(None, None, None) == {"items": []}
