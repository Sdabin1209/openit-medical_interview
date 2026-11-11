// 가짜 survey-service(메모리 구현). 응답 본문은 계약에서 생성한 타입(src/contract/survey-service.d.ts)으로 만든다.
// 이웃 영역 없이 혼자 시험하려고 단위 시험(MSW)과 브라우저 시험(Playwright page.route)이 같은 가짜를 쓴다(ADR 0012).
// 계약의 오류 사유(ProblemReason)와 상태 코드를 따르되, 서버의 문진 로직은 흉내 내지 않고 시험에 필요한 만큼의 대본만 가진다.
import type { components } from "../../src/contract/survey-service";

type S = components["schemas"];

export interface FakeRequest {
  method: string;
  /** 쿼리 없는 경로(/v1/...) */
  path: string;
  body?: unknown;
}

export interface FakeResponse {
  status: number;
  headers?: Record<string, string>;
  body: unknown;
  /** 있으면 본문 대신 이 조각들을 차례로 보내는 text/event-stream 이다(청크 경계가 이벤트 중간에 걸릴 수 있다) */
  chunks?: string[];
}

/** 스트림 data 의 모양(계약 SessionStartStreamEvent·TurnStreamEvent). 생성 타입에 data 스키마가 없어 생성된 조각으로 맞춘다 */
export type FakeStreamEvent =
  | { event: "delta"; text: string }
  | { event: "result"; result: S["SessionStarted"] | S["TurnResponse"] }
  | { event: "error"; problem: S["ProblemDetails"]; retry_after_seconds?: number };

