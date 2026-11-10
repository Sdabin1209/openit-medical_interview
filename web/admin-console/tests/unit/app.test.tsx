import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/App";
import { openAlertStream, type Connection, type StaffAlertEvent, useStaffAlerts } from "../../src/link/alerts";
import { createFakeBackend, fakeFetch, type FakeOptions } from "../fakes/backend";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readyState = 0;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  private listeners = new Map<string, ((m: MessageEvent<string>) => void)[]>();
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  addEventListener(name: string, fn: (m: MessageEvent<string>) => void) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), fn]);
  }
  close() {
    this.closed = true;
    this.readyState = 2;
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  emit(event: StaffAlertEvent) {
    for (const fn of this.listeners.get(event.event) ?? []) fn(new MessageEvent(event.event, { data: JSON.stringify(event) }));
  }
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function renderApp(options: FakeOptions, path = "/") {
  const backend = createFakeBackend(options);
  vi.stubGlobal("fetch", fakeFetch(backend));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return backend;
}

describe("역할에 따라 화면을 보인다", () => {
  it("직원: 시작 코드와 알림 메뉴만, 첫 화면은 시작 코드", async () => {
    renderApp({ roles: ["staff"] });
    expect(await screen.findByRole("heading", { name: "시작 코드 발급" })).toBeVisible();
    const nav = screen.getByRole("navigation", { name: "화면 메뉴" });
    expect(nav).toHaveTextContent("시작 코드");
    expect(nav).toHaveTextContent("알림");
    expect(nav).not.toHaveTextContent("결과");
    expect(nav).not.toHaveTextContent("모델 패키지");
  });
  it("승인자: 모델 패키지 화면만(알림 스트림을 열지 않는다)", async () => {
    renderApp({ roles: ["release-approver"] });
    expect(await screen.findByRole("heading", { name: "모델 패키지" })).toBeVisible();
    expect(FakeEventSource.instances).toHaveLength(0);
  });
  it("역할이 없는 화면 주소로 직접 가면 권한 없음", async () => {
    renderApp({ roles: ["staff"] }, "/release");
    expect(await screen.findByText("이 화면을 볼 권한이 없다")).toBeVisible();
  });
  it("열 수 있는 화면이 없는 계정(admin 만)은 안내를 본다", async () => {
    renderApp({ roles: ["admin"] });
    expect(await screen.findByText(/열 수 있는 화면이 없다/)).toBeVisible();
  });
  it("서버가 403 을 주면 화면에 사유를 보인다(화면은 편의일 뿐 서버가 검사한다)", async () => {
    renderApp({ roles: ["clinician"] }, "/question-sets");
    expect(await screen.findByText("이 화면을 볼 권한이 없다")).toBeVisible();
  });
});

describe("화면 흐름", () => {
  it("시작 코드를 발급하면 6자리가 보인다", async () => {
    const backend = renderApp({ roles: ["staff"] });
    await userEvent.type(await screen.findByLabelText("대상자 참조값"), "subj-000123");
    await userEvent.click(screen.getByRole("button", { name: "코드 발급" }));
    expect(await screen.findByRole("img", { name: "시작 코드 4 8 2 9 1 0" })).toBeVisible();
    expect(backend.calls.find((c) => c.path === "/v1/start-codes")?.body).toEqual({ subject_ref: "subj-000123" });
  });
  it("계약에 어긋난 참조값은 서버 사유를 보인다", async () => {
    renderApp({ roles: ["staff"] });
    await userEvent.type(await screen.findByLabelText("대상자 참조값"), "잘못된 값!");
    await userEvent.click(screen.getByRole("button", { name: "코드 발급" }));
    expect(await screen.findByText(/형식이 아니다/)).toBeVisible();
  });
  it("의사: 목록 → 상세 → 확인 표시", async () => {
    renderApp({ roles: ["clinician"] }, "/results");
    await userEvent.click(await screen.findByRole("link", { name: "subj-000123 결과 보기" }));
    expect(await screen.findByRole("heading", { name: "문진 결과 subj-000123" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "확인했음 표시" }));
    expect(await screen.findByRole("status")).toHaveTextContent("doctor-1");
  });
  it("승인자: 목록에서 후보를 골라 평가 보고서를 보고 승인하면 적재 중에서 준비됨이 되고 목록의 활성 표시가 바뀐다", async () => {
    const backend = renderApp({ roles: ["release-approver"] });
    expect(await screen.findByRole("row", { name: /sha256:b+.*비활성/ })).toBeVisible();
    expect(screen.getByRole("row", { name: /sha256:a+.*\s활성/ })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: `sha256:${"b".repeat(64)} 평가 보고서 보기` }));
    expect(await screen.findByText("next_item_accuracy")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "이 패키지 활성화 승인" }));
    await userEvent.type(screen.getByLabelText("사유"), "평가 통과");
    await userEvent.click(screen.getByRole("button", { name: "승인" }));
    await waitFor(() => { expect(backend.calls.some((c) => c.path === "/v1/model-activations")).toBe(true); });
    await waitFor(() => { expect(screen.getAllByRole("status")[0]).toHaveTextContent("준비됨"); }, { timeout: 8000 });
  });
  it("운영자: 목록은 보이고 승인 버튼은 없다", async () => {
    renderApp({ roles: ["operator"] });
    await userEvent.click(await screen.findByRole("button", { name: `sha256:${"b".repeat(64)} 평가 보고서 보기` }));
    expect(await screen.findByText("next_item_accuracy")).toBeVisible();
    expect(screen.queryByRole("button", { name: "이 패키지 활성화 승인" })).toBeNull();
  });
  it("검토자: 사례를 검토하면 새 버전으로 게시된다", async () => {
    const backend = renderApp({ roles: ["reviewer"] });
    await userEvent.click(await screen.findByRole("link", { name: /Q7_1/ }));
    await userEvent.selectOptions(await screen.findByLabelText("검토 결과"), "DISMISSED");
    await userEvent.click(screen.getByRole("button", { name: "검토 결과 게시" }));
    expect(await screen.findByText("검토 결과를 게시했다")).toBeVisible();
    expect(backend.calls.find((c) => c.path.endsWith("/reviews"))?.body).toMatchObject({ base_case_version: 1, review_status: "DISMISSED" });
  });
  it("문항 세트를 올리면 목록에 생기고 활성화한다", async () => {
    const backend = renderApp({ roles: ["author"] });
    const upload = { questionnaire_id: "nh2", runtime_contract_version: 1, content: { title: "새 세트", bank: { items: [] }, flow: { start_item: "Q1", rules: [] } } };
    await userEvent.upload(await screen.findByLabelText("문항 세트 파일(JSON)"), new File([JSON.stringify(upload)], "q.json", { type: "application/json" }));
    expect(await screen.findByText(/새 세트 버전 2 을\(를\) 저장했다/)).toBeVisible();
    // 처음 활성인 버전(nh 1)의 버튼은 막혀 있고, 올린 버전은 비활성이다
    expect(await screen.findByRole("button", { name: "national-health 버전 1 활성화" })).toBeDisabled();
    await userEvent.click(await screen.findByRole("button", { name: "nh2 버전 2 활성화" }));
    await userEvent.click(screen.getByRole("button", { name: "활성화" }));
    await waitFor(() => { expect(backend.calls.some((c) => c.path.endsWith("/activation"))).toBe(true); });
    expect(await screen.findByText(/활성 버전을 .* 로 바꿨다/)).toBeVisible();
    // 목록을 다시 읽어 활성 표시가 옮겨진다
    await waitFor(() => { expect(screen.getByRole("button", { name: "nh2 버전 2 활성화" })).toBeDisabled(); });
  });
});

