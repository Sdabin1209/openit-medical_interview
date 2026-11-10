import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { HEARTBEAT_SECONDS } from "../../src/link/alerts";
import { USER_ROLES } from "../../src/link/session";

const root = resolve(import.meta.dirname, "../..");
const components = readFileSync(resolve(root, "../../contracts/components.yaml"), "utf-8");

/** components.yaml 의 `    <이름>:` 블록(다음 같은 들여쓰기 항목 전까지) */
function block(name: string): string {
  const match = new RegExp(`^    ${name}:.*\\n(?:(?: {5,}.*|)\\n)*`, "m").exec(components);
  if (!match) throw new Error(`계약에 ${name} 이 없다`);
  return match[0];
}

describe("계약 → 타입 생성", () => {
  it("src/contract 는 contracts/ 에서 다시 생성한 결과와 같다(손으로 고치지 않았다)", () => {
    expect(() => {
      execFileSync(resolve(root, "node_modules/.bin/openapi-typescript"), ["--check"], { cwd: root, stdio: "pipe" });
    }).not.toThrow();
  });
});

describe("생성 타입에 없어 손으로 적은 값이 계약과 같다", () => {
  it("UserRole(src/link/session.ts)", () => {
    const enumLine = /enum: \[([^\]]*)\]/.exec(block("UserRole"));
    expect(enumLine?.[1]?.split(",").map((item) => item.trim())).toEqual([...USER_ROLES]);
  });
  it("AlertStreamHeartbeatSeconds(src/link/alerts.ts)", () => {
    expect(block("AlertStreamHeartbeatSeconds")).toContain(`const: ${String(HEARTBEAT_SECONDS)}`);
  });
  it("AlertEventName 의 이벤트 이름 넷", () => {
    const enumLine = /enum: \[([^\]]*)\]/.exec(block("AlertEventName"));
    expect(enumLine?.[1]?.split(",").map((item) => item.trim())).toEqual(["alert", "resolved", "heartbeat", "resync"]);
  });
  it("StaffAlertEvent 는 event, sequence 가 필수이고 alert 는 선택", () => {
    const text = block("StaffAlertEvent");
    expect(text).toContain("required: [event, sequence]");
    expect(text).toContain("alert:");
  });
});
