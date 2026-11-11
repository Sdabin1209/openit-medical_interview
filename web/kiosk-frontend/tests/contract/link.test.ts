// link/survey 가 받는·내는 계약(survey-service 키오스크 작업)을 가짜 서버(MSW)로 확인한다.
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { components } from "../../src/contract/survey-service";
import { createSurveyLink, SurveyError } from "../../src/link/survey";
import { mswServerFor } from "../fakes/msw";
import { CODES, createFakeSurveyService, SESSION_ID, sse } from "../fakes/survey-service";

const fake = createFakeSurveyService({ questionnaires: [{ questionnaire_id: "a", title: "A 문진표" }] });
const server = mswServerFor(fake);
beforeAll(() => {
  server.listen({ onUnhandledFrame: "error" });
});
afterEach(() => {
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});

/** 기다림을 건너뛰고 기록하는 시계. 시험이 실제 시간을 재지 않는다 */
function fakeClock() {
  let now = 0;
  const sleeps: number[] = [];
  return {
    sleeps,
    clock: {
      now: () => now,
      sleep: (ms: number) => {
        sleeps.push(ms);
        now += ms;
        return Promise.resolve();
      },
    },
  };
}

function okStream(result: components["schemas"]["TurnResponse"]) {
  return new HttpResponse(sse([{ event: "result", result }]), { status: 200, headers: { "content-type": "text/event-stream" } });
}

function link(clock = fakeClock().clock) {
  return createSurveyLink({ baseUrl: "http://kiosk.test", requestLimitSeconds: 60, retryBudgetSeconds: 120, fallbackRetrySeconds: 2, clock });
}

describe("받는 계약", () => {
  it("활성 문진표 목록", async () => {
    expect((await link().listActiveQuestionnaires()).questionnaires).toEqual([{ questionnaire_id: "a", title: "A 문진표" }]);
  });
  it("세션 시작은 첫 문장을 준다", async () => {
    const started = await link().startSession({ start_code: CODES.ok });
    expect(started.session_id).toBe(SESSION_ID);
    expect(started.response_text).toContain("문진을 시작");
  });
  it.each([
    [CODES.invalid, 422, "START_CODE_INVALID"],
    [CODES.expired, 409, "START_CODE_EXPIRED"],
    [CODES.used, 409, "START_CODE_USED"],
  ])("시작 코드 %s 의 오류는 상태 %i 와 사유 %s 로 온다", async (code, status, reason) => {
    await expect(link().startSession({ start_code: code })).rejects.toMatchObject({ status, reason });
  });
  it("429 는 Retry-After 를 담아 던지고 자동으로 다시 보내지 않는다", async () => {
    const { clock, sleeps } = fakeClock();
    await expect(link(clock).startSession({ start_code: CODES.rateLimited })).rejects.toMatchObject({ status: 429, retryAfterSeconds: 5 });
    expect(sleeps).toEqual([]);
  });
  it("턴: 응답 문장 또는 실패 신호", async () => {
    const l = link();
    await l.startSession({ start_code: CODES.ok });
    const ok = await l.submitTurn(SESSION_ID, crypto.randomUUID(), "피워요");
    expect(ok.response_text).toBeDefined();
    const failed = await l.submitTurn(SESSION_ID, crypto.randomUUID(), "실패 시키기");
    expect(failed.failure_signal).toBe("EXTRACTION_UNAVAILABLE");
  });
  it("같은 turn_id 는 같은 결과(멱등)", async () => {
    const l = link();
    const id = crypto.randomUUID();
    expect(await l.submitTurn(SESSION_ID, id, "하루 한 갑")).toEqual(await l.submitTurn(SESSION_ID, id, "하루 한 갑"));
  });
  it("계약의 발화 상한(300자)을 넘으면 서버가 400 으로 거절한다", async () => {
    await expect(link().submitTurn(SESSION_ID, crypto.randomUUID(), "가".repeat(301))).rejects.toMatchObject({ status: 400 });
  });
  it("세션 상태, 직원 호출(201 후 200), 끝내기", async () => {
    const l = link();
    expect((await l.getSessionState(SESSION_ID)).status).toBeDefined();
    expect((await l.requestStaffCall(SESSION_ID)).kind).toBe("CALL_STAFF");
    expect((await l.getSessionState(SESSION_ID)).pause_reason).toBe("STAFF_CALL");
    expect((await l.requestStaffCall(SESSION_ID)).kind).toBe("CALL_STAFF");
    expect((await l.endSession(SESSION_ID)).ended_at).toBeDefined();
  });
});