describe("알림 스트림", () => {
  it("스트림의 alert 이벤트가 목록과 메뉴의 열린 알림 수에 반영된다", async () => {
    renderApp({ roles: ["staff"] }, "/alerts");
    await screen.findByText("직원 호출");
    const stream = FakeEventSource.instances[0];
    expect(stream?.url).toBe("/v1/staff-alerts/stream");
    act(() => {
      stream?.open();
      stream?.emit({ event: "alert", sequence: 5, alert: { alert_id: "00000000-0000-4000-8000-000000000099", kind: "RISK", session_id: "00000000-0000-4000-8000-000000000004", device_id: "kiosk-09", raised_at: "2026-11-10T09:30:00Z" } });
    });
    expect(await screen.findByText(/기기 kiosk-09/)).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("실시간 연결됨");
    expect(screen.getByLabelText("열린 알림 2건")).toBeVisible();
  });
  it("정지 해제는 확인 뒤 RESUME 을 서버에 보낸다", async () => {
    const backend = renderApp({ roles: ["staff"] }, "/alerts");
    await userEvent.click(await screen.findByRole("button", { name: "정지 해제" }));
    await userEvent.click(screen.getByRole("button", { name: "재개" }));
    await waitFor(() => { expect(backend.calls.find((c) => c.path.endsWith("/intervention"))?.body).toEqual({ action: "RESUME" }); });
  });
  it("연결 오류: 브라우저가 포기(CLOSED)하면 연결 끊김, 다시 연결하면 새 스트림을 연다", async () => {
    renderApp({ roles: ["staff"] }, "/alerts");
    await screen.findByText("직원 호출");
    const first = FakeEventSource.instances[0];
    act(() => {
      first?.close();
      first?.onerror?.();
    });
    expect(await screen.findByRole("status")).toHaveTextContent("연결 끊김");
    await userEvent.click(screen.getByRole("button", { name: "다시 연결" }));
    await waitFor(() => { expect(FakeEventSource.instances).toHaveLength(2); });
  });
});

