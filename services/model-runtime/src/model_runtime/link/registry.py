"""link_registry: 레지스트리에서 모델 패키지를 digest 로 받는다(OCI Distribution Spec, 표준 클라이언트 ORAS).

영역 밖 통신이다. 사설 루트 인증서로 TLS 를 신뢰하고(ADR 0013), 나가는 호출은 게이트웨이 터널을 지난다(D128).
받은 파일의 digest 검증은 받는 컴포넌트(package_loader)가 한다. 여기서는 바이트를 가져다 줄 뿐이다.
"""

# oras 는 형 선언이 없는 라이브러리라 그 경계에서만 pyright 의 Unknown 보고를 끈다
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path
from typing import cast
from urllib.parse import urljoin, urlsplit

import oras.provider
import requests

from model_runtime.types import PackageNotFoundError, RawManifest, RegistryUnavailableError

# 왜 이 Accept: OCI Image Spec 1.1 의 이미지 매니페스트 미디어 유형. 모델 패키지도 이 매니페스트 형식이다(계약
# OciImageManifestMediaType)
_MANIFEST_ACCEPT = "application/vnd.oci.image.manifest.v1+json"
# 왜 sha256-<16진수>: 게시 도구가 패키지마다 다는 태그다(publish_registry.package_tag). 태그 목록(`tags/list`)이
# 패키지를 찾는
# 유일한 표준 길이라 digest 를 태그 문자 집합(OCI Distribution Spec 의 태그 정규식)으로 옮긴 이름을 쓴다(cosign 의
# 같은 관례)
PACKAGE_TAG = re.compile(r"sha256-[a-f0-9]{64}")
# 왜 100: 태그 목록 한 쪽을 달라고 하는 크기. Distribution 의 `n` 매개변수이고 측정하지 않았다(레지스트리가 더 적게
# 줄 수 있다)
TAGS_PAGE = 100
_LINK_NEXT = re.compile(r'<([^>]+)>\s*;\s*rel="next"')


def basic_credentials(line: str) -> tuple[str, str]:
    """자격 파일의 한 줄 `사용자:비밀번호` 를 HTTP 기본 인증(RFC 7617)의 두 값으로 나눈다.

    왜 첫 콜론에서 나누나: RFC 7617 2 는 user-id 에 콜론이 없다고 정하고 비밀번호에는 콜론을 허용한다.
    """
    user, separator, password = line.partition(":")
    if not separator or not user:
        raise ValueError("레지스트리 자격은 한 줄 '사용자:비밀번호' 여야 한다")
    return user, password