describe("재시도(계약 kiosk_retry_budget 120초 안에서 같은 요청)", () => {
  it("503 은 Retry-After 만큼 기다린 뒤 같은 turn_id 로 다시 보낸다", async () => {
    const seen: string[] = [];
    let calls = 0;
    server.use(
      http.post("*/v1/sessions/:id/turns/stream", async ({ request }) => {
        seen.push(((await request.json()) as { turn_id: string }).turn_id);
        calls += 1;
        if (calls < 3) return HttpResponse.json({ type: "about:blank", title: "x", status: 503 }, { status: 503, headers: { "retry-after": "4" } });
        return okStream({ turn_id: seen[0] ?? "", status: "ACTIVE", response_text: "다음 질문" });
      }),
    );
    const { clock, sleeps } = fakeClock();
    const id = crypto.randomUUID();
    const response = await link(clock).submitTurn(SESSION_ID, id, "네");
    expect(response.response_text).toBe("다음 질문");
    expect(sleeps).toEqual([4000, 4000]);
    expect(new Set(seen)).toEqual(new Set([id]));
  });
  it("409 TURN_IN_PROGRESS 도 기다린 뒤 다시 보낸다", async () => {
    let calls = 0;
    server.use(
      http.post("*/v1/sessions/:id/turns/stream", () => {
        calls += 1;
        if (calls === 1) return HttpResponse.json({ type: "about:blank", title: "x", status: 409, reason: "TURN_IN_PROGRESS" }, { status: 409, headers: { "retry-after": "1" } });
        return okStream({ turn_id: crypto.randomUUID(), status: "ACTIVE", response_text: "ok" });
      }),
    );
    await expect(link().submitTurn(SESSION_ID, crypto.randomUUID(), "네")).resolves.toMatchObject({ response_text: "ok" });
    expect(calls).toBe(2);
  });
  it("연결 실패(응답 없음)도 다시 보낸다", async () => {
    let calls = 0;
    server.use(
      http.post("*/v1/sessions/:id/end", () => {
        calls += 1;
        if (calls === 1) return HttpResponse.error();
        return HttpResponse.json({ session_id: SESSION_ID, status: "ENDED_PARTIAL", ended_at: "2026-11-10T09:00:00Z" });
      }),
    );
    await expect(link().endSession(SESSION_ID)).resolves.toMatchObject({ status: "ENDED_PARTIAL" });
  });
  it("예산(120초)이 끝나면 마지막 오류를 던진다", async () => {
    server.use(http.post("*/v1/sessions/:id/turns/stream", () => HttpResponse.json({ type: "about:blank", title: "x", status: 503 }, { status: 503, headers: { "retry-after": "50" } })));
    const { clock, sleeps } = fakeClock();
    const error = await link(clock).submitTurn(SESSION_ID, crypto.randomUUID(), "네").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SurveyError);
    expect(error).toMatchObject({ status: 503 });
    expect(sleeps).toEqual([50_000, 50_000]);
  });
  it("재시도할 수 없는 오류(404)는 바로 던진다", async () => {
    const { clock, sleeps } = fakeClock();
    await expect(link(clock).getSessionState("00000000-0000-4000-8000-000000000000")).rejects.toMatchObject({ status: 404 });
    expect(sleeps).toEqual([]);
  });
});
