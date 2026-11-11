// survey-service 호출(N01, N02). 영역 밖(서버) 통신은 이 폴더에서만 한다(ADR 0003).
// 요청·응답은 계약에서 생성한 타입(src/contract/survey-service.d.ts)으로 만든다. 받은 계약 값은 서버가 한 번 검증했으므로 다시 검증하지 않는다(R7).
// 기기 인증은 브라우저·OS 가 내는 기기 인증서(mTLS)이고 화면 코드는 신원을 다루지 않는다(브리프).
import { createParser } from "eventsource-parser";
import createClient from "openapi-fetch";

import type { components, paths } from "../contract/survey-service";

export type ActiveQuestionnaireList = components["schemas"]["ActiveQuestionnaireList"];
export type SessionStarted = components["schemas"]["SessionStarted"];
export type TurnResponse = components["schemas"]["TurnResponse"];
export type SessionState = components["schemas"]["SessionState"];
export type SessionEnded = components["schemas"]["SessionEnded"];
export type StaffAlert = components["schemas"]["StaffAlert"];
export type ProblemDetails = components["schemas"]["ProblemDetails"];
export type ProblemReason = components["schemas"]["ProblemReason"];
export type SessionStartRequest = components["schemas"]["SessionStartRequest"];

/**
 * 응답 문장 스트림의 이벤트 data(계약 SessionStartStreamEvent·TurnStreamEvent: delta, result, error).
 * 왜 여기서 조립: 생성 타입(src/contract)에 이 data 스키마가 없어(작업 응답이 text/event-stream 의 문자열이다) 생성된 조각(SessionStarted, TurnResponse, ProblemDetails)으로 맞춘다.
 */
type StreamEventData<R> =
  | { event: "delta"; text: string }
  | { event: "result"; result: R }
  | { event: "error"; problem: ProblemDetails; retry_after_seconds?: number };

/** 화면에 보일 문장 전체를 알린다. 빈 문자열은 그린 조각을 지우라는 뜻이다(계약 README 응답 문장 스트림 7항) */
export type SentenceSink = (text: string) => void;

/** 서버가 계약대로 오류로 답했거나(status 4xx·5xx) 답을 받지 못했다(status 0: 연결 실패·시간 초과). */
export class SurveyError extends Error {
  constructor(
    /** HTTP 상태 코드. 응답을 받지 못했으면 0 */
    public readonly status: number,
    public readonly reason: ProblemReason | undefined,
    /** Retry-After(초). 계약 RetryAfterSeconds */
    public readonly retryAfterSeconds: number | undefined,
    message: string,
  ) {
    super(message);
    this.name = "SurveyError";
  }
}

export interface SurveyLinkOptions {
  /** 같은 출처(게이트웨이 뒤)의 주소. 계약의 서버 주소는 영역 게이트웨이 뒤라 브라우저에서는 같은 출처다 */
  baseUrl: string;
  /** 서버 응답을 기다리는 실패 판정 상한(초). 계약 TimeBudgetTable.kiosk_request */
  requestLimitSeconds: number;
  /** 같은 요청을 다시 보내는 데 쓸 수 있는 총 시간(초). 계약 TimeBudgetTable.kiosk_retry_budget */
  retryBudgetSeconds: number;
  /** Retry-After 가 없을 때 기다릴 초 */
  fallbackRetrySeconds: number;
  /** 시험에서 시계와 기다림을 바꿔 끼운다. 기본은 실제 시계 */
  clock?: { now: () => number; sleep: (ms: number, signal?: AbortSignal) => Promise<void> };
}

const realClock = {
  now: () => Date.now(),
  sleep: (ms: number, signal?: AbortSignal) =>
    new Promise<void>((resolve, reject) => {
      const timer = setTimeout(resolve, ms);
      signal?.addEventListener(
        "abort",
        () => {
          clearTimeout(timer);
          reject(new DOMException("중단", "AbortError"));
        },
        { once: true },
      );
    }),
};

function parseRetryAfter(value: string | null): number | undefined {
  if (value === null || !/^[0-9]+$/.test(value)) return undefined;
  return Number(value);
}

