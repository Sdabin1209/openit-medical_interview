import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/App";

function renderApp(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("준비 상태를 서버에서 읽어 보인다", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(Response.json({ status: "ready", failed: [] }))));
    renderApp();
    expect(await screen.findByText("준비됨")).toBeInTheDocument();
  });
  it("이름을 입력하고 확인하면 표에 행이 생긴다", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(Response.json({ status: "ready", failed: [] }))));
    renderApp();
    await userEvent.type(screen.getByLabelText("이름"), "다빈");
    await userEvent.click(screen.getByRole("button", { name: "추가" }));
    await userEvent.click(await screen.findByRole("button", { name: "확인" }));
    expect(await screen.findByRole("cell", { name: "다빈" })).toBeInTheDocument();
  });
  it("라우팅: /about", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderApp("/about");
    expect(screen.getByText("템플릿 예시 화면")).toBeInTheDocument();
  });
});
