// 응답 문장 스트림(startSessionStream, submitTurnStream)을 link/survey 가 어떻게 읽는지 가짜 서버(MSW)로 확인한다.
// 표준: WHATWG HTML 9.2 이벤트 스트림 해석, 계약 README 응답 문장 스트림 7항(화면 규칙). 실제 시간은 재지 않는다(기다림은 바꿔 끼운 시계).
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { components } from "../../src/contract/survey-service";
import { createSurveyLink, SurveyError } from "../../src/link/survey";
import { mswServerFor } from "../fakes/msw";
import { CODES, createFakeSurveyService, SESSION_ID, sse, type FakeSurveyService } from "../fakes/survey-service";

let fake: FakeSurveyService = createFakeSurveyService();
const server = mswServerFor({ handle: (request) => fake.handle(request) } as FakeSurveyService);
beforeAll(() => {
  server.listen({ onUnhandledFrame: "error" });
});
afterEach(() => {
  server.resetHandlers();
  fake = createFakeSurveyService();
});
afterAll(() => {
  server.close();
});

function link() {
  const sleeps: number[] = [];
  let now = 0;
  const l = createSurveyLink({
    baseUrl: "http://kiosk.test",
    requestLimitSeconds: 60,
    retryBudgetSeconds: 120,
    fallbackRetrySeconds: 2,
    clock: { now: () => now, sleep: (ms) => { sleeps.push(ms); now += ms; return Promise.resolve(); } },
  });
  return { l, sleeps };
}

/** sink 가 받은 글을 모은다 */
function okStream(result: components["schemas"]["TurnResponse"]) {
  return new HttpResponse(sse([{ event: "result", result }]), { status: 200 });
}

/** sink 가 받은 글을 모은다 */
function recorder() {
  const shown: string[] = [];
  return { shown, sink: (text: string) => { shown.push(text); } };
}

const TURN_ID = "3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90";

describe("조각을 받는 대로 그린다", () => {
  it("delta 는 이어 붙인 전체 글로 알리고 result 의 문장으로 바꾼다", async () => {
    const { l } = link();
    await l.startSession({ start_code: CODES.ok });
    const { shown: turnShown, sink } = recorder();
    const result = await l.submitTurn(SESSION_ID, TURN_ID, "안 피워요", undefined, sink);
    // 앞 조각은 뒤 조각의 앞부분이고 마지막은 result 의 문장이다
    expect(turnShown.length).toBeGreaterThan(1);
    for (let i = 1; i < turnShown.length; i += 1) expect(turnShown[i]?.startsWith(turnShown[i - 1] ?? "")).toBe(true);
    expect(turnShown.at(-1)).toBe(result.response_text);
  });

  it("청크가 이벤트 중간(한 글자의 바이트 중간 포함)에서 잘려도 같은 이벤트로 읽는다", async () => {
    const bytes = new TextEncoder().encode(sse([{ event: "delta", text: "안녕" }, { event: "delta", text: "하세요" }, { event: "result", result: { turn_id: TURN_ID, status: "ACTIVE", response_text: "안녕하세요." } }]));
    server.use(
      http.post("*/v1/sessions/:id/turns/stream", () =>
        new HttpResponse(new ReadableStream({ start(c) { for (let i = 0; i < bytes.length; i += 4) c.enqueue(bytes.slice(i, i + 4)); c.close(); } }), { status: 200, headers: { "content-type": "text/event-stream" } }),
      ),
    );
    const { shown, sink } = recorder();
    const result = await link().l.submitTurn(SESSION_ID, TURN_ID, "네", undefined, sink);
    expect(shown).toEqual(["안녕", "안녕하세요", "안녕하세요."]);
    expect(result.response_text).toBe("안녕하세요.");
  });

  it("조각은 도착하는 대로 알린다(스트림이 끝나기 전에 첫 조각이 보인다)", async () => {
    const encoder = new TextEncoder();
    let controller!: ReadableStreamDefaultController<Uint8Array>;
    server.use(
      http.post("*/v1/sessions/:id/turns/stream", () =>
        new HttpResponse(new ReadableStream<Uint8Array>({ start(c) { controller = c; } }), { status: 200, headers: { "content-type": "text/event-stream" } }),
      ),
    );
    const seen: string[] = [];
    const pending = link().l.submitTurn(SESSION_ID, TURN_ID, "네", undefined, (t) => { seen.push(t); });
    await expect.poll(() => controller).toBeDefined();
    controller.enqueue(encoder.encode(sse([{ event: "delta", text: "첫 " }])));
    await expect.poll(() => seen).toEqual(["첫 "]);
    controller.enqueue(encoder.encode(sse([{ event: "delta", text: "조각" }])));
    await expect.poll(() => seen).toEqual(["첫 ", "첫 조각"]);
    controller.enqueue(encoder.encode(sse([{ event: "result", result: { turn_id: TURN_ID, status: "ACTIVE", response_text: "확정 문장" } }])));
    controller.close();
    await expect(pending).resolves.toMatchObject({ response_text: "확정 문장" });
    expect(seen.at(-1)).toBe("확정 문장");
  });

  it("result 의 문장이 조각을 이은 것과 달라도(고정 문장) result 의 것으로 바꾼다", async () => {
    server.use(
      http.post("*/v1/sessions/:id/turns/stream", () =>
        new HttpResponse(sse([{ event: "delta", text: "조각" }, { event: "result", result: { turn_id: TURN_ID, status: "ACTIVE", response_text: "직원 도움 안내 문장", staff_help_notice: true } }]), { status: 200 }),
      ),
    );
    const { shown, sink } = recorder();
    await link().l.submitTurn(SESSION_ID, TURN_ID, "네", undefined, sink);
    expect(shown).toEqual(["조각", "직원 도움 안내 문장"]);
  });

  it("delta 없이 result 하나(재생)도 받는다", async () => {
    const { l } = link();
    await l.submitTurn(SESSION_ID, TURN_ID, "안 피워요");
    const { shown, sink } = recorder();
    const again = await l.submitTurn(SESSION_ID, TURN_ID, "안 피워요", undefined, sink);
    expect(shown).toEqual([again.response_text]);
  });
});

