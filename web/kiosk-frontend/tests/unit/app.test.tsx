// App 조립 시험: 가짜 survey-service(MSW)를 상대로 시작 → 턴 → 직원 호출 → 끝을 화면에서 따라간다.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/App";
import { mswServerFor } from "../fakes/msw";
import { CODES, createFakeSurveyService, type FakeSurveyService } from "../fakes/survey-service";

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
});
afterAll(() => {
  server.close();
});

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function enterCode(code: string) {
  for (const digit of code) await userEvent.click(screen.getByRole("button", { name: digit }));
  await userEvent.click(screen.getByRole("button", { name: "시작하기" }));
}

async function startSession() {
  renderApp();
  await enterCode(CODES.ok);
  await screen.findByRole("textbox", { name: "답변" });
}

async function say(text: string) {
  await userEvent.type(screen.getByRole("textbox", { name: "답변" }), text);
  await userEvent.click(screen.getByRole("button", { name: "보내기" }));
}

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
  it("문진표가 둘이면 코드 뒤에 고른 문진표로 시작한다", async () => {
    fake = createFakeSurveyService({ questionnaires: [{ questionnaire_id: "a", title: "A 문진표" }, { questionnaire_id: "b", title: "B 문진표" }] });
    renderApp();
    await waitFor(() => { expect(fake.requests.some((r) => r.path === "/v1/questionnaires")).toBe(true); });
    await enterCode(CODES.ok);
    await userEvent.click(await screen.findByRole("button", { name: "B 문진표" }));
    expect(await screen.findByText("B 문진표")).toBeInTheDocument();
    expect(fake.requests.find((r) => r.path === "/v1/sessions")?.body).toEqual({ start_code: CODES.ok, questionnaire_id: "b" });
  });
});

describe("대화", () => {
  it("발화를 보내면 다음 문장이 보이고 입력칸이 비워진다", async () => {
    await startSession();
    await say("안 피워요");
    expect(await screen.findByText(/일주일에 술을 몇 번/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "답변" })).toHaveValue("");
    const turn = fake.requests.find((r) => r.path.endsWith("/turns"));
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
    await userEvent.clear(screen.getByRole("textbox", { name: "답변" }));
    await userEvent.type(screen.getByRole("textbox", { name: "답변" }), "다시요");
    await userEvent.click(screen.getByRole("button", { name: "보내기" }));
    await screen.findByText(/일주일에 술을 몇 번/);
    const ids = fake.requests.filter((r) => r.path.endsWith("/turns")).map((r) => (r.body as { turn_id: string }).turn_id);
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
    await userEvent.click(screen.getByRole("button", { name: "처음으로" }));
    expect(await screen.findByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeInTheDocument();
  });
  it("문진 끝내기를 확인하면 중간 종료 안내가 나온다", async () => {
    await startSession();
    await userEvent.click(screen.getByRole("button", { name: "문진 끝내기" }));
    await userEvent.click(await screen.findByRole("button", { name: "끝내기" }));
    expect(await screen.findByRole("heading", { name: /저장되었습니다/ })).toBeInTheDocument();
  });
  it("서버가 세션이 멈췄다고 하면(409 SESSION_NOT_ACTIVE) 상태를 읽어 멈춤 화면으로 간다", async () => {
    await startSession();
    fake.pause("RISK_SIGNAL");
    await say("네");
    expect(await screen.findByRole("heading", { name: "잠시 기다려 주세요" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("직원이 곧 도와드립니다");
  });
  it("서버가 세션이 끝났다고 하면 끝 화면으로 간다", async () => {
    await startSession();
    fake.expire();
    await say("네");
    expect(await screen.findByRole("heading", { name: /오래 입력이 없어/ })).toBeInTheDocument();
  });
});

describe("직원 호출", () => {
  it("직원을 부르면 멈춤 화면이 되고 직원이 풀면 resume_text 로 이어진다", async () => {
    // 2초 간격의 다음 읽기를 가짜 시계로 건너뛴다(계약 SessionStatePollSeconds)
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "setTimeout", "clearTimeout"], shouldAdvanceTime: true });
    await startSession();
    await userEvent.click(screen.getByRole("button", { name: "직원 부르기" }));
    expect(await screen.findByRole("heading", { name: "잠시 기다려 주세요" })).toBeInTheDocument();
    fake.resume("다시 시작하겠습니다.");
    await vi.advanceTimersByTimeAsync(2000);
    expect(await screen.findByText("다시 시작하겠습니다.")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "답변" })).toBeInTheDocument();
  });
  it("멈춤 화면에서 직원을 다시 부를 수 있다", async () => {
    await startSession();
    await userEvent.click(screen.getByRole("button", { name: "직원 부르기" }));
    await userEvent.click(await screen.findByRole("button", { name: "직원 다시 부르기" }));
    await waitFor(() => { expect(fake.requests.filter((r) => r.path.endsWith("/staff-calls"))).toHaveLength(2); });
  });
});

describe("유휴 초기화(60초)", () => {
  it("대화 중 입력 없이 60초가 지나면 처음 화면으로 돌아가고 입력이 지워진다", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "setTimeout", "clearTimeout", "Date"], shouldAdvanceTime: true });
    await startSession();
    await userEvent.type(screen.getByRole("textbox", { name: "답변" }), "남은 글");
    await vi.advanceTimersByTimeAsync(61_000);
    expect(await screen.findByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeInTheDocument();
    expect(screen.queryByDisplayValue("남은 글")).toBeNull();
  });
  it("멈춘 세션은 초기화하지 않는다(계약: 멈춘 세션은 만료하지 않는다)", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "setTimeout", "clearTimeout", "Date"], shouldAdvanceTime: true });
    await startSession();
    await userEvent.click(screen.getByRole("button", { name: "직원 부르기" }));
    await screen.findByRole("heading", { name: "잠시 기다려 주세요" });
    await vi.advanceTimersByTimeAsync(61_000);
    expect(screen.getByRole("heading", { name: "잠시 기다려 주세요" })).toBeInTheDocument();
  });
  it("시작 화면에서 입력 중이던 코드는 60초 뒤 지워진다", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "setTimeout", "clearTimeout", "Date"], shouldAdvanceTime: true });
    renderApp();
    await userEvent.click(screen.getByRole("button", { name: "1" }));
    expect(screen.getByRole("group", { name: /1자리 입력함/ })).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(61_000);
    expect(screen.getByRole("group", { name: /0자리 입력함/ })).toBeInTheDocument();
  });
});
