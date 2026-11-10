// 계약 대조: src/limits.ts 의 값이 contracts/components.yaml 과 같은지, 생성 타입이 계약과 같은지 본다(ADR 0020).
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";
import { parse } from "yaml";

import * as limits from "../../src/limits";

const root = resolve(import.meta.dirname, "../..");
const components = parse(readFileSync(resolve(root, "../../contracts/components.yaml"), "utf8")) as {
  components: { schemas: Record<string, Record<string, unknown>> };
};
const schemas = components.components.schemas;

function constOf(name: string): unknown {
  return schemas[name]?.["const"];
}

describe("src/limits.ts 는 계약의 값과 같다", () => {
  it("시작 코드는 숫자 6자리", () => {
    expect(schemas["StartCodeValue"]?.["pattern"]).toBe(`^[0-9]{${String(limits.START_CODE_LENGTH)}}$`);
    expect(schemas["StartCodeValue"]?.["maxLength"]).toBe(limits.START_CODE_LENGTH);
  });
  it("발화 상한", () => {
    expect(schemas["UtteranceText"]?.["maxLength"]).toBe(limits.UTTERANCE_MAX_LENGTH);
  });
  it.each([
    ["KioskIdleResetSeconds", limits.KIOSK_IDLE_RESET_SECONDS],
    ["KioskRequestLimitSeconds", limits.KIOSK_REQUEST_LIMIT_SECONDS],
    ["KioskRetryBudgetSeconds", limits.KIOSK_RETRY_BUDGET_SECONDS],
    ["KioskProgressNoticeSeconds", limits.KIOSK_PROGRESS_NOTICE_SECONDS],
    ["SessionStatePollSeconds", limits.SESSION_STATE_POLL_SECONDS],
  ])("%s", (name, value) => {
    expect(constOf(name)).toBe(value);
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
