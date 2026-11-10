"""가짜 엔진 시나리오: package_publish(로컬 레지스트리) → 패키지 적재 → 활성화 → 추출(정상, 위반 → 출력 불가, 고쳐 쓰기)
→ 응답 문장 → 롤백. 레지스트리와 엔진은 실제 소켓의 시험용 서버, 인증은 실제 JWT 검증이다."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from model_io import compose_response_from_request, serialize_extraction_input, serialize_response_input

from fakes.engine import dump
from scenario.world import (
    A_BAD,
    A_NEXT,
    A_NEXT_GOLD,
    A_SKIP,
    B_REQUEST,
    B_START,
    SYSTEM_A,
    SYSTEM_B,
    World,
    a_key,
    ask,
    bank,
    world,
)
from support import Identity, make_app, settings_for

pytestmark = pytest.mark.anyio


@asynccontextmanager
async def serving(
    w: World, identity: Identity, cache: Path | None = None
) -> AsyncGenerator[tuple[httpx.AsyncClient, Any]]:
    """앱을 시작해(저장된 기록에서 활성 패키지를 스스로 적재한다) 호출 클라이언트를 낸다."""
    settings = settings_for(w.tmp, w.pki, w.registry_url, **({"model_cache_dir": cache} if cache else {}))
    app = make_app(settings, w.pki, identity, w.engine)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://model-runtime") as client,
    ):
        yield client, app


def machine(identity: Identity) -> dict[str, str]:
    return {"Authorization": f"Bearer {identity.machine_token()}"}


def human(identity: Identity, *roles: str, sub: str = "approver-1") -> dict[str, str]:
    return {"Authorization": f"Bearer {identity.token(list(roles), sub=sub)}"}


def extraction_body(payload: dict[str, Any], version: int = 1) -> dict[str, Any]:
    return {"runtime_contract_version": version, **ask(payload), "flow": bank()["flow"], "fields": bank()["fields"]}


async def settle(app: Any) -> None:  # noqa: ANN401
    await app.state.runtime.wait_idle()


async def test_publish_load_activate_extract_respond_rollback(tmp_path: Path) -> None:
    identity = Identity.new()
    with world(tmp_path) as w:
        first = await anyio.to_thread.run_sync(
            lambda: w.publish("one")
        )  # 도구는 자기 이벤트 루프를 쓰므로 다른 스레드에서 돌린다
        second = await anyio.to_thread.run_sync(lambda: w.publish("two", prompt_suffix=" (둘째)"))
        assert first.startswith("sha256:") and second != first
        assert first in {f"sha256:{k[7:]}" for k in w.registry.manifests}  # 레지스트리가 digest 로 저장했다

        # 평가 보고서: 의미 위반율은 고쳐 쓰기 전 출력으로 센다(세 표본 중 하나가 일부러 틀렸다)
        report = json.loads((tmp_path / "publish-one" / "report.json").read_text(encoding="utf-8"))
        metrics = {(m["name"], m.get("slice")): (m["value"], m["sample_count"]) for m in report["metrics"]}
        assert metrics[("semantic_violation_rate", None)] == (pytest.approx(1 / 3), 3)
        assert metrics[("semantic_violation_rate", "violation_code=NEXT_ITEM_MISMATCH")][0] == pytest.approx(1 / 3)
        assert metrics[("value_recall", None)] == (1.0, 4)
        assert metrics[("next_item_accuracy", "action=NEXT")] == (pytest.approx(2 / 3), 3)

        async with serving(w, identity) as (client, app):
            # 적재 전: 상태는 NOT_LOADED, 추론은 503 MODEL_NOT_LOADED
            status = (await client.get("/v1/model-status", headers=machine(identity))).json()
            assert status == {"state": "NOT_LOADED"}
            early = await client.post("/v1/extractions", json=extraction_body(A_NEXT), headers=machine(identity))
            assert (
                early.status_code == 503
                and early.json()["reason"] == "MODEL_NOT_LOADED"
                and "retry-after" in early.headers
            )

            # 활성화 승인은 release-approver 의 접근 토큰. 승인자는 토큰의 sub 에서 얻는다
            listed = await client.get(f"/v1/model-packages/{first}", headers=human(identity, "operator"))
            assert listed.status_code == 200 and listed.json()["base_model"] == "Qwen/Qwen3-8B"
            # 게시된 패키지 목록(태그 목록과 매니페스트 조회): 승인자가 digest 를 직접 입력하지 않고 고른다
            catalog = await client.get("/v1/model-packages", headers=human(identity, "operator"))
            assert catalog.status_code == 200
            assert {(i["package_digest"], i["is_active"]) for i in catalog.json()["items"]} == {
                (first, False),
                (second, False),
            }
            page = await client.get("/v1/model-packages?limit=1", headers=human(identity, "release-approver"))
            assert len(page.json()["items"]) == 1 and "next_cursor" in page.json()
            rest = await client.get(
                f"/v1/model-packages?limit=1&cursor={page.json()['next_cursor']}", headers=human(identity, "operator")
            )
            assert {page.json()["items"][0]["package_digest"], rest.json()["items"][0]["package_digest"]} == {
                first,
                second,
            }
            assert "next_cursor" not in rest.json()
            assert (
                await client.get("/v1/model-packages?limit=0", headers=human(identity, "operator"))
            ).status_code == 400
            assert (
                await client.get("/v1/model-packages?cursor=!!", headers=human(identity, "operator"))
            ).status_code == 400
            assert (await client.get("/v1/model-packages", headers=machine(identity))).status_code == 403
            assert (await client.get("/v1/model-packages")).status_code == 401
            denied = await client.post(
                "/v1/model-activations",
                json={"package_digest": first, "reason": "시험"},
                headers=human(identity, "operator"),
            )
            assert denied.status_code == 403
            accepted = await client.post(
                "/v1/model-activations",
                json={"package_digest": first, "reason": "평가 보고서 확인"},
                headers=human(identity, "release-approver", sub="user-7"),
            )
            assert accepted.status_code == 202 and accepted.json()["package_digest"] == first
            await settle(app)
            status = (await client.get("/v1/model-status", headers=machine(identity))).json()
            assert (
                status["state"] == "READY" and status["package_digest"] == first and status["activated_by"] == "user-7"
            )
            assert status["runtime_contract_version"] == 1 and status["model_io_version"] == "model-io-v2"
            active = (await client.get("/v1/model-packages", headers=human(identity, "operator"))).json()["items"]
            assert {i["package_digest"] for i in active if i["is_active"]} == {
                first
            }  # 활성 여부는 활성화 기록과 맞춘다
            again = await client.post(
                "/v1/model-activations",
                json={"package_digest": first, "reason": "다시"},
                headers=human(identity, "release-approver"),
            )
            assert again.status_code == 200  # 이미 활성인 digest 의 활성화는 멱등

            # 추출(정상): 모델 입력 글자는 학습 데이터와 같은 직렬화다. 시스템 프롬프트는 패키지의 것이다
            ok = await client.post("/v1/extractions", json=extraction_body(A_NEXT), headers=machine(identity))
            assert ok.status_code == 200
            assert ok.json() == {"package_digest": first, "output": A_NEXT_GOLD}
            call = w.engine.calls[-1]
            assert call.user == serialize_extraction_input(A_NEXT, list(A_NEXT["state"])) and call.system == SYSTEM_A
            assert call.temperature == 0.0 and call.response_format is None

            # 추출(고쳐 쓰기): 모델이 틀린 next_item 을 냈지만 순서표로 채워 낸다
            fixed = await client.post("/v1/extractions", json=extraction_body(A_BAD), headers=machine(identity))
            assert fixed.status_code == 200 and fixed.json()["output"]["next_item"] == "Q8_2"

            # 추출(위반 → 출력 불가): 없는 칸을 낸 출력은 값을 지어내지 않고 503 OUTPUT_INVALID
            w.answers[a_key(A_SKIP)] = dump(
                {
                    "action": "NEXT",
                    "next_item": "Q5",
                    "values": [
                        {"key": "Q4.nope", "value": True, "precision": "exact", "status": "ANSWERED", "save": True}
                    ],
                }
            )
            invalid = await client.post("/v1/extractions", json=extraction_body(A_SKIP), headers=machine(identity))
            assert (
                invalid.status_code == 503
                and invalid.json()["reason"] == "OUTPUT_INVALID"
                and "UNKNOWN_SLOT" in invalid.json()["detail"]
            )

            # 문항 은행 버전이 다르면 409
            mismatch = await client.post(
                "/v1/extractions", json=extraction_body(A_NEXT, version=2), headers=machine(identity)
            )
            assert mismatch.status_code == 409 and mismatch.json()["reason"] == "QUESTION_BANK_VERSION_MISMATCH"

            # 응답 문장
            reply = await client.post(
                "/v1/responses", json={"runtime_contract_version": 1, **B_REQUEST}, headers=machine(identity)
            )
            assert reply.status_code == 200 and reply.json() == {
                "package_digest": first,
                "text": "진단 받으셨군요. 다음 질문입니다.",
            }
            assert (
                w.engine.calls[-1].user == serialize_response_input(compose_response_from_request(B_REQUEST))
                and w.engine.calls[-1].system == SYSTEM_B
            )

            # 시작(START): 환자 말 없이 다음 문항의 topic 과 질문 문장으로 모델 입력을 만든다
            started = await client.post(
                "/v1/responses", json={"runtime_contract_version": 1, **B_START}, headers=machine(identity)
            )
            assert started.status_code == 200
            assert w.engine.calls[-1].user == serialize_response_input(compose_response_from_request(B_START))

            # 저장된 칸 목록에서 모델 입력 state 를 고른다(지금·직전·참조 원천 문항만, 서버가 정한다)
            slots = [
                {"key": "Q1.D01.diagnosed", "value": True, "status": "ANSWERED"},
                {"key": "Q9_1.days", "value": 3, "status": "ANSWERED"},
                {"key": "Q8_2.duration_minutes", "value": 30, "status": "ANSWERED"},
                {"key": "Q9_2.duration_minutes", "value": None, "status": "MISSING"},
            ]
            body = {
                **extraction_body({**A_NEXT, "question_id": "Q9_2"}),
                "slots": slots,
                "previous_question_id": "Q9_1",
            }
            await client.post(
                "/v1/extractions", json=body, headers=machine(identity)
            )  # 엔진이 빈 답을 내므로 503. 보낸 입력을 본다
            sent = json.loads(w.engine.calls[-1].user)
            assert list(sent["state"]) == ["Q9_1.days", "Q8_2.duration_minutes", "Q9_2.duration_minutes"]
            assert sent["state"]["Q9_2.duration_minutes"] == {"value": None, "status": "MISSING"}

            # 모델 입출력 v2 의 표에 없는 문항은 400
            unknown = await client.post(
                "/v1/responses",
                json={
                    "runtime_contract_version": 1,
                    **B_REQUEST,
                    "question_id": "Q99",
                    "values": [{**B_REQUEST["values"][0], "key": "Q99.x"}],
                },
                headers=machine(identity),
            )
            assert unknown.status_code == 400 and unknown.headers["content-type"] == "application/problem+json"

            # 둘째 패키지를 활성화하면 직전 패키지가 롤백 대상이 된다
            await client.post(
                "/v1/model-activations",
                json={"package_digest": second, "reason": "새 평가"},
                headers=human(identity, "release-approver"),
            )
            await settle(app)
            status = (await client.get("/v1/model-status", headers=human(identity, "operator"))).json()
            assert status["package_digest"] == second and status["previous_package_digest"] == first
            assert (
                w.engine.calls
                and (
                    await client.post("/v1/extractions", json=extraction_body(A_NEXT), headers=machine(identity))
                ).json()["package_digest"]
                == second
            )
            assert w.engine.calls[-1].system == SYSTEM_A + " (둘째)"

            # 롤백: 이전에 활성이었던 패키지로만. 아니면 409 ROLLBACK_TARGET_INVALID
            never = "sha256:" + "0" * 64
            refused = await client.post(
                "/v1/model-rollbacks",
                json={"target_package_digest": never, "reason": "시험"},
                headers=human(identity, "operator"),
            )
            assert refused.status_code == 409 and refused.json()["reason"] == "ROLLBACK_TARGET_INVALID"
            current = await client.post(
                "/v1/model-rollbacks",
                json={"target_package_digest": second, "reason": "시험"},
                headers=human(identity, "operator"),
            )
            assert current.status_code == 409
            back = await client.post(
                "/v1/model-rollbacks",
                json={"target_package_digest": first, "reason": "둘째가 느리다"},
                headers=human(identity, "operator", sub="op-3"),
            )
            assert back.status_code == 202
            await settle(app)
            status = (await client.get("/v1/model-status", headers=machine(identity))).json()
            assert status["state"] == "READY" and status["package_digest"] == first and status["activated_by"] == "op-3"
            assert status["previous_package_digest"] == second

        # 기록은 파일에 덧붙어 있고(승인자·시각·사유), 다시 시작하면 활성 패키지를 스스로 적재한다
        log = [
            json.loads(x)
            for x in (tmp_path / "cache" / "model-runtime" / "release-log.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        requested = [e for e in log if e["kind"].endswith("_REQUESTED")]
        assert [(e["kind"], e["actor"], e["reason"]) for e in requested] == [
            ("ACTIVATE_REQUESTED", "user-7", "평가 보고서 확인"),
            ("ACTIVATE_REQUESTED", "approver-1", "새 평가"),
            ("ROLLBACK_REQUESTED", "op-3", "둘째가 느리다"),
        ]
        async with serving(w, identity) as (client, app):
            await settle(app)
            status = (await client.get("/v1/model-status", headers=machine(identity))).json()
            assert status["state"] == "READY" and status["package_digest"] == first
            assert (
                await client.post("/v1/extractions", json=extraction_body(A_NEXT), headers=machine(identity))
            ).status_code == 200
