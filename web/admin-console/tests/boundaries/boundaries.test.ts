// 경계 점검이 위반을 실제로 잡는지 본다. fixtures 는 일부러 규칙을 어긴 파일이다(본 lint 에서는 제외).
import { resolve } from "node:path";

import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const root = resolve(import.meta.dirname, "../..");
const fixtures = resolve(import.meta.dirname, "fixtures/src");

async function violations(relative: string): Promise<string[]> {
  const eslint = new ESLint({ cwd: root, ignore: false });
  const [result] = await eslint.lintFiles([resolve(fixtures, relative)]);
  return (result?.messages ?? []).filter((m) => m.ruleId === "boundaries/dependencies" || m.ruleId === "no-restricted-globals").map((m) => m.ruleId ?? "");
}

describe("영역 경계", () => {
  it("컴포넌트는 자기 폴더의 파일을 import 할 수 있다", async () => {
    expect(await violations("components/A/uses-own.ts")).toEqual([]);
  });
  it("컴포넌트는 contract 를 import 할 수 있다", async () => {
    expect(await violations("components/A/ok-contract.ts")).toEqual([]);
  });
  it("컴포넌트는 다른 컴포넌트를 import 할 수 없다", async () => {
    expect(await violations("components/A/bad-other-component.ts")).toEqual(["boundaries/dependencies"]);
  });
  it("컴포넌트는 link 를 import 할 수 없다", async () => {
    expect(await violations("components/A/bad-link.ts")).toEqual(["boundaries/dependencies"]);
  });
  it("컴포넌트는 fetch 를 쓸 수 없다", async () => {
    expect(await violations("components/A/bad-fetch.ts")).toEqual(["no-restricted-globals"]);
  });
  it("link 는 fetch 를 쓸 수 있다", async () => {
    expect(await violations("link/l.ts")).toEqual([]);
  });
  it("link 는 컴포넌트를 import 할 수 없다", async () => {
    expect(await violations("link/bad-component.ts")).toEqual(["boundaries/dependencies"]);
  });
  it("contract 는 link 를 import 할 수 없다", async () => {
    expect(await violations("contract/bad-link.ts")).toEqual(["boundaries/dependencies"]);
  });
  it("조립 층(app)은 모두 import 할 수 있다", async () => {
    expect(await violations("app-ok.ts")).toEqual([]);
  });
});
