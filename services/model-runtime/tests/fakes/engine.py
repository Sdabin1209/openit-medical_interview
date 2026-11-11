"""시험용 추론 엔진: vLLM 의 OpenAI 호환 서버 중 이 영역이 쓰는 부분(채팅 완성, 어댑터 올리기·내리기, 건강 확인)을 흉내
낸다.

GPU 가 없는 환경에서 추론 엔진 자리를 채운다. 답은 시험이 정한다(answer 함수). 받은 요청은 calls 에 남겨 글자 단위로
대조한다.
"""

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse


@dataclass
class Call:
    adapter: str
    system: str
    user: str
    max_tokens: int
    temperature: float
    response_format: dict[str, Any] | None
    chat_template_kwargs: dict[str, Any] | None = None
    stream: bool = False


@dataclass
class FakeEngine:
    """answer(adapter, user) 가 모델이 낸 글자를 정한다."""

    answer: Callable[[str, str], str] = lambda _adapter, _user: ""
    loaded: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    calls: list[Call] = field(default_factory=lambda: list[Call]())
    healthy: bool = True
    base_model: str = "Qwen/Qwen3-8B"  # 엔진이 서빙하는 기반 모델(vLLM 의 `--model`)
    refuse_load: bool = False
    split: Callable[[str], list[str]] = lambda text: [
        text[i : i + 2] for i in range(0, len(text), 2)
    ]  # stream=True 의 조각
    unloaded: list[str] = field(default_factory=lambda: list[str]())

    def app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/health")
        async def health() -> PlainTextResponse:  # pyright: ignore[reportUnusedFunction]
            return PlainTextResponse("", status_code=200 if self.healthy else 503)

        @app.get("/v1/models")
        async def models() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
            names = [self.base_model, *self.loaded]
            return JSONResponse({"object": "list", "data": [{"id": name, "object": "model"} for name in names]})

        @app.post("/v1/load_lora_adapter")
        async def load(request: Request) -> PlainTextResponse:  # pyright: ignore[reportUnusedFunction]
            body = await request.json()
            path = Path(body["lora_path"])
            if self.refuse_load or not (path / "adapter_config.json").is_file():
                return PlainTextResponse("cannot load", status_code=400)
            self.loaded[body["lora_name"]] = str(path)
            return PlainTextResponse(f"Success: LoRA adapter '{body['lora_name']}' added successfully.")

        @app.post("/v1/unload_lora_adapter")
        async def unload(request: Request) -> PlainTextResponse:  # pyright: ignore[reportUnusedFunction]
            name = (await request.json())["lora_name"]
            self.unloaded.append(name)
            if self.loaded.pop(name, None) is None:
                return PlainTextResponse("not found", status_code=404)
            return PlainTextResponse("Success")

        @app.post("/v1/chat/completions")
        async def chat(request: Request) -> Response:  # pyright: ignore[reportUnusedFunction]
            body = await request.json()
            system, user = body["messages"][0]["content"], body["messages"][1]["content"]
            if body["model"] not in self.loaded:
                return JSONResponse(
                    {"error": {"message": "model not found", "type": "NotFoundError", "code": 404}}, status_code=404
                )
            self.calls.append(
                Call(
                    body["model"],
                    system,
                    user,
                    body["max_tokens"],
                    body["temperature"],
                    body.get("response_format"),
                    body.get("chat_template_kwargs"),
                    bool(body.get("stream")),
                )
            )
            text = self.answer(body["model"], user)
            if body.get("stream"):
                return StreamingResponse(self._chunks(body["model"], text), media_type="text/event-stream")
            return JSONResponse(
                {
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "created": 0,
                    "model": body["model"],
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
            )

        return app

    def _chunks(self, model: str, text: str) -> Iterator[str]:
        """OpenAI 호환 스트림(chat.completion.chunk 들과 [DONE])."""

        def chunk(delta: dict[str, Any], finish: str | None) -> str:
            body = {
                "id": "chatcmpl-test",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"

        yield chunk({"role": "assistant", "content": ""}, None)
        for piece in self.split(text):
            yield chunk({"content": piece}, None)
        yield chunk({}, "stop")
        yield "data: [DONE]\n\n"


def dump(value: object) -> str:
    """모델 출력 글자(정렬된 키, 학습 정답과 같은 모양)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
