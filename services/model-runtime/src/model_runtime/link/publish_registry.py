"""package_publish 가 모델 패키지를 레지스트리에 올리는 길(OCI Distribution Spec, 표준 클라이언트 ORAS).

영역 밖 통신이다. 파일(blob)을 올리고 매니페스트를 올려 매니페스트의 digest 를 돌려준다. 그 digest 가 패키지의 식별자다.
"""

# oras 는 형 선언이 없는 라이브러리라 그 경계에서만 pyright 의 Unknown 보고를 끈다
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import oras.provider
import requests

from model_runtime.components.package_publish import BuiltPackage

_MANIFEST_TYPE = "application/vnd.oci.image.manifest.v1+json"


class PublishError(Exception):
    """레지스트리에 올리지 못했다. 메시지에 자격과 주소의 비밀 부분은 싣지 않는다."""


class OciPackagePublisher:
    """BuiltPackage 를 레지스트리에 올린다."""

    def __init__(
        self, base_url: str, repository: str, credentials: tuple[str, str], root_certificate: Path | None
    ) -> None:
        parts = urlsplit(base_url)
        self._hostname = parts.netloc
        self._repository = repository
        self._client = oras.provider.Registry(
            hostname=self._hostname,
            insecure=parts.scheme == "http",
            tls_verify=str(root_certificate) if root_certificate else True,
            # 왜 basic: 플랫폼의 레지스트리는 Distribution 앞의 Caddy 기본 인증이다(registry.py 와 같다)
            auth_backend="basic",
        )
        self._client.auth.set_basic_auth(*credentials)

    def close(self) -> None:
        """레지스트리와의 연결을 닫는다."""
        self._client.session.close()

    def publish(self, package: BuiltPackage) -> str:
        """파일(config, layer 넷)과 매니페스트를 올리고 레지스트리가 확인한 매니페스트 digest 를 돌려준다."""
        container = self._client.get_container(f"{self._hostname}/{self._repository}@{package.digest}")
        try:
            for blob in (package.config, *package.layers):
                response = self._client.upload_blob(str(blob.path), container, blob.descriptor())
                if response.status_code not in (200, 201, 202):
                    raise PublishError(f"파일 올리기를 레지스트리가 {response.status_code} 로 거절했다")
            reply = self._client.do_request(
                f"{self._client.prefix}://{container.manifest_url()}",
                "PUT",
                headers={"Content-Type": _MANIFEST_TYPE},
                data=package.manifest,
            )
        except (requests.RequestException, ValueError) as error:
            raise PublishError("레지스트리에 닿지 못했거나 인증이 거절되었다") from error
        if reply.status_code not in (200, 201):
            raise PublishError(f"매니페스트 올리기를 레지스트리가 {reply.status_code} 로 거절했다")
        confirmed = reply.headers.get("Docker-Content-Digest")
        if confirmed is not None and confirmed != package.digest:
            raise PublishError("레지스트리가 확인한 매니페스트 digest 가 보낸 것과 다르다")
        return package.digest
