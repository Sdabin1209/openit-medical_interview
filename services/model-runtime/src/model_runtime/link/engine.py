"""추론 엔진(vLLM 의 OpenAI 호환 서버)과 통신하는 길. ChatEngine 과 AdapterRegistry 포트의 구현이다.

채팅 완성은 OpenAI 호환 API 표준 클라이언트(openai SDK)로 부르고, 어댑터를 올리고 내리는 일은 vLLM 의
런타임 LoRA 갱신 API(`/v1/load_lora_adapter`, `/v1/unload_lora_adapter`)로 한다. 표준 OpenAI API 에는 어댑터 갱신이
없다.
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import httpx2 as httpx
import openai
from openai.types.chat import ChatCompletionMessageParam

from model_runtime.types import ChatRequest, EngineError

# 왜 상수: OpenAI SDK 는 키가 비어 있으면 거부한다. vLLM 은 `--api-key` 를 주지 않으면 키를 확인하지 않는다(비밀이
# 아니다)
_NO_KEY = "none"
_JSON_SCHEMA_NAME = "ActionExtraction"


class VllmEngine:
    """vLLM OpenAI 호환 서버 하나와 이야기한다."""

    def __init__(self, base_url: str, base_model: str, http_client: httpx.AsyncClient | None = None) -> None:
        self._base_model = base_model  # 프로파일 표의 기반 모델. 엔진이 이 모델을 서빙해야 준비된 것이다(ADR 0007)
        self._http = http_client or httpx.AsyncClient(
            timeout=None
        )  # 왜 None: 시간 상한은 inference 컴포넌트가 계약 값으로 건다
        self._base_url = base_url.rstrip("/")
        self._client = openai.AsyncOpenAI(
            base_url=f"{self._base_url}/v1", api_key=_NO_KEY, http_client=self._http, max_retries=0
        )

    async def complete(self, request: ChatRequest) -> str:
        """채팅 완성을 한 번 부른다. 제약 디코딩이면 출력 스키마를 response_format 으로 싣는다."""
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.user},
        ]
        try:
            if request.json_schema is None:
                reply = await self._client.chat.completions.create(
                    model=request.adapter,
                    messages=messages,
                    max_tokens=request.max_new_tokens,
                    temperature=request.temperature,
                )
            else:
                reply = await self._client.chat.completions.create(
                    model=request.adapter,
                    messages=messages,
                    max_tokens=request.max_new_tokens,
                    temperature=request.temperature,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {"name": _JSON_SCHEMA_NAME, "schema": dict(request.json_schema)},
                    },
                )
        except (openai.OpenAIError, httpx.HTTPError) as error:
            raise EngineError("추론 엔진 호출이 실패했다") from error
        content = reply.choices[0].message.content if reply.choices else None
        if not content:
            raise EngineError("추론 엔진이 빈 답을 냈다")
        return content

    async def healthy(self) -> bool:
        """엔진이 살아 있고 프로파일의 기반 모델을 서빙하는가. /readyz 의 engine 점검이 쓴다.

        살아 있음은 vLLM 의 `/health`, 기반 모델은 OpenAI 호환 `GET /v1/models` 의 모델 목록으로 본다(엔진은 시작할 때 정한
        기반 모델 하나를 서빙하고 런타임에 바꿀 수 없어서, 이 서비스가 엔진에 기반 모델을 알릴 길은 없고 확인만 할 수 있다).
        """
        try:
            if (await self._http.get(f"{self._base_url}/health")).status_code != HTTPStatus.OK:
                return False
            listed = await self._http.get(f"{self._base_url}/v1/models")
            return listed.status_code == HTTPStatus.OK and any(
                item.get("id") == self._base_model for item in listed.json().get("data", [])
            )
        except (httpx.HTTPError, ValueError, AttributeError):
            return False

    async def load_adapter(self, name: str, path: Path) -> None:
        """어댑터 폴더를 name 으로 올린다. 엔진이 읽을 수 있는 경로여야 한다(같은 볼륨을 같은 경로로 마운트한다)."""
        try:
            response = await self._http.post(
                f"{self._base_url}/v1/load_lora_adapter", json={"lora_name": name, "lora_path": str(path)}
            )
        except httpx.HTTPError as error:
            raise EngineError("추론 엔진에 닿지 못했다") from error
        if response.status_code != HTTPStatus.OK:
            raise EngineError(f"추론 엔진이 어댑터 적재를 {response.status_code} 로 거절했다")

    async def unload_adapter(self, name: str) -> None:
        """name 의 어댑터를 내린다. 없는 이름(404)이나 연결 실패는 무시한다(정리 단계라 실패해도 서비스를 막지
        않는다)."""
        try:
            await self._http.post(f"{self._base_url}/v1/unload_lora_adapter", json={"lora_name": name})
        except httpx.HTTPError:
            return
