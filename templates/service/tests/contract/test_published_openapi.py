"""응답이 이 서비스가 공개하는 OpenAPI 의 응답 스키마와 맞는지 본다(경계 사례 포함).

영역 계약(contracts/)이 정해지면 이 파일에 받는·내는 계약 검증을 더한다(ADR 0003).
"""

from typing import Any

import jsonschema
from fastapi.testclient import TestClient

from __PKG__.main import Settings, create_app


def _schema(spec: dict[str, Any], path: str, code: str) -> dict[str, Any]:
    ref: str = spec["paths"][path]["get"]["responses"][code]["content"]["application/json"]["schema"]["$ref"]
    name = ref.rsplit("/", 1)[-1]
    return {"$ref": f"#/components/schemas/{name}", "components": spec["components"]}


def test_health_responses_match_openapi() -> None:
    app = create_app(Settings())
    spec: dict[str, Any] = app.openapi()
    client = TestClient(app)
    jsonschema.validate(client.get("/healthz").json(), _schema(spec, "/healthz", "200"))
    jsonschema.validate(client.get("/readyz").json(), _schema(spec, "/readyz", "200"))


def test_not_ready_response_matches_openapi() -> None:
    async def down() -> bool:
        return False

    app = create_app(Settings(), {"x": down})
    spec: dict[str, Any] = app.openapi()
    body = TestClient(app).get("/readyz").json()
    jsonschema.validate(body, _schema(spec, "/readyz", "200"))
