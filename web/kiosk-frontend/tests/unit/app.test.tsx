// App 조립 시험: 가짜 survey-service(MSW)를 상대로 시작 → 턴 → 직원 호출 → 끝을 화면에서 따라간다.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { http, HttpResponse } from "msw";

import { App } from "../../src/App";
import { mswServerFor } from "../fakes/msw";
import { CODES, createFakeSurveyService, sse, type FakeSurveyService } from "../fakes/survey-service";

let fake: FakeSurveyService = createFakeSurveyService();
const server = mswServerFor({ handle: (request) => fake.handle(request) } as FakeSurveyService);
beforeAll(() => {
  server.listen({ onUnhandledFrame: "error" });
});
beforeEach(() => {
  fake = createFakeSurveyService();
});
afterEach(() => {
  server.resetHandlers();
  vi.useRealTimers();
  delete (globalThis as { jest?: unknown }).jest;
  user = userEvent.setup();
});
afterAll(() => {
  server.close();
});

let user = userEvent.setup();

// 가짜 시계: 실제 시간은 흐르지 않고 vi.advanceTimersByTime 으로만 넘어간다.
// Testing Library 의 waitFor/findBy 는 `jest.advanceTimersByTime` 이 있으면 가짜 타이머로 판단해 시계를 직접 넘긴다(표준 연동 방법).
function useFakeClock() {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "setTimeout", "clearTimeout", "Date"] });
  (globalThis as { jest?: unknown }).jest = { advanceTimersByTime: (ms: number) => vi.advanceTimersByTime(ms) };
  user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) });
}

function renderApp(path = "/", basename?: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]} {...(basename === undefined ? {} : { basename })}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function enterCode(code: string) {
  for (const digit of code) await user.click(screen.getByRole("button", { name: digit }));
  await user.click(screen.getByRole("button", { name: "시작하기" }));
}

async function startSession() {
  renderApp();
  await enterCode(CODES.ok);
  await screen.findByRole("textbox", { name: "답변" });
}

async function say(text: string) {
  await user.type(screen.getByRole("textbox", { name: "답변" }), text);
  await user.click(screen.getByRole("button", { name: "보내기" }));
}