class OciPackageSource:
    """PackageSource 의 구현. 요청마다 새 ORAS 클라이언트를 쓰지 않고 하나를 재사용한다(세션과 토큰 유지)."""

    def __init__(
        self,
        base_url: str,
        repository: str,
        credentials: tuple[str, str] | None,
        root_certificate: Path | None,
        egress_proxy: str | None,
        client_certificate: tuple[Path, Path] | None = None,
        tags_page: int = TAGS_PAGE,
    ) -> None:
        self._tags_page = tags_page
        parts = urlsplit(base_url)
        self._hostname = parts.netloc
        self._repository = repository
        self._client = oras.provider.Registry(
            hostname=self._hostname,
            insecure=parts.scheme == "http",
            tls_verify=str(root_certificate) if root_certificate else True,
            # 왜 basic: 플랫폼의 레지스트리는 Distribution 앞의 Caddy 기본 인증이다.
            # 토큰 인증(bearer realm) 서버는 지원하지 않는다
            auth_backend="basic",
        )
        if credentials:
            # 왜 login 이 아니라 set_basic_auth: login 은 사용자 전역 docker 설정과 docker 클라이언트를
            # 건드린다(워크스페이스 규칙)
            self._client.auth.set_basic_auth(*credentials)
        if client_certificate:
            # 왜 경로만 준다: requests 는 연결을 새로 열 때마다 파일을 읽는다. 인증서 에이전트가 파일을 갱신하면 새
            # 연결부터
            # 새 인증서를 쓴다(이미 열린 연결은 그대로). 레지스트리가 mTLS 를 요구하지 않아도 계약대로 보인다
            self._client.session.cert = (str(client_certificate[0]), str(client_certificate[1]))
        if egress_proxy:
            self._client.session.proxies = {"https": egress_proxy, "http": egress_proxy}

    def close(self) -> None:
        """레지스트리와의 연결을 닫는다(서버가 TLS 종료를 기다리지 않게)."""
        self._client.session.close()

    def _reference(self, digest: str) -> str:
        return f"{self._hostname}/{self._repository}@{digest}"

    def _fetch_manifest_sync(self, digest: str) -> RawManifest:
        container = self._client.get_container(self._reference(digest))
        try:
            response = self._client.do_request(
                f"{self._client.prefix}://{container.manifest_url()}", "GET", headers={"Accept": _MANIFEST_ACCEPT}
            )
        except (requests.RequestException, ValueError, OSError) as error:
            raise RegistryUnavailableError("레지스트리에 닿지 못했거나 인증이 거절되었다") from error
        if response.status_code == requests.codes.not_found:
            raise PackageNotFoundError("레지스트리에 그 digest 의 매니페스트가 없다")
        if response.status_code != requests.codes.ok:
            raise RegistryUnavailableError(f"레지스트리가 매니페스트 요청에 {response.status_code} 로 답했다")
        return RawManifest(digest, response.content)

    async def fetch_manifest(self, digest: str) -> RawManifest:
        """매니페스트를 받는다. 없으면 PackageNotFoundError, 닿지 못하면 RegistryUnavailableError."""
        return await asyncio.to_thread(self._fetch_manifest_sync, digest)

    def _download_sync(self, digest: str, destination: Path) -> None:
        try:
            with self._client.get_blob(self._reference(digest), digest, stream=True) as response:
                if response.status_code == requests.codes.not_found:
                    raise PackageNotFoundError("레지스트리에 그 digest 의 파일이 없다")
                if response.status_code != requests.codes.ok:
                    raise RegistryUnavailableError(f"레지스트리가 파일 요청에 {response.status_code} 로 답했다")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        handle.write(chunk)
        except (requests.RequestException, ValueError, OSError) as error:
            raise RegistryUnavailableError("레지스트리에 닿지 못했거나 인증이 거절되었다") from error

    async def download_blob(self, digest: str, destination: Path) -> None:
        """파일을 destination 에 받는다. 내용 검증은 받는 컴포넌트가 한다."""
        await asyncio.to_thread(self._download_sync, digest, destination)

    def _list_manifests_sync(self) -> list[RawManifest]:
        base = f"{self._client.prefix}://{self._hostname}"
        url: str | None = f"{base}/v2/{self._repository}/tags/list?n={self._tags_page}"
        tags: list[str] = []
        try:
            while url:
                response = self._client.do_request(url, "GET")
                if response.status_code == requests.codes.not_found:
                    return []  # 왜 빈 목록: 아직 아무것도 올리지 않은 저장소는 태그 목록이 없다(NAME_UNKNOWN)
                if response.status_code != requests.codes.ok:
                    raise RegistryUnavailableError(f"레지스트리가 태그 목록 요청에 {response.status_code} 로 답했다")
                listed = cast("list[str]", response.json().get("tags") or [])
                tags += [tag for tag in listed if PACKAGE_TAG.fullmatch(tag)]
                link = _LINK_NEXT.search(response.headers.get("Link", ""))
                url = urljoin(base, link.group(1)) if link else None
            found: dict[str, RawManifest] = {}
            for tag in tags:
                reply = self._client.do_request(
                    f"{base}/v2/{self._repository}/manifests/{tag}", "GET", headers={"Accept": _MANIFEST_ACCEPT}
                )
                if reply.status_code != requests.codes.ok:
                    continue  # 왜 건너뜀: 목록을 받는 사이 지워진 태그다
                digest = f"sha256:{hashlib.sha256(reply.content).hexdigest()}"
                found[digest] = RawManifest(digest, reply.content)
        except (requests.RequestException, ValueError, OSError) as error:
            raise RegistryUnavailableError("레지스트리에 닿지 못했거나 인증이 거절되었다") from error
        return list(found.values())

    async def list_manifests(self) -> list[RawManifest]:
        """게시된 모델 패키지의 매니페스트들. 태그 목록(OCI Distribution Spec)에서 패키지 태그만 골라 매니페스트를
        받는다."""
        return await asyncio.to_thread(self._list_manifests_sync)