/** 같은 요청을 다시 보내도 되는 오류인가: 응답 없음(끊긴 스트림 포함), 503(변경은 되돌렸다), 같은 turn_id·같은 시작 코드가 처리 중(409 TURN_IN_PROGRESS, SESSION_START_IN_PROGRESS). */
export function isRetryable(error: SurveyError): boolean {
  return (
    error.status === 0 ||
    error.status === 503 ||
    (error.status === 409 && (error.reason === "TURN_IN_PROGRESS" || error.reason === "SESSION_START_IN_PROGRESS"))
  );
}

export function createSurveyLink(options: SurveyLinkOptions) {
  const clock = options.clock ?? realClock;
  const client = createClient<paths>({ baseUrl: options.baseUrl });

  /** 한 번 보내고 오류는 SurveyError 로 던진다. */
  async function once<T>(
    send: (signal: AbortSignal) => Promise<{ data?: T | undefined; error?: unknown; response: Response }>,
    outer: AbortSignal | undefined,
  ): Promise<{ data: T; status: number }> {
    const signal = AbortSignal.any([AbortSignal.timeout(options.requestLimitSeconds * 1000), ...(outer ? [outer] : [])]);
    let result: Awaited<ReturnType<typeof send>>;
    try {
      result = await send(signal);
    } catch (cause) {
      if (outer?.aborted === true) throw cause;
      throw new SurveyError(0, undefined, undefined, cause instanceof Error ? cause.message : "연결하지 못했다");
    }
    if (result.data !== undefined) return { data: result.data, status: result.response.status };
    const problem = result.error as Partial<ProblemDetails> | undefined;
    throw new SurveyError(
      result.response.status,
      problem?.reason,
      parseRetryAfter(result.response.headers.get("Retry-After")),
      problem?.title ?? `응답 코드 ${String(result.response.status)}`,
    );
  }

  /** 총 시간 예산 안에서 같은 시도를 되풀이한다. 처음 오류를 삼키지 않고 예산이 끝나면 마지막 오류를 던진다. */
  async function retrying<T>(attempt: () => Promise<T>, outer: AbortSignal | undefined): Promise<T> {
    const deadline = clock.now() + options.retryBudgetSeconds * 1000;
    for (;;) {
      try {
        return await attempt();
      } catch (error) {
        if (!(error instanceof SurveyError) || !isRetryable(error)) throw error;
        const waitMs = (error.retryAfterSeconds ?? options.fallbackRetrySeconds) * 1000;
        if (clock.now() + waitMs >= deadline) throw error;
        await clock.sleep(waitMs, outer);
      }
    }
  }

  function withRetry<T>(
    send: (signal: AbortSignal) => Promise<{ data?: T | undefined; error?: unknown; response: Response }>,
    outer: AbortSignal | undefined,
  ): Promise<T> {
    return retrying(async () => (await once(send, outer)).data, outer);
  }

  /**
   * 응답 문장 스트림 작업을 한 번 보낸다(WHATWG HTML 9.2 의 이벤트 스트림 해석을 eventsource-parser 로, POST 라 EventSource 대신 fetch).
   * 열기 전의 실패는 JSON 작업과 같은 문제 상세, 연 뒤의 실패(error 이벤트)와 result 없이 끝난 스트림은 같은 SurveyError 로 던진다.
   * 요청 상한(KioskRequestLimitSeconds)은 같은 신호로 마지막 이벤트까지 건다(계약 README 8항).
   * 문장은 sink 로 알린다: delta 는 이어 붙인 전체 글, result 에 문장이 있으면 그 글, 실패(문장 없는 result·error·끊김)는 빈 글.
   */
  async function streamOnce<R extends { response_text?: string | undefined }>(
    path: string,
    body: unknown,
    sink: SentenceSink | undefined,
    outer: AbortSignal | undefined,
  ): Promise<R> {
    const signal = AbortSignal.any([AbortSignal.timeout(options.requestLimitSeconds * 1000), ...(outer ? [outer] : [])]);
    let shown = "";
    const show = (text: string) => {
      shown = text;
      sink?.(text);
    };
    const clear = () => {
      if (shown !== "") show("");
    };
    const state: { end?: StreamEventData<R> } = {};
    try {
      const response = await fetch(`${options.baseUrl}${path}`, {
        method: "POST",
        headers: { "content-type": "application/json", accept: "text/event-stream" },
        body: JSON.stringify(body),
        signal,
      });
      if (!response.ok) {
        const problem = (await response.json().catch(() => undefined)) as Partial<ProblemDetails> | undefined;
        throw new SurveyError(response.status, problem?.reason, parseRetryAfter(response.headers.get("Retry-After")), problem?.title ?? `응답 코드 ${String(response.status)}`);
      }
      if (response.body === null) throw new SurveyError(0, undefined, undefined, "스트림 본문이 없다");
      const parser = createParser({
        onEvent: (message) => {
          if (state.end !== undefined) return;
          const data = JSON.parse(message.data) as StreamEventData<R>;
          if (data.event === "delta") show(shown + data.text);
          else state.end = data;
        },
      });
      // 왜 stream: true: 한 글자의 바이트가 청크 경계에서 잘려도 이어 푼다
      const decoder = new TextDecoder();
      const reader = response.body.getReader();
      while (state.end === undefined) {
        const chunk = await reader.read();
        if (chunk.done) break;
        parser.feed(decoder.decode(chunk.value, { stream: true }));
      }
      await reader.cancel().catch(() => undefined);
    } catch (cause) {
      clear();
      if (outer?.aborted === true || cause instanceof SurveyError) throw cause;
      throw new SurveyError(0, undefined, undefined, cause instanceof Error ? cause.message : "연결하지 못했다");
    }
    const end = state.end;
    if (end === undefined || end.event === "delta") {
      clear();
      throw new SurveyError(0, undefined, undefined, "결과 없이 스트림이 끝났다");
    }
    if (end.event === "error") {
      clear();
      throw new SurveyError(end.problem.status, end.problem.reason, end.retry_after_seconds, end.problem.title);
    }
    // 왜 result 의 문장으로 바꾼다: 서비스가 고정 문장을 붙이면 조각을 이은 것과 다르다. 문장이 없으면(failure_signal) 조각을 지운다
    if (end.result.response_text === undefined) clear();
    else show(end.result.response_text);
    return end.result;
  }

  /** 스트림 작업을 총 시간 예산 안에서 같은 요청으로 다시 보낸다. 다시 보내기 전에 그린 조각은 이미 지워졌다. */
  const streaming = <R extends { response_text?: string | undefined }>(path: string, body: unknown, sink: SentenceSink | undefined, outer: AbortSignal | undefined) =>
    retrying(() => streamOnce<R>(path, body, sink, outer), outer);

  return {
    listActiveQuestionnaires: (signal?: AbortSignal) =>
      withRetry<ActiveQuestionnaireList>((s) => client.GET("/v1/questionnaires", { signal: s }), signal),

    /** startSessionStream. 같은 기기가 같은 코드로 다시 시작하면 같은 세션이 온다(멱등)이므로 다시 보내도 된다. 첫 문장은 sink 로 알린다. */
    startSession: (body: SessionStartRequest, signal?: AbortSignal, sink?: SentenceSink) =>
      streaming<SessionStarted>("/v1/sessions/stream", body, sink, signal),

    /** submitTurnStream. 같은 turn_id 의 재전송은 같은 결과를 받는다(멱등). 호출자가 turn_id 를 정한다. 응답 문장은 sink 로 알린다. */
    submitTurn: (sessionId: string, turnId: string, utterance: string, signal?: AbortSignal, sink?: SentenceSink) =>
      streaming<TurnResponse>(`/v1/sessions/${encodeURIComponent(sessionId)}/turns/stream`, { turn_id: turnId, utterance }, sink, signal),

    endSession: (sessionId: string, signal?: AbortSignal) =>
      withRetry<SessionEnded>((s) => client.POST("/v1/sessions/{session_id}/end", { params: { path: { session_id: sessionId } }, signal: s }), signal),

    /** 2초마다 다시 읽으므로 재시도하지 않는다. */
    getSessionState: async (sessionId: string, signal?: AbortSignal) =>
      (await once<SessionState>((s) => client.GET("/v1/sessions/{session_id}/state", { params: { path: { session_id: sessionId } }, signal: s }), signal)).data,

    requestStaffCall: (sessionId: string, signal?: AbortSignal) =>
      withRetry<StaffAlert>((s) => client.POST("/v1/sessions/{session_id}/staff-calls", { params: { path: { session_id: sessionId } }, signal: s }), signal),
  };
}

export type SurveyLink = ReturnType<typeof createSurveyLink>;
