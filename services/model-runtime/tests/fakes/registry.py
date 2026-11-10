"""시험용 OCI 레지스트리(OCI Distribution Spec 의 push·pull 최소 부분). 기본 인증(RFC 7617)을 요구하고 digest 를
검증해 저장한다."""

import base64
import hashlib
import re
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response


class FakeRegistry:
    """메모리 저장소. blobs 와 manifests 는 digest 를 키로 한다."""

    def __init__(self, user: str, password: str) -> None:
        self.expected = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        self.blobs: dict[str, bytes] = {}
        self.manifests: dict[str, tuple[bytes, str]] = {}
        self.tags: dict[str, str] = {}
        self.uploads: dict[str, bytearray] = {}
        self.requests: list[tuple[str, str]] = []

    def app(self) -> FastAPI:
        app = FastAPI()

        @app.api_route("/v2/{rest:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
        async def handle(request: Request, rest: str) -> Response:  # pyright: ignore[reportUnusedFunction]
            self.requests.append((request.method, rest))
            if request.headers.get("authorization") != self.expected:
                return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="registry"'})
            return await self._route(request, rest)

        return app

    async def _route(self, request: Request, rest: str) -> Response:
        method = request.method
        if rest in ("", "/"):
            return Response("{}", media_type="application/json")
        blob = re.fullmatch(r"(?P<name>.+)/blobs/(?P<digest>sha256:[a-f0-9]{64})", rest)
        if blob:
            data = self.blobs.get(blob["digest"])
            if data is None:
                return Response(status_code=404)
            headers = {"Docker-Content-Digest": blob["digest"], "Content-Length": str(len(data))}
            return Response(None if method == "HEAD" else data, headers=headers, media_type="application/octet-stream")
        start = re.fullmatch(r"(?P<name>.+)/blobs/uploads/?", rest)
        if start and method == "POST":
            upload_id = uuid.uuid4().hex
            self.uploads[upload_id] = bytearray()
            return Response(status_code=202, headers={"Location": f"/v2/{start['name']}/blobs/uploads/{upload_id}"})
        upload = re.fullmatch(r"(?P<name>.+)/blobs/uploads/(?P<id>[a-f0-9]+)", rest)
        if upload and method == "PUT":
            body = bytes(self.uploads.pop(upload["id"], bytearray())) + await request.body()
            digest = request.query_params.get("digest", "")
            if f"sha256:{hashlib.sha256(body).hexdigest()}" != digest:
                return Response(status_code=400, content=b'{"errors":[{"code":"DIGEST_INVALID"}]}')
            self.blobs[digest] = body
            return Response(status_code=201, headers={"Docker-Content-Digest": digest})
        manifest = re.fullmatch(r"(?P<name>.+)/manifests/(?P<ref>.+)", rest)
        if manifest:
            ref = manifest["ref"]
            if method == "PUT":
                body = await request.body()
                digest = f"sha256:{hashlib.sha256(body).hexdigest()}"
                self.manifests[digest] = (body, request.headers.get("content-type", ""))
                if not ref.startswith("sha256:"):
                    self.tags[ref] = digest
                return Response(status_code=201, headers={"Docker-Content-Digest": digest})
            digest = ref if ref.startswith("sha256:") else self.tags.get(ref, "")
            found = self.manifests.get(digest)
            if found is None:
                return Response(status_code=404)
            headers: dict[str, Any] = {"Docker-Content-Digest": digest}
            return Response(None if method == "HEAD" else found[0], headers=headers, media_type=found[1])
        return Response(status_code=404)
