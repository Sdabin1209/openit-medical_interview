import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchReadyz, HttpError } from "../../src/link/health";

const root = resolve(import.meta.dirname, "../..");

afterEach(() => {
  vi.unstubAllGlobals();
});

function respond(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status }))));
}

describe("link/health 가 받는 계약(HealthReport, ProblemDetails)", () => {
  const report = { status: "pass", service: "platform" };
  const problem = { type: "about:blank", title: "의존이 준비되지 않았다", status: 503, detail: "준비되지 않은 점검: database" };

  it("200 HealthReport", async () => {
    respond(200, report);
    expect(await fetchReadyz()).toEqual(report);
  });
  it("503 ProblemDetails 도 계약이 정한 응답이다", async () => {
    respond(503, problem);
    expect(await fetchReadyz()).toEqual(problem);
  });
  it("계약에 없는 상태값은 거부한다", async () => {
    respond(200, { status: "weird", service: "platform" });
    await expect(fetchReadyz()).rejects.toBeInstanceOf(HttpError);
  });
  it("503 본문이 ProblemDetails 가 아니면 거부한다", async () => {
    respond(503, report);
    await expect(fetchReadyz()).rejects.toBeInstanceOf(HttpError);
  });
  it("계약에 없는 응답 코드는 오류다", async () => {
    respond(500, report);
    await expect(fetchReadyz()).rejects.toMatchObject({ status: 500 });
  });
});

describe("계약 → 타입 생성", () => {
  it("src/contract 는 contracts/ 에서 다시 생성한 결과와 같다(손으로 고치지 않았다)", () => {
    // 왜 --check: openapi-typescript 가 생성물이 최신인지 스스로 본다. 다르면 종료 코드 1
    expect(() => {
      execFileSync(resolve(root, "node_modules/.bin/openapi-typescript"), ["--check"], { cwd: root, stdio: "pipe" });
    }).not.toThrow();
  });
});