describe("실패는 그린 조각을 지우고 JSON 작업의 실패와 같게 던진다", () => {
  it("문장 없는 result(failure_signal)는 조각을 지우고 그 결과를 돌려준다", async () => {
    const { l } = link();
    const { shown, sink } = recorder();
    const result = await l.submitTurn(SESSION_ID, TURN_ID, "실패 시키기", undefined, sink);
    expect(result.failure_signal).toBe("EXTRACTION_UNAVAILABLE");
    expect(shown.length).toBeGreaterThan(1);
    expect(shown.at(-1)).toBe("");
  });

  it("error 이벤트(503, retry_after_seconds 0)는 지우고 같은 turn_id 로 다시 보내 성공한다", async () => {
    fake.faultTimes("error");
    const { l, sleeps } = link();
    const { shown, sink } = recorder();
    const result = await l.submitTurn(SESSION_ID, TURN_ID, "안 피워요", undefined, sink);
    expect(result.response_text).toBeDefined();
    expect(shown).toContain("");
    expect(shown.indexOf("")).toBeLessThan(shown.length - 1);
    expect(sleeps).toEqual([0]);
    expect(fake.requests.filter((r) => r.path.endsWith("/turns/stream")).map((r) => (r.body as { turn_id: string }).turn_id)).toEqual([TURN_ID, TURN_ID]);
  });

  it("result 없이 끊긴 스트림은 지우고 같은 turn_id 로 다시 보낸다", async () => {
    fake.faultTimes("drop");
    const { l } = link();
    const { shown, sink } = recorder();
    const result = await l.submitTurn(SESSION_ID, TURN_ID, "안 피워요", undefined, sink);
    expect(result.response_text).toBeDefined();
    expect(shown).toContain("");
    expect(fake.requests.filter((r) => r.path.endsWith("/turns/stream"))).toHaveLength(2);
  });

  it("error 이벤트의 retry_after_seconds 만큼 기다린다", async () => {
    let calls = 0;
    server.use(
      http.post("*/v1/sessions/:id/turns/stream", () => {
        calls += 1;
        if (calls === 1) return new HttpResponse(sse([{ event: "delta", text: "x" }, { event: "error", problem: { type: "about:blank", title: "t", status: 503 }, retry_after_seconds: 7 }]), { status: 200 });
        return okStream({ turn_id: TURN_ID, status: "ACTIVE", response_text: "ok" });
      }),
    );
    const { l, sleeps } = link();
    await l.submitTurn(SESSION_ID, TURN_ID, "네");
    expect(sleeps).toEqual([7000]);
  });

  it("재시도할 수 없는 error 이벤트(500)는 지우고 SurveyError 로 던진다", async () => {
    server.use(
      http.post("*/v1/sessions/:id/turns/stream", () =>
        new HttpResponse(sse([{ event: "delta", text: "x" }, { event: "error", problem: { type: "about:blank", title: "t", status: 500, reason: "OUTPUT_INVALID" } }]), { status: 200 }),
      ),
    );
    const { shown, sink } = recorder();
    const { l, sleeps } = link();
    const error = await l.submitTurn(SESSION_ID, TURN_ID, "네", undefined, sink).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SurveyError);
    expect(error).toMatchObject({ status: 500, reason: "OUTPUT_INVALID" });
    expect(shown).toEqual(["x", ""]);
    expect(sleeps).toEqual([]);
  });

  it("예산(120초)이 끝날 때까지 끊기면 마지막 오류(status 0)를 던진다", async () => {
    server.use(http.post("*/v1/sessions/:id/turns/stream", () => new HttpResponse(sse([{ event: "delta", text: "x" }]), { status: 200 })));
    const { l, sleeps } = link();
    await expect(l.submitTurn(SESSION_ID, TURN_ID, "네")).rejects.toMatchObject({ status: 0 });
    expect(sleeps.every((ms) => ms === 2000)).toBe(true);
    expect(sleeps.reduce((a, b) => a + b, 0)).toBeLessThan(120_000);
  });
});

describe("세션 시작 스트림", () => {
  it("409 SESSION_START_IN_PROGRESS 는 Retry-After 만큼 기다린 뒤 같은 코드로 다시 보낸다", async () => {
    fake.startInProgressTimes(1);
    const { l, sleeps } = link();
    const started = await l.startSession({ start_code: CODES.ok });
    expect(started.session_id).toBe(SESSION_ID);
    expect(sleeps).toEqual([0]);
    expect(fake.requests.filter((r) => r.path === "/v1/sessions/stream").map((r) => r.body)).toEqual([{ start_code: CODES.ok }, { start_code: CODES.ok }]);
  });

  it("열기 전의 실패(422 시작 코드)는 JSON 작업과 같은 상태와 사유로 던진다", async () => {
    await expect(link().l.startSession({ start_code: CODES.invalid })).rejects.toMatchObject({ status: 422, reason: "START_CODE_INVALID" });
  });

  it("스트림 도중 error 는 지우고 같은 코드로 다시 시작한다", async () => {
    fake.faultTimes("error");
    const { shown, sink } = recorder();
    const started = await link().l.startSession({ start_code: CODES.ok }, undefined, sink);
    expect(shown).toContain("");
    expect(shown.at(-1)).toBe(started.response_text);
  });
});
