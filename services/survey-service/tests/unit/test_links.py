"""이웃·IdP 호출(link): model-runtime 클라이언트, JWKS, 기계 토큰 표."""

import base64
import json
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from tests.support.harness import DIGEST
from tests.unit.test_settings_health import REQUIRED

from survey_service.contract.models import ExtractionRequest, ResponseGenerationRequest
from survey_service.link.auth import JwksKeys, load_machine_credentials
from survey_service.link.model_client import HttpModelClient
from survey_service.link.problem import ApiError
from survey_service.settings import limits_of, load_env
from survey_service.types import ModelCallError, ModelCallFailure

pytestmark = pytest.mark.anyio
LIMITS = limits_of(load_env(REQUIRED))


def extraction_request() -> ExtractionRequest:
    return ExtractionRequest.model_validate(
        {
            "runtime_contract_version": 1,
            "question_id": "Q1",
            "current_question": "질문",
            "user_utterance": "네",
            "slots": [],
            "flow": {"start_item": "Q1", "rules": [{"item_id": "Q1", "branches": [{"next_item": "END"}]}]},
            "fields": [{"item_id": "Q1", "field_name": "answer", "data_type": "boolean"}],
        }
    )


def client(handler: httpx.MockTransport) -> HttpModelClient:
    return HttpModelClient(
        "https://model-runtime", "secret-token", LIMITS, egress_proxy=None, root_certificate=None, transport=handler
    )


async def test_model_client_posts_contract_bodies_with_bearer_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/extractions":
            return httpx.Response(
                200, json={"package_digest": DIGEST, "output": {"values": [], "action": "NEXT", "next_item": "END"}}
            )
        return httpx.Response(200, json={"package_digest": DIGEST, "text": "문장"})

    model = client(httpx.MockTransport(handler))
    extracted = await model.extract(extraction_request())
    responded = await model.respond(
        ResponseGenerationRequest.model_validate(
            {
                "runtime_contract_version": 1,
                "action": "START",
                "next": {"type": "NEXT", "question_id": "Q1", "text": "질문"},
            }
        )
    )
    assert extracted.output.action.value == "NEXT" and responded.text.root == "문장"
    assert [r.url.path for r in seen] == ["/v1/extractions", "/v1/responses"]
    assert all(r.headers["authorization"] == "Bearer secret-token" for r in seen)
    assert "null" not in seen[0].content.decode()  # 값이 없는 칸은 싣지 않는다
    await model.close()


@pytest.mark.parametrize("status", [400, 409, 503, 500])
async def test_model_errors_become_unavailable(status: int) -> None:
    model = client(httpx.MockTransport(lambda _r: httpx.Response(status, json={"status": status})))
    with pytest.raises(ModelCallError) as error:
        await model.extract(extraction_request())
    assert error.value.failure is ModelCallFailure.UNAVAILABLE


async def test_model_timeout_connection_and_garbage() -> None:
    def timeout(_r: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    def refused(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with pytest.raises(ModelCallError) as late:
        await client(httpx.MockTransport(timeout)).extract(extraction_request())
    assert late.value.failure is ModelCallFailure.DEADLINE
    with pytest.raises(ModelCallError) as down:
        await client(httpx.MockTransport(refused)).extract(extraction_request())
    assert down.value.failure is ModelCallFailure.UNAVAILABLE
    with pytest.raises(ModelCallError):
        await client(httpx.MockTransport(lambda _r: httpx.Response(200, json={"nonsense": 1}))).extract(
            extraction_request()
        )


async def test_model_io_version_is_cached_and_failure_is_unknown() -> None:
    calls = {"n": 0}

    def handler(_r: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"state": "READY", "model_io_version": "model-io-v2"})

    model = client(httpx.MockTransport(handler))
    assert await model.model_io_version() == "model-io-v2" and await model.model_io_version() == "model-io-v2"
    assert calls["n"] == 1
    broken = client(httpx.MockTransport(lambda _r: httpx.Response(503)))
    assert await broken.model_io_version() is None


async def test_jwks_discovery_refetch_limit_and_unknown_kid() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = key.public_key().public_numbers()

    def b64(value: int) -> str:
        return base64.urlsafe_b64encode(value.to_bytes((value.bit_length() + 7) // 8, "big")).decode().rstrip("=")

    jwk = {"kty": "RSA", "n": b64(numbers.n), "e": b64(numbers.e), "kid": "k1", "use": "sig"}
    fetched: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(request.url.path)
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json={"jwks_uri": "https://platform/certs"})
        return httpx.Response(200, json={"keys": [jwk]})

    now = {"t": 1000.0}
    keys = JwksKeys(
        "https://platform/realms/openit/",
        None,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        clock=lambda: now["t"],
    )
    assert await keys("k1") is not None and fetched == ["/realms/openit/.well-known/openid-configuration", "/certs"]
    assert await keys("k1") is not None and len(fetched) == 2  # 캐시
    with pytest.raises(ApiError):
        await keys("unknown")
    assert len(fetched) == 2  # 60초 안에는 모르는 kid 로 IdP 를 다시 두드리지 않는다
    now["t"] += 61
    with pytest.raises(ApiError):
        await keys("unknown")
    assert len(fetched) == 4
    only = JwksKeys(
        "https://platform/realms/openit",
        "https://platform/certs",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    assert await only(None) is not None  # 키가 하나뿐이면 kid 없는 토큰도 그 키로


async def test_jwks_fetch_failure_is_401() -> None:
    keys = JwksKeys(
        "https://platform/realms/openit",
        "https://platform/certs",
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(500))),
    )
    with pytest.raises(ApiError) as error:
        await keys("k1")
    assert error.value.status == 401


def test_machine_token_table_is_read_from_files(tmp_path: Path) -> None:
    token = tmp_path / "hospital.token"
    token.write_text("abc123\n", encoding="utf-8")
    table = tmp_path / "machines.json"
    table.write_text(
        json.dumps({"tokens": [{"client": "hospital", "roles": ["result-reader"], "token_file": str(token)}]}),
        encoding="utf-8",
    )
    (credential,) = load_machine_credentials(str(table))
    assert credential.client == "hospital" and credential.roles == {"result-reader"} and credential.token == b"abc123"
    table.write_text(
        json.dumps({"tokens": [{"client": "Bad Name", "roles": [], "token_file": str(token)}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="client"):
        load_machine_credentials(str(table))
