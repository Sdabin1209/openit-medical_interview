"""계약(OpenAPI 3.1 + 공유 값 정의)으로 요청·응답을 검증하며 호출한다.

왜 직접 읽나: E2E 의 판정은 '응답이 계약대로인가'다. 영역이 만든 생성 타입이 아니라 계약 파일(정본)을 그대로 읽어 같은 JSON Schema 로 검증해야
영역의 생성 오류를 영역의 시험이 통과시켰을 때도 잡는다. JSON Schema 2020-12 의 format 은 기본이 주석이라 format 단언을 켠다(contracts/README.md '시각·식별자·검증기').
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
import yaml
from jsonschema import Draft202012Validator

COMPONENTS_REF = "../components.yaml#"


class StepFailure(Exception):
    """E2E 단계가 계약대로 끝나지 않았다."""


@dataclass(frozen=True)
class Reply:
    status: int
    body: Any
    headers: httpx.Headers


@dataclass(frozen=True)
class Operation:
    service: str
    operation_id: str
    method: str
    path: str
    spec: dict[str, Any]
    path_parameters: list[dict[str, Any]]


class Contract:
    def __init__(self, contracts_dir: Path) -> None:
        self.components: dict[str, Any] = yaml.safe_load((contracts_dir / "components.yaml").read_text(encoding="utf-8"))
        self.operations: dict[tuple[str, str], Operation] = {}
        for file in sorted((contracts_dir / "openapi").glob("*.yaml")):
            service = file.stem
            document = yaml.safe_load(file.read_text(encoding="utf-8"))
            for path, item in document["paths"].items():
                shared = item.get("parameters", [])
                for method, spec in item.items():
                    if method == "parameters":
                        continue
                    self.operations[(service, spec["operationId"])] = Operation(
                        service, spec["operationId"], method.upper(), path, spec, shared + spec.get("parameters", [])
                    )

    # ------------------------------------------------------------ 스키마
    def _resolve(self, node: Any) -> Any:
        """components.yaml 안의 $ref(응답·매개변수)를 한 번 풀어 준다."""
        if isinstance(node, dict) and "$ref" in node and str(node["$ref"]).startswith(COMPONENTS_REF):  # type: ignore[arg-type]
            target: Any = self.components
            for part in str(node["$ref"]).removeprefix(COMPONENTS_REF + "/").split("/"):  # type: ignore[arg-type]
                target = target[part]
            return target
        return cast(Any, node)

    def validator(self, schema: Any) -> Draft202012Validator:
        text = json.dumps(schema).replace(COMPONENTS_REF, "#")
        document: dict[str, Any] = {**json.loads(text), "components": self.components["components"]}
        return Draft202012Validator(document, format_checker=Draft202012Validator.FORMAT_CHECKER)

    def integer_constant(self, name: str) -> int:
        """계약의 정수 상수 스키마(`const`)의 값. 시간 상한처럼 계약이 정한 값을 복사하지 않고 읽는다."""
        value = self.components["components"]["schemas"][name].get("const")
        if not isinstance(value, int) or isinstance(value, bool):
            raise StepFailure(f"계약 {name} 의 const 가 정수가 아니다")
        return value

    def named(self, name: str) -> Draft202012Validator:
        return self.validator({"$ref": f"#/components/schemas/{name}"})

    def schema_errors(self, validator: Draft202012Validator, value: Any) -> list[str]:
        errors: list[Any] = list(cast(Any, validator).iter_errors(value))
        return [f"{'/'.join(str(p) for p in error.absolute_path) or '(본문)'}: {str(error.message)[:200]}" for error in errors]

    def request_schema(self, op: Operation) -> Any | None:
        body = op.spec.get("requestBody")
        if not body:
            return None
        return next(iter(body["content"].values())).get("schema")

    def response(self, op: Operation, status: int) -> dict[str, Any] | None:
        responses = op.spec["responses"]
        if str(status) not in responses:
            return None
        return self._resolve(responses[str(status)])  # type: ignore[no-any-return]

    def response_schema(self, op: Operation, status: int) -> Any | None:
        response = self.response(op, status)
        content = (response or {}).get("content")
        return next(iter(content.values())).get("schema") if content else None

    # ------------------------------------------------------------ 호출
    def call(
        self,
        client: httpx.Client,
        service: str,
        operation_id: str,
        *,
        expect: tuple[int, ...],
        path: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
        body: Any = None,
        idempotent: bool = False,
        headers: dict[str, str] | None = None,
    ) -> Reply:
        """계약의 작업 하나를 부르고 (1) 보낸 본문이 요청 스키마를 지키는지, (2) 상태 코드가 기대한 것이며 계약에 있는 것인지, (3) 응답이 그 상태의 스키마를 지키는지 본다."""
        op = self.operations[(service, operation_id)]
        if body is not None:
            schema = self.request_schema(op)
            if schema is not None and (errors := self.schema_errors(self.validator(schema), body)):
                raise StepFailure(f"{operation_id}: 보내려던 요청 본문이 계약을 어겼다(시험 코드의 결함): {errors}")
        url = op.path.format(**(path or {}))
        sent = dict(headers or {})
        if idempotent:
            sent["Idempotency-Key"] = str(uuid.uuid4())  # 왜 uuid4: 계약 IdempotencyKeyValue 는 재전송을 가리는 임의의 값이다
        response = client.request(op.method, url, params=query, json=body, headers=sent)
        try:
            parsed: Any = response.json() if response.content else None
        except ValueError:
            parsed = response.text
        reply = Reply(response.status_code, parsed, response.headers)
        if reply.status not in expect:
            raise StepFailure(f"{operation_id}: 상태 {reply.status}(기대 {list(expect)}) {str(parsed)[:300]}")
        if self.response(op, reply.status) is None:
            raise StepFailure(f"{operation_id}: 상태 {reply.status} 는 계약에 없다")
        schema = self.response_schema(op, reply.status)
        if schema is not None and (errors := self.schema_errors(self.validator(schema), parsed)):
            raise StepFailure(f"{operation_id}: 응답이 계약({reply.status})을 어겼다: {errors}")
        return reply
