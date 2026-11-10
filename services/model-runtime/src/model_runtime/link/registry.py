"""link_registry: 레지스트리에서 모델 패키지를 digest 로 받는다(OCI Distribution Spec, 표준 클라이언트 ORAS).

영역 밖 통신이다. 사설 루트 인증서로 TLS 를 신뢰하고(ADR 0013), 나가는 호출은 게이트웨이 터널을 지난다(D128).
받은 파일의 digest 검증은 받는 컴포넌트(package_loader)가 한다. 여기서는 바이트를 가져다 줄 뿐이다.
"""

# oras 는 형 선언이 없는 라이브러리라 그 경계에서만 pyright 의 Unknown 보고를 끈다
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlsplit

import oras.provider
import requests

from model_runtime.types import PackageNotFoundError, RawManifest, RegistryUnavailableError

# 왜 이 Accept: OCI Image Spec 1.1 의 이미지 매니페스트 미디어 유형. 모델 패키지도 이 매니페스트 형식이다(계약
# OciImageManifestMediaType)
_MANIFEST_ACCEPT = "application/vnd.oci.image.manifest.v1+json"


class OciPackageSource:
    """PackageSource 의 구현. 요청마다 새 ORAS 클라이언트를 쓰지 않고 하나를 재사용한다(세션과 토큰 유지)."""

    def __init__(
        self,
        base_url: str,
        repository: str,
        credentials: tuple[str, str] | None,
        root_certificate: Path | None,
        egress_proxy: str | None,
    ) -> None:
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
        except (requests.RequestException, ValueError) as error:
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
        except (requests.RequestException, ValueError) as error:
            raise RegistryUnavailableError("레지스트리에 닿지 못했거나 인증이 거절되었다") from error

    async def download_blob(self, digest: str, destination: Path) -> None:
        """파일을 destination 에 받는다. 내용 검증은 받는 컴포넌트가 한다."""
        await asyncio.to_thread(self._download_sync, digest, destination)
