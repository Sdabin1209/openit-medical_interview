"""link_model_client: model-runtime 에 추출·응답 문장을 요청한다(N03, N04).

나가는 호출은 영역 게이트웨이의 CONNECT 터널(OPENIT_EGRESS_PROXY)로만 간다(D128). 영역 사이 호출은 mTLS(우리 클라이언트
인증서, 루트 인증서로 서버 검증)와 기계 토큰(client credentials 로 받은 JWT, ADR 0014)이다.
계약 값 검증은 받는 쪽(model-runtime)이 한 번 했으므로 응답을 계약 타입으로 읽을 뿐 의미를 다시 검사하지 않는다(R7).
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import httpx
from httpx_sse import EventSource, SSEError
from prometheus_client import Histogram
from pydantic import ValidationError

from survey_service.contract.models import (
    ExtractionRequest,
    ExtractionResult,
    ModelStatus,
    ResponseDeltaEvent,
    ResponseGenerationRequest,
    ResponseResult,
    ResponseResultEvent,
)
from survey_service.link.machine_token import MachineTokenSource, TokenError
from survey_service.link.tls import ClientTls
from survey_service.types import Limits, ModelCallError, ModelCallFailure

# 왜 이 지표: 계약 RequiredPrometheusMetric(model_call_duration_seconds, 라벨 op). 호출 시간 히스토그램(초)
MODEL_CALL_SECONDS = Histogram("model_call_duration_seconds", "model-runtime 호출 시간(초)", ["op"])
# 왜 30초: 모델 적재 상태는 활성화 때만 바뀌므로 턴마다 읽지 않는다. 값은 측정하지 않은 선택이다(ADR 0012)
STATUS_CACHE = timedelta(seconds=30)


class HttpModelClient:
    """ModelPort 의 HTTP 구현."""

    def __init__(
        self,
        base_url: str,
        tokens: MachineTokenSource,
        limits: Limits,
        *,
        egress_proxy: str | None,
        tls: ClientTls | None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._limits = limits
        self._tokens = tokens
        self._tls = tls
        self._status: tuple[float, str | None] | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url,
            proxy=egress_proxy if transport is None else None,
            verify=tls.context if tls is not None and transport is None else True,
            transport=transport,
        )

    async def _headers(self) -> dict[str, str]:
        """요청 머리글. 왜 매번: 토큰은 만료 전에 갱신되고 클라이언트 인증서는 파일이 바뀌면 다시 올린다(ADR 0015)."""
        if self._tls is not None:
            self._tls.refresh()
        try:
            return {"Authorization": f"Bearer {await self._tokens.token()}"}
        except TokenError as error:
            raise ModelCallError(ModelCallFailure.UNAVAILABLE) from error

    async def _post(self, op: str, path: str, body: str, seconds: int) -> Any:  # noqa: ANN401
        started = time.monotonic()
        try:
            headers = {**await self._headers(), "Content-Type": "application/json"}
            response = await self._client.post(path, content=body, headers=headers, timeout=float(seconds))
        except httpx.TimeoutException as error:
            raise ModelCallError(ModelCallFailure.DEADLINE) from error
        except httpx.HTTPError as error:
            raise ModelCallError(ModelCallFailure.UNAVAILABLE) from error
        finally:
            MODEL_CALL_SECONDS.labels(op=op).observe(time.monotonic() - started)
        if response.status_code == 401:
            self._tokens.invalidate()  # 왜: 토큰이 취소됐거나 발급자가 키를 돌렸을 수 있다. 다음 호출이 새로 받는다
        if response.status_code != 200:
            # 왜 상태·사유를 구분하지 않나: OUTPUT_INVALID, MODEL_NOT_LOADED, QUESTION_BANK_VERSION_MISMATCH
            # 모두 턴은 실패 신호로 끝난다
            raise ModelCallError(ModelCallFailure.UNAVAILABLE)
        return response

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        body = request.model_dump_json(exclude_none=True)
        response = await self._post("extract", "/v1/extractions", body, self._limits.extract_seconds)
        try:
            return ExtractionResult.model_validate_json(response.content)
        except ValidationError as error:
            raise ModelCallError(ModelCallFailure.UNAVAILABLE) from error

    async def respond(self, request: ResponseGenerationRequest) -> ResponseResult:
        body = request.model_dump_json(exclude_none=True)
        response = await self._post("respond", "/v1/responses", body, self._limits.respond_seconds)
        try:
            return ResponseResult.model_validate_json(response.content)
        except ValidationError as error:
            raise ModelCallError(ModelCallFailure.UNAVAILABLE) from error

    async def respond_stream(
        self, request: ResponseGenerationRequest, on_delta: Callable[[str], Awaitable[None]]
    ) -> ResponseResult:
        """generateResponseStream 을 부르고 SSE 를 읽는다. 조각은 받는 대로 on_delta 로 넘기고(모으지 않는다) result 를
        돌려준다. error 이벤트나 result 없이 끝난 스트림은 JSON 작업의 503 과 같이 UNAVAILABLE 이다.
        모델 출력은 다시 검증하지 않는다(R7): 이벤트를 계약 타입으로 읽을 뿐이다."""
        started = time.monotonic()
        body = request.model_dump_json(exclude_none=True)
        try:
            # 왜 asyncio.timeout: httpx 의 timeout 은 읽기 한 번마다라서 조각이 계속 오면 끝나지 않는다.
            # 계약 8항은 상한을 마지막 이벤트까지에 건다(RespondClientLimitSeconds)
            async with asyncio.timeout(self._limits.respond_seconds):
                headers = {**await self._headers(), "Content-Type": "application/json", "Accept": "text/event-stream"}
                async with self._client.stream("POST", "/v1/responses/stream", content=body, headers=headers) as reply:
                    if reply.status_code == 401:
                        self._tokens.invalidate()
                    if reply.status_code != 200:
                        raise ModelCallError(ModelCallFailure.UNAVAILABLE)
                    # 왜 EventSource 를 직접 쓰나: aconnect_sse 와 달리 상태 코드를 먼저 우리가 판정한다
                    async for event in EventSource(reply).aiter_sse():
                        if event.event == "delta":
                            await on_delta(ResponseDeltaEvent.model_validate_json(event.data).text.root)
                        elif event.event == "result":
                            return ResponseResultEvent.model_validate_json(event.data).result
                        elif event.event == "error":
                            raise ModelCallError(ModelCallFailure.UNAVAILABLE)
                        # 그 밖의 이벤트 이름은 WHATWG HTML 9.2.6 대로 무시한다
        except TimeoutError as error:
            raise ModelCallError(ModelCallFailure.DEADLINE) from error
        except httpx.TimeoutException as error:
            raise ModelCallError(ModelCallFailure.DEADLINE) from error
        except (httpx.HTTPError, SSEError, ValidationError) as error:
            raise ModelCallError(ModelCallFailure.UNAVAILABLE) from error
        finally:
            MODEL_CALL_SECONDS.labels(op="respond_stream").observe(time.monotonic() - started)
        raise ModelCallError(ModelCallFailure.UNAVAILABLE)  # result 도 error 도 없이 끝났다(끊김)

    async def model_io_version(self) -> str | None:
        """활성 모델 패키지의 입출력 버전. 알 수 없으면 None(그러면 v3 의존 기능은 꺼진 채로 둔다)."""
        now = time.monotonic()
        if self._status is not None and now - self._status[0] < STATUS_CACHE.total_seconds():
            return self._status[1]
        version: str | None = None
        try:
            response = await self._client.get(
                "/v1/model-status", headers=await self._headers(), timeout=float(self._limits.extract_seconds)
            )
            if response.status_code == 401:
                self._tokens.invalidate()
            if response.status_code == 200:
                status = ModelStatus.model_validate_json(response.content)
                version = status.model_io_version.value if status.model_io_version is not None else None
        except (httpx.HTTPError, ValidationError, ModelCallError):
            version = None
        self._status = (now, version)
        return version

    async def close(self) -> None:
        await self._client.aclose()
