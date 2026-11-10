import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createFakeBackend, fakeFetch } from "../fakes/backend";
import { useFakeClock, useRealClock } from "../fakes/clock";
import { applyAlertEvent, base64UrlToBytes, enablePush, type StaffAlertEvent } from "../../src/link/alerts";
import { ApiError } from "../../src/link/http";
import { useActivateModelPackage, useModelStatus } from "../../src/link/model";
import { fetchCurrentUser, parseUser } from "../../src/link/session";
import { useIssueStartCode, useResult } from "../../src/link/survey";

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return ({ children }: { children: ReactNode }) => createElement(QueryClientProvider, { client }, children);
}

let backend = createFakeBackend();
beforeEach(() => {
  backend = createFakeBackend();
  vi.stubGlobal("fetch", fakeFetch(backend));
});
afterEach(() => {
  useRealClock();
  vi.unstubAllGlobals();
});

describe("session", () => {
  it("userinfo 의 groups 에서 계약 역할만 남긴다", () => {
    expect(parseUser({ preferredUsername: "김", groups: ["staff", "offline_access", "release-approver"] })).toEqual({ name: "김", roles: ["staff", "release-approver"] });
  });
  it("이름은 preferredUsername, email, user 순서", () => {
    expect(parseUser({ email: "a@b" }).name).toBe("a@b");
    expect(parseUser({}).name).toBe("");
  });
  it("401 이면 oauth2-proxy 로그인으로 보낸다(rd 는 지금 경로)", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { origin: window.location.origin, pathname: "/console/results", search: "?x=1", assign });
    vi.stubGlobal("fetch", () => Promise.resolve(new Response("", { status: 401 })));
    await expect(fetchCurrentUser()).rejects.toThrow();
    expect(assign).toHaveBeenCalledWith("/oauth2/start?rd=%2Fconsole%2Fresults%3Fx%3D1");
  });
});

describe("link 가 받는 계약 응답", () => {
  it("시작 코드 발급은 Idempotency-Key 를 싣고, 성공하기 전에는 같은 키로 다시 보낸다", async () => {
    const keys: string[] = [];
    const inner = fakeFetch(backend);
    let calls = 0;
    vi.stubGlobal("fetch", (request: Request) => {
      calls += 1;
      keys.push(request.headers.get("Idempotency-Key") ?? "");
      if (calls === 1) return Promise.resolve(new Response(JSON.stringify({ type: "about:blank", title: "잠시 후", status: 503 }), { status: 503, headers: { "content-type": "application/problem+json" } }));
      return inner(request);
    });
    const { result } = renderHook(() => useIssueStartCode(), { wrapper: wrapper() });
    result.current.mutate({ subject_ref: "subj-1" });
    await waitFor(() => { expect(result.current.isError).toBe(true); });
    result.current.mutate({ subject_ref: "subj-1" });
    await waitFor(() => { expect(result.current.isSuccess).toBe(true); });
    expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/);
    expect(keys[1]).toBe(keys[0]);
    expect(result.current.data?.code).toMatch(/^[0-9]{6}$/);
    // 성공한 뒤의 다음 발급은 새 키를 쓴다
    result.current.mutate({ subject_ref: "subj-2" });
    await waitFor(() => { expect(keys).toHaveLength(3); });
    expect(keys[2]).not.toBe(keys[0]);
  });

  it("오류 응답은 Problem Details 를 담은 ApiError 가 된다(403)", async () => {
    backend = createFakeBackend({ roles: ["staff"] });
    vi.stubGlobal("fetch", fakeFetch(backend));
    const { result } = renderHook(() => useResult("00000000-0000-4000-8000-000000000001"), { wrapper: wrapper() });
    await waitFor(() => { expect(result.current.isError).toBe(true); });
    const error = result.current.error;
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 403, problem: { status: 403, title: "권한이 없다" } });
  });

  it("결과 상세는 창 초점으로 다시 읽지 않는다(읽을 때마다 접근 기록이 남는다)", async () => {
    useFakeClock();
    const { result } = renderHook(() => useResult("00000000-0000-4000-8000-000000000001"), { wrapper: wrapper() });
    await waitFor(() => { expect(result.current.isSuccess).toBe(true); });
    window.dispatchEvent(new Event("focus"));
    document.dispatchEvent(new Event("visibilitychange"));
    // 가짜 시계로 재읽기가 일어날 만큼 넘긴 뒤에도 읽기는 한 번뿐이어야 한다
    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
    expect(backend.calls.filter((c) => c.path.startsWith("/v1/results/"))).toHaveLength(1);
  });

  it("활성화 승인 본문에 신원을 싣지 않는다(digest 와 사유만)", async () => {
    const { result } = renderHook(() => useActivateModelPackage(), { wrapper: wrapper() });
    result.current.mutate({ packageDigest: `sha256:${"b".repeat(64)}`, reason: "평가 통과" });
    await waitFor(() => { expect(result.current.isSuccess).toBe(true); });
    expect(backend.calls.find((c) => c.path === "/v1/model-activations")?.body).toEqual({ package_digest: `sha256:${"b".repeat(64)}`, reason: "평가 통과" });
  });

  it("적재 중이면 상태를 다시 읽고 끝나면 멈춘다", async () => {
    useFakeClock();
    const { result } = renderHook(() => ({ status: useModelStatus(), activate: useActivateModelPackage() }), { wrapper: wrapper() });
    await waitFor(() => { expect(result.current.status.data?.state).toBe("READY"); });
    result.current.activate.mutate({ packageDigest: `sha256:${"b".repeat(64)}`, reason: "r" });
    await waitFor(() => { expect(result.current.status.data?.state).toBe("LOADING"); });
    await waitFor(() => { expect(result.current.status.data?.state).toBe("READY"); }, { timeout: 8000 });
  });
});