describe("화면 접두어(/kiosk/)", () => {
  it("접두어 아래 주소로 열면 시작 화면이 보이고, 모르는 경로도 시작 화면으로 간다", async () => {
    renderApp("/kiosk/nowhere", "/kiosk/");
    expect(await screen.findByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeVisible();
  });
});

describe("시작", () => {
  it("올바른 코드로 시작하면 첫 문장이 보인다", async () => {
    await startSession();
    expect(screen.getByText(/문진을 시작하겠습니다/)).toBeInTheDocument();
    expect(screen.getByText("국가건강검진 문진표")).toBeInTheDocument();
  });
  it("틀린 코드는 알리고 다시 입력하게 한다", async () => {
    renderApp();
    await enterCode(CODES.invalid);
    expect(await screen.findByRole("alert")).toHaveTextContent("코드가 맞지 않습니다");
    expect(screen.getByRole("group", { name: /0자리 입력함/ })).toBeInTheDocument();
  });
  const two = [{ questionnaire_id: "a", title: "A 문진표" }, { questionnaire_id: "b", title: "B 문진표" }];
  it("문진표가 둘이고 정해진 것이 없으면 서버의 422 QUESTIONNAIRE_REQUIRED 뒤에 고르게 하고 같은 코드로 다시 보낸다", async () => {
    fake = createFakeSurveyService({ questionnaires: two });
    renderApp();
    await waitFor(() => { expect(fake.requests.some((r) => r.path === "/v1/questionnaires")).toBe(true); });
    await enterCode(CODES.ok);
    await user.click(await screen.findByRole("button", { name: "B 문진표" }));
    expect(await screen.findByText("B 문진표")).toBeInTheDocument();
    const bodies = fake.requests.filter((r) => r.path === "/v1/sessions/stream").map((r) => r.body);
    expect(bodies).toEqual([{ start_code: CODES.ok }, { start_code: CODES.ok, questionnaire_id: "b" }]);
  });
  it("코드나 기기 배치가 문진표를 정했으면(문진표가 둘이어도) 선택 화면 없이 시작한다", async () => {
    fake = createFakeSurveyService({ questionnaires: two, boundQuestionnaire: true });
    renderApp();
    await waitFor(() => { expect(fake.requests.some((r) => r.path === "/v1/questionnaires")).toBe(true); });
    await enterCode(CODES.ok);
    await screen.findByRole("textbox", { name: "답변" });
    expect(screen.queryByRole("button", { name: "B 문진표" })).toBeNull();
    expect(fake.requests.filter((r) => r.path === "/v1/sessions/stream").map((r) => r.body)).toEqual([{ start_code: CODES.ok }]);
  });
});

describe("대화", () => {
  it("발화를 보내면 다음 문장이 보이고 입력칸이 비워진다", async () => {
    await startSession();
    await say("안 피워요");
    expect(await screen.findByText(/일주일에 술을 몇 번/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "답변" })).toHaveValue("");
    const turn = fake.requests.find((r) => r.path.endsWith("/turns/stream"));
    expect(turn?.body).toMatchObject({ utterance: "안 피워요" });
  });
  it("실패 신호면 다시 말하라고 알리고 발화를 지우지 않는다", async () => {
    await startSession();
    await say("실패 시키기");
    expect(await screen.findByRole("alert")).toHaveTextContent("잘 이해하지 못했습니다");
    expect(screen.getByRole("textbox", { name: "답변" })).toHaveValue("실패 시키기");
    expect(screen.getByText(/문진을 시작하겠습니다/)).toBeInTheDocument();
  });
  it("실패 뒤 다시 보내면 새 turn_id 로 보낸다", async () => {
    await startSession();
    await say("실패 시키기");
    await screen.findByRole("alert");
    await user.clear(screen.getByRole("textbox", { name: "답변" }));
    await user.type(screen.getByRole("textbox", { name: "답변" }), "다시요");
    await user.click(screen.getByRole("button", { name: "보내기" }));
    await screen.findByText(/일주일에 술을 몇 번/);
    const ids = fake.requests.filter((r) => r.path.endsWith("/turns/stream")).map((r) => (r.body as { turn_id: string }).turn_id);
    expect(new Set(ids).size).toBe(2);
  });
  it("마지막 문항 뒤에는 끝 화면이 나온다", async () => {
    await startSession();
    await say("a");
    await screen.findByText(/일주일에 술을 몇 번/);
    await say("b");
    await screen.findByText(/운동은 일주일에/);
    await say("c");
    expect(await screen.findByRole("heading", { name: /문진이 끝났습니다/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "처음으로" }));
    expect(await screen.findByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeInTheDocument();
  });
  it("문진 끝내기를 확인하면 중간 종료 안내가 나온다", async () => {
    await startSession();
    await user.click(screen.getByRole("button", { name: "문진 끝내기" }));
    await user.click(await screen.findByRole("button", { name: "끝내기" }));
    expect(await screen.findByRole("heading", { name: /저장되었습니다/ })).toBeInTheDocument();
  });
  it("서버가 세션이 멈췄다고 하면(409 SESSION_NOT_ACTIVE) 상태를 읽어 멈춤 화면으로 간다", async () => {
    await startSession();
    fake.pause("RISK_SIGNAL");
    await say("네");
    expect(await screen.findByRole("heading", { name: "잠시 기다려 주세요" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("직원이 곧 도와드립니다");
  });
  it("서버가 세션을 만료시켰으면(409 SESSION_NOT_ACTIVE 뒤 상태 EXPIRED) 시작 화면으로 돌아가고 입력이 지워진다", async () => {
    await startSession();
    fake.expire();
    await say("네");
    expect(await screen.findByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeInTheDocument();
    expect(screen.queryByDisplayValue("네")).toBeNull();
    expect(fake.requests.some((r) => r.method === "GET" && r.path.endsWith("/state"))).toBe(true);
  });
  it("끝내기를 눌렀는데 서버가 이미 만료시켰으면(endSession 이 EXPIRED) 시작 화면으로 돌아간다", async () => {
    await startSession();
    fake.expire();
    await user.click(screen.getByRole("button", { name: "문진 끝내기" }));
    await user.click(await screen.findByRole("button", { name: "끝내기" }));
    expect(await screen.findByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeInTheDocument();
  });
  it("멈춘 동안 읽은 상태가 EXPIRED 여도 시작 화면으로 돌아간다", async () => {
    useFakeClock();
    await startSession();
    await user.click(screen.getByRole("button", { name: "직원 부르기" }));
    await screen.findByRole("heading", { name: "잠시 기다려 주세요" });
    fake.expire();
    await vi.advanceTimersByTimeAsync(2000);
    expect(await screen.findByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeInTheDocument();
  });
  it("직원 호출이 409 SESSION_NOT_ACTIVE 이고 상태가 EXPIRED 면 시작 화면으로 돌아간다", async () => {
    await startSession();
    fake.expire();
    await user.click(screen.getByRole("button", { name: "직원 부르기" }));
    expect(await screen.findByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeInTheDocument();
  });
});

describe("직원 호출", () => {
  it("직원을 부르면 멈춤 화면이 되고 직원이 풀면 resume_text 로 이어진다", async () => {
    // 2초 간격의 다음 읽기를 가짜 시계로 건너뛴다(계약 SessionStatePollSeconds)
    useFakeClock();
    await startSession();
    await user.click(screen.getByRole("button", { name: "직원 부르기" }));
    expect(await screen.findByRole("heading", { name: "잠시 기다려 주세요" })).toBeInTheDocument();
    fake.resume("다시 시작하겠습니다.");
    await vi.advanceTimersByTimeAsync(2000);
    expect(await screen.findByText("다시 시작하겠습니다.")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "답변" })).toBeInTheDocument();
  });
  it("멈춤 화면에서 직원을 다시 부를 수 있다", async () => {
    await startSession();
    await user.click(screen.getByRole("button", { name: "직원 부르기" }));
    await user.click(await screen.findByRole("button", { name: "직원 다시 부르기" }));
    await waitFor(() => { expect(fake.requests.filter((r) => r.path.endsWith("/staff-calls"))).toHaveLength(2); });
  });
});

describe("유휴 초기화(60초)", () => {
  it("대화 중 입력 없이 60초가 지나면 처음 화면으로 돌아가고 입력이 지워진다", async () => {
    useFakeClock();
    await startSession();
    await user.type(screen.getByRole("textbox", { name: "답변" }), "남은 글");
    await vi.advanceTimersByTimeAsync(61_000);
    expect(await screen.findByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeInTheDocument();
    expect(screen.queryByDisplayValue("남은 글")).toBeNull();
  });
  it("멈춘 세션은 초기화하지 않는다(계약: 멈춘 세션은 만료하지 않는다)", async () => {
    useFakeClock();
    await startSession();
    await user.click(screen.getByRole("button", { name: "직원 부르기" }));
    await screen.findByRole("heading", { name: "잠시 기다려 주세요" });
    await vi.advanceTimersByTimeAsync(61_000);
    expect(screen.getByRole("heading", { name: "잠시 기다려 주세요" })).toBeInTheDocument();
  });
  it("시작 화면에서 입력 중이던 코드는 60초 뒤 지워진다", async () => {
    useFakeClock();
    renderApp();
    await user.click(screen.getByRole("button", { name: "1" }));
    expect(screen.getByRole("group", { name: /1자리 입력함/ })).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(61_000);
    expect(screen.getByRole("group", { name: /0자리 입력함/ })).toBeInTheDocument();
  });
});

describe("응답 문장 스트림(계약 README 응답 문장 스트림 7항)", () => {
  const TURN = "3f2b8c1e-5a47-4d0e-9b6a-7c1d2e8f4a90";

  it("조각을 받는 대로 화면의 문장에 이어 그리고 result 의 문장으로 바꾼다", async () => {
    await startSession();
    const encoder = new TextEncoder();
    let controller!: ReadableStreamDefaultController<Uint8Array>;
    server.use(
      http.post("*/v1/sessions/:id/turns/stream", () =>
        new HttpResponse(new ReadableStream<Uint8Array>({ start(c) { controller = c; } }), { status: 200, headers: { "content-type": "text/event-stream" } }),
      ),
    );
    await say("안 피워요");
    await waitFor(() => { expect(controller).toBeDefined(); });
    // 스트림이 끝나기 전에 첫 조각이 보이고, 이전 문장은 사라진다
    controller.enqueue(encoder.encode(sse([{ event: "delta", text: "네, " }])));
    expect(await screen.findByText("네,")).toBeInTheDocument();
    expect(screen.queryByText(/문진을 시작하겠습니다/)).toBeNull();
    controller.enqueue(encoder.encode(sse([{ event: "delta", text: "알겠습니다." }])));
    expect(await screen.findByText("네, 알겠습니다.")).toBeInTheDocument();
    expect(document.getElementById("sentence")).toHaveAttribute("aria-busy", "true");
    controller.enqueue(encoder.encode(sse([{ event: "result", result: { turn_id: TURN, status: "ACTIVE", response_text: "확정된 다음 질문입니다." } }])));
    controller.close();
    expect(await screen.findByText("확정된 다음 질문입니다.")).toBeInTheDocument();
    expect(screen.queryByText("네, 알겠습니다.")).toBeNull();
    expect(document.getElementById("sentence")).toHaveAttribute("aria-busy", "false");
  });

  it("failure_signal result 는 조각을 지우고 이전 문장으로 돌아가 다시 말하라고 알린다", async () => {
    await startSession();
    await say("실패 시키기");
    expect(await screen.findByRole("alert")).toHaveTextContent("잘 이해하지 못했습니다");
    expect(screen.getByText(/문진을 시작하겠습니다/)).toBeInTheDocument();
    expect(screen.queryByText(/알겠습니다/)).toBeNull();
  });

  it("error 이벤트면 조각을 지우고 같은 turn_id 로 다시 보내 성공한다", async () => {
    await startSession();
    fake.faultTimes("error");
    await say("안 피워요");
    expect(await screen.findByText(/일주일에 술을 몇 번/)).toBeInTheDocument();
    const ids = fake.requests.filter((r) => r.path.endsWith("/turns/stream")).map((r) => (r.body as { turn_id: string }).turn_id);
    expect(ids).toHaveLength(2);
    expect(new Set(ids).size).toBe(1);
  });

  it("끊긴 스트림이 예산 안에 풀리지 않으면 지우고 연결 실패로 알리며 발화를 남긴다", async () => {
    await startSession();
    server.use(http.post("*/v1/sessions/:id/turns/stream", () => HttpResponse.error()));
    useFakeClock();
    await say("안 피워요");
    // 가짜 시계로 재시도 예산(120초)을 넘긴다
    for (let i = 0; i < 70; i += 1) await vi.advanceTimersByTimeAsync(2000);
    expect(await screen.findByRole("alert")).toHaveTextContent(/연결/);
    expect(screen.getByRole("textbox", { name: "답변" })).toHaveValue("안 피워요");
    expect(screen.getByText(/문진을 시작하겠습니다/)).toBeInTheDocument();
  });

  it("세션 시작: 첫 문장을 받는 대로 시작 화면에 보이고 result 뒤 대화 화면의 문장이 된다", async () => {
    renderApp();
    const encoder = new TextEncoder();
    let controller!: ReadableStreamDefaultController<Uint8Array>;
    server.use(
      http.post("*/v1/sessions/stream", () =>
        new HttpResponse(new ReadableStream<Uint8Array>({ start(c) { controller = c; } }), { status: 200, headers: { "content-type": "text/event-stream" } }),
      ),
    );
    await enterCode(CODES.ok);
    await waitFor(() => { expect(controller).toBeDefined(); });
    controller.enqueue(encoder.encode(sse([{ event: "delta", text: "안녕하세요. " }])));
    expect(await screen.findByTestId("start-preview")).toHaveTextContent("안녕하세요.");
    controller.enqueue(encoder.encode(sse([{ event: "result", result: { session_id: "6f0c2c1a-3b5e-4a58-9d57-0b1f6f3b9a10", status: "ACTIVE", questionnaire_id: "q", response_text: "안녕하세요. 첫 질문입니다." } }])));
    controller.close();
    expect(await screen.findByText("안녕하세요. 첫 질문입니다.")).toBeInTheDocument();
    expect(screen.queryByTestId("start-preview")).toBeNull();
  });

  it("세션 시작: 409 SESSION_START_IN_PROGRESS 는 기다린 뒤 같은 코드로 다시 보내 시작한다", async () => {
    fake.startInProgressTimes(1);
    renderApp();
    await enterCode(CODES.ok);
    await screen.findByRole("textbox", { name: "답변" });
    expect(fake.requests.filter((r) => r.path === "/v1/sessions/stream").map((r) => r.body)).toEqual([{ start_code: CODES.ok }, { start_code: CODES.ok }]);
  });

  it("세션 시작: 스트림 도중 error 는 조각을 지우고 같은 코드로 다시 보낸다", async () => {
    fake.faultTimes("error");
    renderApp();
    await enterCode(CODES.ok);
    await screen.findByRole("textbox", { name: "답변" });
    expect(screen.queryByTestId("start-preview")).toBeNull();
    expect(fake.requests.filter((r) => r.path === "/v1/sessions/stream")).toHaveLength(2);
  });

  it("음성 합성은 조각을 읽지 않고 result 로 확정된 문장 하나만 읽는다", async () => {
    const spoken: string[] = [];
    const voice = { localService: true, lang: "ko-KR" };
    vi.stubGlobal("SpeechSynthesisUtterance", class { constructor(public text: string) {} voice: unknown; lang = "" });
    vi.stubGlobal("speechSynthesis", {
      getVoices: () => [voice],
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      cancel: vi.fn(),
      speak: (u: { text: string }) => { spoken.push(u.text); },
    });
    try {
      await startSession();
      spoken.length = 0;
      await say("안 피워요");
      await screen.findByText(/일주일에 술을 몇 번/);
      expect(spoken).toEqual(["네, 알겠습니다. 일주일에 술을 몇 번 드시나요?"]);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
