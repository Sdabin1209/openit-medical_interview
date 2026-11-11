# 0013. 응답 문장 스트림은 Starlette StreamingResponse 와 작업 큐로 낸다

## 상태
승인(2026-11-11, model-runtime 작업자). 계약 9.2.0 의 `generateResponseStream`(`POST /v1/responses/stream`)과 계약 README 의 "응답 문장 스트림" 절 1~9항을 구현한다.

## 맥락
환자에게 보이는 LoRA-B 문장을 엔진이 토큰을 내는 대로 흘려야 한다. 서버는 Server-Sent Events(WHATWG HTML 9.2)로 `delta` 를 0개 이상 보낸 뒤 `result` 나 `error` 하나로 끝낸다. 받아들인 요청은 클라이언트가 끊어도 끝까지 처리하고, 시간 상한(`ModelRespondLimitSeconds`)은 마지막 이벤트까지에 걸어야 한다. SSE 를 내는 서버 방식과, 상한과 연결을 어떻게 묶을지를 정해야 한다.

## 결정
- 응답은 Starlette 의 `StreamingResponse`(`media_type="text/event-stream"`, 머리글 `Cache-Control: no-store, no-transform`)이다. 이벤트는 `event: <이름>\ndata: <JSON 한 줄>\n\n` 로 직접 쓴다. 이름은 data 의 `event` 와 같다. 낸 data 는 `ResponseStreamEvent` 로 검증한다.
- 압축 미들웨어를 쓰지 않는다(이 앱에는 없다). `id` 와 재개는 없다(계약).
- 엔진 호출과 상한은 요청과 따로 도는 작업(`Runtime._produce_response`)이 맡는다. 작업이 `asyncio.timeout(respond_limit)` 안에서 엔진 조각을 읽어 `SentenceStream`(responder 컴포넌트)으로 거른 뒤 큐에 쓰고, 응답 쪽은 큐를 읽어 보낸다. 큐는 한도가 없다(문장이 344자를 넘지 않아 이벤트 수가 그 안이다).
- 받아들이지 못하는 요청(검증, 인증, 409, 503 MODEL_NOT_LOADED)은 작업을 만들기 전에 던져 JSON 작업과 같은 문제 상세로 답한다. 스트림이 열린 뒤의 실패는 `error` 이벤트다.
- 엔진 포트(`ChatEngine`)에 `stream` 을 더한다. 구현(`VllmEngine`)은 openai SDK 의 `stream=True` 를 쓰고 `chat_template_kwargs={"enable_thinking": False}` 를 JSON 경로와 같이 싣는다(ADR 0010).

## 왜
- SSE 는 `text/event-stream` 본문일 뿐이고 형식은 `event:`/`data:` 두 줄과 빈 줄이라 표준(WHATWG HTML 9.2)만으로 쓸 수 있다. FastAPI 가 이미 Starlette 위에 있어 새 의존이 없다.
- 시간 상한과 "클라이언트가 끊어도 끝까지 처리"는 응답 제너레이터 안에서 풀 수 없다. 응답 제너레이터는 클라이언트가 끊으면 닫히고, 비동기 제너레이터는 `yield` 를 가로질러 `asyncio.timeout` 을 걸 수 없다. 별도 작업이 상한을 쥐고 큐로 넘기면 둘 다 풀린다. 처리가 끝나면 JSON 경로와 같은 지표(`model_call_duration_seconds{op="respond"}`)를 남긴다.
- 상한은 JSON 경로와 같은 값(25초, 계약 `ModelRespondLimitSeconds`)을 쓰고 호출 하나가 아니라 스트림 전체에 건다(계약 README 8항). 값은 계약이 정한 것이고 측정하지 않았다.
- 문장의 받아들이는 조건은 코드에 두지 않고 생성된 계약 모델 `ResponseSentence` 로만 가린다(D117, 계약 9.2.1: 1~344자, 앞뒤 공백 없음, `\n`·`\t` 밖의 제어 문자 없음, `{`·`[` 로 시작하지 않음). 손으로 쓴 제어 문자·JSON 감싸기 검사는 지웠다.
- 스트림(계약 README 5항): 조각은 바꾸지 않되 문장 앞의 공백은 보내지 않고, 끝의 공백은 뒤에 글자가 올 때까지 쥐었다가 그 글자와 함께 보낸다(끝이면 버린다). 쥔 공백은 길이에 넣지 않는다. 제어 문자가 오면, 첫 글자가 `{`·`[` 이면, 이은 글자가 344자를 넘으면 그 조각을 보내지 않고 `error`(503, OUTPUT_INVALID)다. 공백뿐이거나 비어서 끝나도 같다. `result.text` 는 보낸 조각을 이은 것이고 매 조각마다 `ResponseSentence` 로 확인한 값이다. 글자가 없는 조각은 보낼 것이 없어 건너뛴다(`ResponseDeltaText` 는 1자 이상).
- JSON 작업(`validate_sentence`)은 `.strip()` 을 남기되 공백만 걷고(제어 문자는 걷지 않는다) 나머지는 `ResponseSentence` 가 가린다. 이유: 스트림이 앞뒤 공백을 보내지 않으므로 두 작업이 같은 출력에 같은 문장을 내야 한다. 엔진이 흔히 붙이는 끝 줄바꿈 때문에 문장을 버리면 환자가 응답을 못 받는다. 걷지 않으면 스트림은 성공하는 출력이 JSON 에서는 503 이 되어 어긋난다.

## 검토한 대안과 버리는 이유
- **sse-starlette 같은 SSE 라이브러리:** 이 계약에 필요한 것은 이벤트 이름과 data 뿐이고 `id`, 재전송, 핑을 쓰지 않는다. 형식이 단순해 의존을 더할 이유가 없다. 라이브러리 시험도 우리가 하지 않는다.
- **응답 제너레이터 안에서 엔진을 읽고 상한을 건다:** 위 이유로 연결이 끊기면 처리가 멈추고(계약 3항 위반) 상한을 yield 너머로 걸 수 없다.
- **Accept 협상으로 `generateResponse` 에 SSE 를 더한다:** 계약이 이미 별도 작업으로 정했다.
- **조각마다 상한을 따로 둔다:** 계약 8항이 두지 않는다.

## 결과
- 얻는 것: 첫 조각을 엔진이 내는 즉시 흘린다. 끊김과 처리가 분리돼 있어 끊긴 뒤 재전송 규칙은 JSON 작업과 같다. 시험은 상한을 0초로 주입하고 끝나지 않는 가짜 엔진으로 상한 경로를 확인해 실제 대기와 벽시계가 없다.
- 감수하는 것: 응답 작업이 요청과 따로 돌아 서비스 종료 때 `aclose` 가 취소해야 한다(적재 작업과 같은 집합으로 관리한다). 중간 장치의 버퍼링은 막지 못한다(배치와 게이트웨이의 일, 계약 9항). 실제 vLLM 의 스트림은 GPU 시간대에 확인하지 못했다.

## 되돌리는 조건
계약이 `id` 와 재개를 요구하거나 이벤트 종류가 늘어 직접 쓰기가 복잡해지면 SSE 라이브러리를 다시 검토한다.