describe("openAlertStream", () => {
  it("heartbeat 가 세 번(45초) 끊기면 연결을 버리고 새로 연다", () => {
    vi.useFakeTimers();
    const states: Connection[] = [];
    const close = openAlertStream({ onEvent: vi.fn(), onConnection: (s) => states.push(s) });
    const first = FakeEventSource.instances[0];
    first?.open();
    vi.advanceTimersByTime(44_000);
    expect(FakeEventSource.instances).toHaveLength(1);
    first?.emit({ event: "heartbeat", sequence: 0 });
    vi.advanceTimersByTime(44_000);
    expect(FakeEventSource.instances).toHaveLength(1);
    vi.advanceTimersByTime(2_000);
    expect(first?.closed).toBe(true);
    expect(FakeEventSource.instances).toHaveLength(2);
    close();
    expect(FakeEventSource.instances[1]?.closed).toBe(true);
    vi.advanceTimersByTime(100_000);
    expect(FakeEventSource.instances).toHaveLength(2);
  });
  it("resync 를 받으면 목록을 다시 읽는다", async () => {
    const backend = createFakeBackend();
    vi.stubGlobal("fetch", fakeFetch(backend));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useStaffAlerts(true), { wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> });
    await waitFor(() => { expect(result.current.alerts).toHaveLength(2); });
    const before = backend.calls.filter((c) => c.path === "/v1/staff-alerts").length;
    act(() => { FakeEventSource.instances[0]?.emit({ event: "resync", sequence: 0 }); });
    await waitFor(() => { expect(backend.calls.filter((c) => c.path === "/v1/staff-alerts").length).toBe(before + 1); });
  });
  it("꺼져 있으면(직원도 의사도 아님) 스트림도 목록도 열지 않는다", async () => {
    const backend = createFakeBackend();
    vi.stubGlobal("fetch", fakeFetch(backend));
    const client = new QueryClient();
    renderHook(() => useStaffAlerts(false), { wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> });
    await new Promise((r) => setTimeout(r, 20));
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(backend.calls).toHaveLength(0);
  });
});