describe("알림 이벤트 반영(applyAlertEvent)", () => {
  const alert = { alert_id: "a1", kind: "RISK", session_id: "s1", raised_at: "2026-11-10T08:00:00Z" } as const;
  const base = new Map();
  it("alert 는 더하고 resolved 는 같은 알림을 바꾼다", () => {
    const added = applyAlertEvent(base, { event: "alert", sequence: 1, alert });
    expect(added.get("a1")).toEqual(alert);
    const resolved = applyAlertEvent(added, { event: "resolved", sequence: 2, alert: { ...alert, resolved_at: "2026-11-10T08:05:00Z" } });
    expect(resolved.get("a1")?.resolved_at).toBe("2026-11-10T08:05:00Z");
    expect(resolved.size).toBe(1);
  });
  it("heartbeat 와 resync 는 목록을 바꾸지 않는다", () => {
    for (const event of ["heartbeat", "resync"] as const) {
      const e: StaffAlertEvent = { event, sequence: 3 };
      expect(applyAlertEvent(base, e)).toBe(base);
    }
  });
});

describe("웹 푸시 구독", () => {
  it("base64url 키를 바이트로 바꾼다(패딩 없음, - 와 _)", () => {
    expect([...base64UrlToBytes("-_8")]).toEqual([251, 255]);
  });

  it("권한 → 공개키 → 구독 → 서버 등록 순서로 하고, 서버에는 endpoint 와 keys 만 보낸다", async () => {
    const subscribe = vi.fn(() => Promise.resolve({ toJSON: () => ({ endpoint: "https://push.example/abc", keys: { p256dh: "P".repeat(87), auth: "A".repeat(22) } }) }));
    const registration = { pushManager: { subscribe } };
    vi.stubGlobal("PushManager", function PushManager() {});
    vi.stubGlobal("Notification", { requestPermission: () => Promise.resolve("granted") });
    Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { register: () => Promise.resolve(registration), ready: Promise.resolve(registration) } });
    await enablePush();
    expect(subscribe).toHaveBeenCalledWith(expect.objectContaining({ userVisibleOnly: true }));
    expect(backend.calls.find((c) => c.path === "/v1/push-subscriptions")?.body).toEqual({ endpoint: "https://push.example/abc", keys: { p256dh: "P".repeat(87), auth: "A".repeat(22) } });
  });

  it("권한을 거절하면 구독하지 않는다", async () => {
    vi.stubGlobal("PushManager", function PushManager() {});
    vi.stubGlobal("Notification", { requestPermission: () => Promise.resolve("denied") });
    Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: {} });
    await expect(enablePush()).rejects.toThrow("권한");
    expect(backend.calls.some((c) => c.path === "/v1/push-subscriptions")).toBe(false);
  });
});
