"""link_model_client: model-runtime 에 추출·응답 문장을 요청한다(N03, N04).

나가는 호출은 영역 게이트웨이의 CONNECT 터널(OPENIT_EGRESS_PROXY)로만 간다(D128). 영역 사이 호출은 TLS 와 기계 토큰이다.
계약 값 검증은 받는 쪽(model-runtime)이 한 번 했으므로 응답을 계약 타입으로 읽을 뿐 의미를 다시 검사하지 않는다(R7).
"""

import time
from datetime import timedelta
from typing import Any

import httpx
from prometheus_client import Histogram
from pydantic import ValidationError

from survey_service.contract.models import (
    ExtractionRequest,
    ExtractionResult,
    ModelStatus,
    ResponseGenerationRequest,
    ResponseResult,
)
from survey_service.types import Limits, ModelCallError, ModelCallFailure

# 왜 이 지표: 계약 RequiredPrometheusMetric(model_call_duration_seconds, 라벨 op). 호출 시간 히스토그램(초)
MODEL_CALL_SECONDS = Histogram("model_call_duration_seconds", "model-runtime 호출 시간(초)", ["op"])
# 왜 30초: 모델 적재 상태는 활성화 때만 바뀌므로 턴마다 읽지 않는다. 값은 측정하지 않은 선택이다(ADR 0003)
STATUS_CACHE = timedelta(seconds=30)


class HttpModelClient:
    """ModelPort 의 HTTP 구현."""

    def __init__(
        self,
        base_url: str,
        token: str,
        limits: Limits,
        *,
        egress_proxy: str | None,
        root_certificate: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._limits = limits
        self._status: tuple[float, str | None] | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            proxy=egress_proxy if transport is None else None,
            verify=root_certificate if root_certificate and transport is None else True,
            transport=transport,
        )

    async def _post(self, op: str, path: str, body: str, seconds: int) -> Any:  # noqa: ANN401
        started = time.monotonic()
        try:
            response = await self._client.post(
                path, content=body, headers={"Content-Type": "application/json"}, timeout=float(seconds)
            )
        except httpx.TimeoutException as error:
            raise ModelCallError(ModelCallFailure.DEADLINE) from error
        except httpx.HTTPError as error:
            raise ModelCallError(ModelCallFailure.UNAVAILABLE) from error
        finally:
            MODEL_CALL_SECONDS.labels(op=op).observe(time.monotonic() - started)
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

    async def model_io_version(self) -> str | None:
        """활성 모델 패키지의 입출력 버전. 알 수 없으면 None(그러면 v3 의존 기능은 꺼진 채로 둔다)."""
        now = time.monotonic()
        if self._status is not None and now - self._status[0] < STATUS_CACHE.total_seconds():
            return self._status[1]
        version: str | None = None
        try:
            response = await self._client.get("/v1/model-status", timeout=float(self._limits.extract_seconds))
            if response.status_code == 200:
                status = ModelStatus.model_validate_json(response.content)
                version = status.model_io_version.value if status.model_io_version is not None else None
        except (httpx.HTTPError, ValidationError):
            version = None
        self._status = (now, version)
        return version

    async def close(self) -> None:
        await self._client.aclose()
