"""link_kiosk_api 의 응답 문장 스트림(Server-Sent Events): 이벤트 틀, 연결과 처리의 분리(ADR 0018).

계약 README '응답 문장 스트림' 3항: 받아들인 요청은 키오스크가 끊어도 끝까지 처리한다. 그래서 처리는 요청이 아니라
Background 가 쥔 작업에서 돌고, 응답 본문은 그 작업이 채우는 큐를 읽어 내보내기만 한다.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine

from fastapi.responses import StreamingResponse

from survey_service.link.problem import ApiError, problem_body

# 왜 이 머리글: 계약 StreamCacheControl(RFC 9111 5.2.2.5, 5.2.2.6). 저장과 변형을 막는다
# (버퍼링을 끄는 것은 게이트웨이 설정)
CACHE_CONTROL = "no-store, no-transform"
LOG = logging.getLogger(__name__)
Emit = Callable[[str], Awaitable[None]]
Produce = Callable[[Emit], Awaitable[bytes]]


def frame(event: str, data: dict[str, object]) -> bytes:
    """SSE 이벤트 하나. 왜 event 줄과 data 의 event 칸을 같게: 계약 StreamEvent* (WHATWG HTML 9.2.6).
    json.dumps 는 줄바꿈을 이스케이프하므로 data 는 한 줄이다."""
    payload = json.dumps({"event": event, **data}, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode()


def result_frame(body: dict[str, object]) -> bytes:
    return frame("result", {"result": body})


def error_frame(error: ApiError, instance: str) -> bytes:
    """JSON 작업이 4xx·5xx 로 답했을 실패를 error 이벤트로(Retry-After 를 주었을 실패면 retry_after_seconds)."""
    data: dict[str, object] = {
        "problem": problem_body(error.status, instance, reason=error.reason, detail=error.detail, errors=error.errors)
    }
    if error.retry_after is not None:
        data["retry_after_seconds"] = error.retry_after
    return frame("error", data)


class Background:
    """요청과 따로 끝까지 도는 작업을 쥔다. 왜: asyncio 는 작업을 약한 참조로만 들고 있어, 쥐지 않으면
    도중에 치워질 수 있다
    (asyncio.create_task 문서). 종료 때 drain 으로 진행 중인 처리를 마친다."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()

    def spawn(self, work: Coroutine[object, object, None]) -> None:
        task = asyncio.get_running_loop().create_task(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)


def event_stream(background: Background, instance: str, retry_after: int, produce: Produce) -> StreamingResponse:
    """처리를 Background 작업으로 띄우고, 그 작업이 내는 이벤트를 받는 대로 내보내는 200 응답을 만든다.

    produce 는 조각을 emit 으로 내고 마지막 이벤트(result 나 error 프레임)를 돌려준다."""
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def emit(text: str) -> None:
        queue.put_nowait(frame("delta", {"text": text}))

    async def work() -> None:
        try:
            last = await produce(emit)
        except ApiError as error:
            last = error_frame(error, instance)
        except Exception:
            # 왜 error 로 닫나: 헤더를 이미 보냈으므로 상태 코드를 바꿀 수 없고, 닫지 않으면 키오스크가 끝없이 기다린다
            LOG.exception("응답 문장 스트림 처리 중 예기치 못한 실패")
            last = error_frame(ApiError(503, retry_after=retry_after), instance)
        queue.put_nowait(last)
        queue.put_nowait(None)

    async def body() -> AsyncGenerator[bytes]:
        while (chunk := await queue.get()) is not None:
            yield chunk

    background.spawn(work())
    return StreamingResponse(body(), media_type="text/event-stream", headers={"Cache-Control": CACHE_CONTROL})
