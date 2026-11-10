"""package_catalog: 레지스트리에 게시된 모델 패키지의 목록(계약 ModelPackageList)을 만든다.

입력은 게시된 매니페스트들(레지스트리 포트)과 지금 활성인 패키지 digest, 쪽 나누기 값(Limit, Cursor), 출력은 목록
한 쪽이다.
적재하거나 활성화하지 않는다. 승인자가 목록에서 패키지를 골라 getModelPackage 로 평가 보고서를 본다(N07).
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from model_runtime.contract.models import (
    ModelPackageList,
    ModelPackageManifest,
    ModelPackageOciManifest,
    PageCursor,
    PageLimit,
)
from model_runtime.types import PackageInvalidError, PackageSource, PublishedPackage

DEFAULT_LIMIT = PageLimit.model_fields["root"].default or 30  # 계약 PageLimit 의 기본값(GitHub REST per_page 관행)


class CursorError(ValueError):
    """커서가 이 서버가 만든 값이 아니거나 가리키는 패키지가 목록에 없다(link_api 가 400 으로 낸다)."""


def encode_cursor(digest: str) -> str:
    """마지막으로 준 패키지의 digest 를 불투명 커서로(base64url, 패딩 없음, RFC 4648 5). 32바이트라 43자다."""
    raw = bytes.fromhex(digest.removeprefix("sha256:"))
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def decode_cursor(cursor: str) -> str:
    """커서가 가리키는 패키지 digest."""
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
    except (binascii.Error, ValueError) as error:
        raise CursorError("커서를 읽을 수 없다") from error
    if len(raw) != 32:
        raise CursorError("커서를 읽을 수 없다")
    return f"sha256:{raw.hex()}"


class PackageCatalog:
    """게시된 패키지를 최근 것이 먼저 나오게 쪽으로 나눈다.

    왜 config 의 created_at 으로 정렬하나: 계약 매니페스트(ModelPackageOciManifest)에는 주석(annotations)이 없어
    게시 시각이
    없다. 목록표의 created_at(패키지를 만든 때)이 있는 유일한 시각이다. 패키지는 digest 로 불변이라 읽은 값을 기억한다.
    왜 커서가 digest 인가: 목록은 요청마다 새로 정렬한다. 위치(번호)는 사이에 게시가 있으면 어긋나지만 digest 는
    어긋나지
    않는다. 값을 해석하지 않는 불투명 커서다(PageCursor).
    """

    def __init__(self, source: PackageSource, workdir: Path) -> None:
        self._source = source
        self._workdir = workdir
        self._created: dict[str, datetime] = {}

    async def _created_at(self, digest: str, oci: ModelPackageOciManifest) -> datetime:
        known = self._created.get(digest)
        if known is not None:
            return known
        target = self._workdir / "catalog" / oci.config.digest.root.removeprefix("sha256:")
        target.parent.mkdir(parents=True, exist_ok=True)
        await self._source.download_blob(oci.config.digest.root, target)
        try:
            manifest = ModelPackageManifest.model_validate_json(target.read_bytes())
        except ValidationError as error:
            raise PackageInvalidError("목록표가 계약과 다르다") from error
        finally:
            target.unlink(missing_ok=True)
        self._created[digest] = manifest.created_at.root
        return manifest.created_at.root

    async def published(self) -> list[PublishedPackage]:
        """게시된 패키지들(최근 것이 먼저, 같은 시각이면 digest 큰 것이 먼저). 계약과 다른 항목은 건너뛴다."""
        found: list[PublishedPackage] = []
        for raw in await self._source.list_manifests():
            try:
                oci = ModelPackageOciManifest.model_validate_json(raw.content)
                found.append(PublishedPackage(raw.digest, await self._created_at(raw.digest, oci)))
            except (ValidationError, PackageInvalidError):
                # 왜 건너뜀: 패키지가 아닌 항목 하나가 목록 전체를 막지 않는다. 읽을 수 있는 패키지만 고를 수 있다
                continue
        return sorted(found, key=lambda item: (item.created_at, item.digest), reverse=True)

    async def page(self, active_digest: str | None, limit: int | None, cursor: str | None) -> dict[str, Any]:
        """목록 한 쪽(ModelPackageList 의 JSON 모양)."""
        size = limit or DEFAULT_LIMIT
        ordered = await self.published()
        start = 0
        if cursor is not None:
            after = decode_cursor(PageCursor(cursor).root)
            positions = [index for index, item in enumerate(ordered) if item.digest == after]
            if not positions:
                raise CursorError("커서가 가리키는 패키지가 목록에 없다")
            start = positions[0] + 1
        chosen = ordered[start : start + size]
        body: dict[str, Any] = {
            "items": [{"package_digest": item.digest, "is_active": item.digest == active_digest} for item in chosen]
        }
        if start + size < len(ordered) and chosen:
            body["next_cursor"] = encode_cursor(chosen[-1].digest)
        return ModelPackageList.model_validate(body).model_dump(mode="json", exclude_none=True)