/** 이벤트를 SSE 글로 만든다(WHATWG HTML 9.2: event 줄, data 줄, 빈 줄) */
export function sse(events: FakeStreamEvent[]): string {
  return events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e)}\n\n`).join("");
}

/** 글을 n 자씩 잘라 청크로 만든다. 이벤트 중간에서 끊긴다 */
export function sliceChunks(text: string, n: number): string[] {
  const out: string[] = [];
  for (let i = 0; i < text.length; i += n) out.push(text.slice(i, i + n));
  return out;
}

/** 시험 대본의 시작 코드. 계약 startSession 의 오류마다 코드 하나를 두었다 */
export const CODES = {
  ok: "123456",
  invalid: "000000",
  expired: "111111",
  used: "222222",
  rateLimited: "333333",
} as const;

export const SESSION_ID = "6f0c2c1a-3b5e-4a58-9d57-0b1f6f3b9a10";
const ALERT_ID = "0a8d3d1c-9d3a-4a86-8d62-5a4d3d2c1b00";

const QUESTIONS = ["최근 1년간 담배를 피우셨나요?", "일주일에 술을 몇 번 드시나요?", "운동은 일주일에 몇 번 하시나요?"] as const;

function problem(status: number, title: string, reason?: S["ProblemReason"], headers?: Record<string, string>): FakeResponse {
  const body: S["ProblemDetails"] = { type: "about:blank", title, status, ...(reason === undefined ? {} : { reason }) };
  return { status, headers: { "content-type": "application/problem+json", ...headers }, body };
}

function json(status: number, body: unknown): FakeResponse {
  return { status, headers: { "content-type": "application/json" }, body };
}

export interface FakeOptions {
  questionnaires?: S["QuestionnaireSummary"][];
  /** 시작 코드나 기기 배치가 문진표를 이미 정한 설치처(문진표가 둘 이상이어도 선택을 요구하지 않는다) */
  boundQuestionnaire?: boolean;
}

export function createFakeSurveyService(options: FakeOptions = {}) {
  const questionnaires = options.questionnaires ?? [{ questionnaire_id: "national-checkup", title: "국가건강검진 문진표" }];
  let status: S["SessionStatus"] = "ACTIVE";
  let pauseReason: S["PauseReason"] | undefined;
  let resumeText: string | undefined;
  let started = false;
  let turns = 0;
  let unavailableNext = 0;
  const seenTurns = new Map<string, S["TurnResponse"]>();
  const requests: FakeRequest[] = [];
  let startInProgressNext = 0;
  let faultNext: { kind: "error" | "drop"; times: number } | undefined;

  const pieces = (text: string) => text.match(/\S+\s*/g) ?? [text];

  /** 스트림 작업: JSON 작업과 같은 판정을 하고, 받아들이면 200 스트림(delta 뒤 result)으로 바꾼다(계약 README 응답 문장 스트림 1·4·6항) */
  function stream(request: FakeRequest, jsonPath: string): FakeResponse {
    const turnId = (request.body as Partial<S["TurnRequest"]> | undefined)?.turn_id;
    const replay = turnId !== undefined && seenTurns.has(turnId);
    const fault = faultNext;
    const head = { status: 200, headers: { "content-type": "text/event-stream", "cache-control": "no-store, no-transform" } };
    if (fault !== undefined && fault.times > 0 && !replay && jsonPath !== "") {
      fault.times -= 1;
      const deltas: FakeStreamEvent[] = pieces("네, 알겠").map((text) => ({ event: "delta", text }));
      const events: FakeStreamEvent[] =
        fault.kind === "error"
          ? [...deltas, { event: "error", problem: { type: "about:blank", title: "지금은 처리할 수 없다", status: 503, reason: "DEADLINE_EXCEEDED" }, retry_after_seconds: 0 }]
          : deltas;
      return { ...head, body: null, chunks: sliceChunks(sse(events), 9) };
    }
    const json = handle({ ...request, path: jsonPath }, false);
    if (json.status !== 200 && json.status !== 201) return json;
    const result = json.body as S["SessionStarted"] | S["TurnResponse"];
    const text = result.response_text;
    const events: FakeStreamEvent[] = [];
    // 재생과 LoRA-B 를 부르지 않은 턴은 delta 없이 result 하나, 실패 신호도 조각을 먼저 보낼 수 있다
    if (!replay) {
      const spoken = text ?? "네, 알겠습니다.";
      events.push(...pieces(spoken).map((piece): FakeStreamEvent => ({ event: "delta", text: piece })));
    }
    events.push({ event: "result", result });
    return { ...head, body: null, chunks: sliceChunks(sse(events), 9) };
  }

  function handle(request: FakeRequest, record = true): FakeResponse {
    if (record) requests.push(request);
    const { method, path } = request;
    if (method === "POST" && path === "/v1/sessions/stream") {
      if (startInProgressNext > 0) {
        startInProgressNext -= 1;
        return problem(409, "앞선 시작 요청이 처리 중이다", "SESSION_START_IN_PROGRESS", { "retry-after": "0" });
      }
      return stream(request, "/v1/sessions");
    }
    const streamTurn = /^\/v1\/sessions\/([^/]+)\/turns\/stream$/.exec(path);
    if (method === "POST" && streamTurn !== null) return stream(request, `/v1/sessions/${streamTurn[1] ?? ""}/turns`);
    if (unavailableNext > 0 && path.startsWith("/v1/sessions")) {
      unavailableNext -= 1;
      return problem(503, "지금은 처리할 수 없다", "DEADLINE_EXCEEDED", { "retry-after": "0" });
    }
    if (method === "GET" && path === "/v1/questionnaires") {
      const body: S["ActiveQuestionnaireList"] = { questionnaires };
      return json(200, body);
    }
    if (method === "POST" && path === "/v1/sessions") {
      const body = request.body as S["SessionStartRequest"];
      if (body.start_code === CODES.invalid || !Object.values(CODES).includes(body.start_code as never)) return problem(422, "시작 코드가 맞지 않는다", "START_CODE_INVALID");
      if (body.start_code === CODES.expired) return problem(409, "시작 코드가 만료되었다", "START_CODE_EXPIRED");
      if (body.start_code === CODES.used) return problem(409, "다른 기기가 쓴 코드다", "START_CODE_USED");
      if (body.start_code === CODES.rateLimited) return problem(429, "시도가 너무 잦다", undefined, { "retry-after": "5" });
      // 계약 startSession: 코드·요청·기기 배치 어디에도 문진표가 없고 활성 문진표가 둘 이상이면 422 QUESTIONNAIRE_REQUIRED(코드는 쓰지 않은 것으로 한다)
      if (body.questionnaire_id === undefined && !options.boundQuestionnaire && questionnaires.length >= 2) return problem(422, "문진표를 골라야 한다", "QUESTIONNAIRE_REQUIRED");
      const first = !started;
      started = true;
      const result: S["SessionStarted"] = {
        session_id: SESSION_ID,
        status: "ACTIVE",
        questionnaire_id: body.questionnaire_id ?? questionnaires[0]?.questionnaire_id ?? "national-checkup",
        questionnaire_title: questionnaires.find((q) => q.questionnaire_id === body.questionnaire_id)?.title ?? questionnaires[0]?.title ?? "문진표",
        response_text: `안녕하세요. 문진을 시작하겠습니다. ${QUESTIONS[0]}`,
        current_item_id: "Q1",
      };
      return json(first ? 201 : 200, result);
    }
    const match = /^\/v1\/sessions\/([^/]+)\/(turns|end|state|staff-calls)$/.exec(path);
    if (match === null) return problem(404, "없는 경로");
    if (match[1] !== SESSION_ID) return problem(404, "없는 세션", undefined);
    const action = match[2];
    if (method === "GET" && action === "state") {
      const result: S["SessionState"] = { session_id: SESSION_ID, status, ...(pauseReason === undefined ? {} : { pause_reason: pauseReason }), ...(resumeText === undefined ? {} : { resume_text: resumeText }) };
      return json(200, result);
    }
    if (method === "POST" && action === "end") {
      // 계약 SessionEnded: 이미 유휴로 만료된 세션이면 EXPIRED
      if (status !== "EXPIRED") status = turns >= QUESTIONS.length ? "ENDED_COMPLETE" : "ENDED_PARTIAL";
      const result: S["SessionEnded"] = { session_id: SESSION_ID, status, ended_at: "2026-11-10T09:00:00Z" };
      return json(200, result);
    }
    if (method === "POST" && action === "staff-calls") {
      if (status !== "ACTIVE" && status !== "PAUSED") return problem(409, "세션이 끝났다", "SESSION_NOT_ACTIVE");
      const created = status === "ACTIVE";
      status = "PAUSED";
      pauseReason = "STAFF_CALL";
      const alert: S["StaffAlert"] = { alert_id: ALERT_ID, kind: "CALL_STAFF", session_id: SESSION_ID, raised_at: "2026-11-10T09:00:00Z" };
      return json(created ? 201 : 200, alert);
    }
    if (method === "POST" && action === "turns") {
      const body = request.body as S["TurnRequest"];
      if (typeof body.utterance !== "string" || body.utterance.length < 1 || body.utterance.length > 300) return problem(400, "발화 길이가 계약을 어겼다");
      const earlier = seenTurns.get(body.turn_id);
      if (earlier !== undefined) return json(200, earlier);
      if (status !== "ACTIVE") return problem(409, "세션이 끝났거나 멈췄다", "SESSION_NOT_ACTIVE");
      if (body.utterance.includes("실패")) {
        // 계약 submitTurn: 실패 신호를 준 turn_id 는 기록하지 않아 같은 turn_id 의 재전송은 다시 처리된다
        const failed: S["TurnResponse"] = { turn_id: body.turn_id, status: "ACTIVE", failure_signal: "EXTRACTION_UNAVAILABLE" };
        return json(200, failed);
      }
      let result: S["TurnResponse"];
      turns += 1;
      const next = QUESTIONS[turns];
      if (next === undefined) {
        status = "ENDED_COMPLETE";
        result = { turn_id: body.turn_id, status, response_text: "문진이 모두 끝났습니다. 감사합니다." };
      } else {
        result = { turn_id: body.turn_id, status: "ACTIVE", response_text: `네, 알겠습니다. ${next}`, current_item_id: `Q${String(turns + 1)}` };
      }
      seenTurns.set(body.turn_id, result);
      return json(200, result);
    }
    return problem(404, "없는 경로");
  }

  return {
    handle,
    requests,
    /** 직원이 정지를 풀었다: 다음 상태 읽기부터 ACTIVE 와 resume_text 를 준다 */
    resume(text = "다시 시작하겠습니다. 이어서 답해 주세요.") {
      status = "ACTIVE";
      pauseReason = undefined;
      resumeText = text;
    },
    /** 위험 신호로 세션이 멈췄다 */
    pause(reason: S["PauseReason"] = "RISK_SIGNAL") {
      status = "PAUSED";
      pauseReason = reason;
    },
    expire() {
      status = "EXPIRED";
    },
    /** 다음 시작 스트림 요청 n 번에 409 SESSION_START_IN_PROGRESS(Retry-After 0)를 낸다 */
    startInProgressTimes(n: number) {
      startInProgressNext = n;
    },
    /** 다음 스트림 n 번이 조각을 보낸 뒤 error 이벤트로 끝나거나(error) result 없이 끊긴다(drop). 기록되지 않는다 */
    faultTimes(kind: "error" | "drop", n = 1) {
      faultNext = { kind, times: n };
    },
    /** 세션 작업에 503 을 n 번 낸다(변경은 되돌렸다) */
    unavailableTimes(n: number) {
      unavailableNext = n;
    },
  };
}

export type FakeSurveyService = ReturnType<typeof createFakeSurveyService>;
