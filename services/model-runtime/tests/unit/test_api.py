"""link_api: 오류는 problem+json(RFC 9457), 요청 검증은 400 과 칸 위치, 건강 확인과 지표."""

from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest

from fakes.engine import FakeEngine
from fakes.pki import make_pki
from scenario.world import A_NEXT, bank
from support import MACHINE_TOKEN, Identity, make_app, settings_for

pytestmark = pytest.mark.anyio
IDENTITY = Identity.new()


def client(tmp_path: Path, engine: FakeEngine | None = None) -> httpx.AsyncClient:
    pki = make_pki(tmp_path / "pki")
    app = make_app(settings_for(tmp_path, pki, "https://registry.invalid"), pki, IDENTITY, engine or FakeEngine())
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://model-runtime")


def machine() -> dict[str, str]:
    return {"Authorization": f"Bearer {MACHINE_TOKEN}"}


def body(**override: Any) -> dict[str, Any]:  # noqa: ANN401
    value: dict[str, Any] = {
        "runtime_contract_version": 1,
        "input": A_NEXT,
        "state_key_order": list[str](),
        "flow": bank()["flow"],
        "fields": bank()["fields"],
    }
    value.update(override)
    return value


async def test_every_error_is_problem_json_with_reason_and_instance(tmp_path: Path) -> None:
    async with client(tmp_path) as http:
        response = await http.post("/v1/extractions", json=body(), headers=machine())
    assert response.status_code == 503 and response.headers["content-type"] == "application/problem+json"
    assert response.headers["retry-after"] == "5"
    assert response.json() == {
        "type": "https://openit/problems/MODEL_NOT_LOADED",
        "title": "모델 패키지를 아직 적재하지 못했다",
        "status": 503,
        "detail": "활성 모델 패키지가 적재되지 않았다",
        "instance": "/v1/extractions",
        "reason": "MODEL_NOT_LOADED",
    }


async def test_missing_and_wrong_credentials_are_401_with_challenge(tmp_path: Path) -> None:
    async with client(tmp_path) as http:
        anonymous = await http.post("/v1/extractions", json=body())
        wrong = await http.get("/v1/model-status", headers={"Authorization": "Bearer nope"})
    for response in (anonymous, wrong):
        assert response.status_code == 401 and response.headers["www-authenticate"].startswith("Bearer")
        assert response.headers["content-type"] == "application/problem+json"


async def test_authentication_comes_before_body_validation(tmp_path: Path) -> None:
    async with client(tmp_path) as http:
        response = await http.post("/v1/extractions", content=b"{not json")
    assert response.status_code == 401


async def test_invalid_body_is_400_with_pointers_and_without_input_values(tmp_path: Path) -> None:
    private_utterance = "환자가 말한 비밀 발화 내용"
    bad = body(input={**A_NEXT, "user_utterance": private_utterance, "question_id": "!!"})
    async with client(tmp_path) as http:
        response = await http.post("/v1/extractions", json=bad, headers=machine())
    assert response.status_code == 400
    errors = response.json()["errors"]
    assert any(item["pointer"] == "/input/question_id" for item in errors)
    assert private_utterance not in response.text and "!!" not in response.text


async def test_non_json_body_is_400(tmp_path: Path) -> None:
    async with client(tmp_path) as http:
        response = await http.post("/v1/responses", content=b"{not json", headers=machine())
    assert response.status_code == 400 and response.json()["detail"] == "본문이 JSON 이 아니다"


async def test_bad_digest_in_path_is_400(tmp_path: Path) -> None:
    async with client(tmp_path) as http:
        response = await http.get(
            "/v1/model-packages/not-a-digest", headers={"Authorization": f"Bearer {IDENTITY.token(['operator'])}"}
        )
    assert response.status_code == 400 and response.json()["errors"][0]["pointer"] == "/path/package_digest"


async def test_machine_token_cannot_activate(tmp_path: Path) -> None:
    async with client(tmp_path) as http:
        response = await http.post(
            "/v1/model-activations", json={"package_digest": "sha256:" + "a" * 64, "reason": "x"}, headers=machine()
        )
    assert response.status_code == 401  # 활성화는 사람(OIDC)만


async def test_health_and_metrics(tmp_path: Path) -> None:
    engine = FakeEngine()
    async with client(tmp_path, engine) as http:
        assert (await http.get("/healthz")).json() == {"status": "pass", "service": "model-runtime"}
        ready = await http.get("/readyz")
        assert ready.status_code == 200 and [c["name"] for c in ready.json()["checks"]] == ["store", "engine"]
        engine.healthy = False
        down = await http.get("/readyz")
        assert down.status_code == 503 and down.json()["detail"] == "준비되지 않은 점검: engine"
        metrics = await http.get("/metrics")
    assert metrics.headers["content-type"].startswith("text/plain")
    assert "# TYPE model_call_duration_seconds histogram" in metrics.text
