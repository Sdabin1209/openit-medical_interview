import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
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

describe("link/health 가 받는 계약(Readyz)", () => {
  it("200 ready", async () => {
    respond(200, { status: "ready", failed: [] });
    expect(await fetchReadyz()).toEqual({ status: "ready", failed: [] });
  });
  it("503 not_ready 도 계약이 정한 응답이다", async () => {
    respond(503, { status: "not_ready", failed: ["database"] });
    expect(await fetchReadyz()).toEqual({ status: "not_ready", failed: ["database"] });
  });
  it("계약에 없는 상태값은 거부한다", async () => {
    respond(200, { status: "weird", failed: [] });
    await expect(fetchReadyz()).rejects.toBeInstanceOf(HttpError);
  });
  it("failed 가 문자열 배열이 아니면 거부한다", async () => {
    respond(200, { status: "ready", failed: [1] });
    await expect(fetchReadyz()).rejects.toBeInstanceOf(HttpError);
  });
  it("계약에 없는 응답 코드는 오류다", async () => {
    respond(500, { status: "ready", failed: [] });
    await expect(fetchReadyz()).rejects.toMatchObject({ status: 500 });
  });
});

describe("계약 → 타입 생성", () => {
  it("src/contract/health.d.ts 는 fixtures 의 OpenAPI 에서 생성한 그대로다(손으로 고치지 않았다)", () => {
    const generated = execFileSync(
      resolve(root, "node_modules/.bin/openapi-typescript"),
      [resolve(root, "tests/contract/fixtures/health.openapi.yaml")],
      { encoding: "utf8", cwd: root },
    );
    expect(readFileSync(resolve(root, "src/contract/health.d.ts"), "utf8")).toBe(generated);
  });
});
