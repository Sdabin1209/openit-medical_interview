import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const root = resolve(import.meta.dirname, "../..");

describe("계약 → 타입 생성", () => {
  it("src/contract 는 contracts/ 에서 다시 생성한 결과와 같다(손으로 고치지 않았다)", () => {
    expect(() => {
      execFileSync(resolve(root, "node_modules/.bin/openapi-typescript"), ["--check"], { cwd: root, stdio: "pipe" });
    }).not.toThrow();
  });
  // UserRole·AlertEventName·AlertStreamHeartbeatSeconds·StaffAlertEvent 는 손 사본이 없고 생성 타입을 쓰므로(tsc 가 대조한다) 따로 대조하지 않는다.
});
