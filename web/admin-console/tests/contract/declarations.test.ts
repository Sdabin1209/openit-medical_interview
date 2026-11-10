// 선언 파일 대조: exposure.json·inputs.json 이 계약 스키마(Exposure, ContainerInputs)를 지키고 Dockerfile 이 ARG 로 라벨을 다는지 본다.
// 왜: 두 파일이 이미지 라벨 io.openit.exposure·io.openit.inputs 의 원본이고 받는 쪽(입구 생성기, deploy)은 값을 다시 검증하지 않는다(R7).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";

const root = resolve(import.meta.dirname, "../..");
const components = (parse(readFileSync(resolve(root, "../../contracts/components.yaml"), "utf8")) as { components: unknown }).components;

function validate(schema: string, value: unknown): string[] {
  // strict 를 끄는 이유: 계약 스키마의 x-owner·x-basis 같은 확장 칸을 ajv 가 모르는 키워드로 거부하지 않게 한다(검증 규칙은 그대로)
  const ajv = new Ajv2020({ strict: false, allErrors: true });
  addFormats(ajv);
  const check = ajv.compile({ components, $ref: `#/components/schemas/${schema}` });
  check(value);
  return (check.errors ?? []).map((error) => `${error.instancePath} ${error.message ?? ""}`);
}

const read = (name: string): unknown => JSON.parse(readFileSync(resolve(root, name), "utf8"));
const exposure = read("exposure.json") as { routes: { path_prefix: string; audience: string }[]; egress: unknown[] };
const inputs = read("inputs.json") as { run_as_uid: number; env: unknown[]; processes: { argv: string[] }[] };
const dockerfile = readFileSync(resolve(root, "Dockerfile"), "utf8");
const viteConfig = readFileSync(resolve(root, "vite.config.ts"), "utf8");
const nginx = readFileSync(resolve(root, "nginx/default.conf"), "utf8");

describe("선언 파일", () => {
  it("exposure.json 은 계약 Exposure 를 지킨다", () => {
    expect(validate("Exposure", exposure)).toEqual([]);
  });
  it("inputs.json 은 계약 ContainerInputs 를 지킨다", () => {
    expect(validate("ContainerInputs", inputs)).toEqual([]);
  });
  it("계약 스키마가 잘못된 값을 거부한다(대조 시험이 항상 통과하지 않는지)", () => {
    expect(validate("Exposure", { routes: [{ path_prefix: "v1", methods: ["GET"], audience: "HUMAN_OIDC" }], egress: [] })).not.toEqual([]);
  });
  it("화면 경로는 사람 인증(OIDC) 뒤에만 열고 나가는 호출이 없다(서버 호출은 브라우저가 같은 출처로 입구에 하고 입구가 각 서비스의 Exposure 로 나눈다)", () => {
    expect(exposure.routes.map((route) => route.audience)).toEqual(["HUMAN_OIDC"]);
    expect(exposure.egress).toEqual([]);
  });
  it("노출 접두어, Vite base, nginx 경로가 같다(입구는 경로를 바꾸지 않고 넘긴다)", () => {
    const prefix = exposure.routes[0]?.path_prefix ?? "";
    expect(prefix).toBe("/console/");
    expect(viteConfig).toContain(`base: "${prefix}"`);
    expect(nginx).toContain(`location ${prefix} {`);
    expect(nginx).toContain(`/console/index.html`);
    expect(dockerfile).toContain("/usr/share/nginx/html/console");
  });
  it("환경 입력이 없다(정적 화면은 설정을 환경 변수로 받지 않는다)", () => {
    expect(inputs.env).toEqual([]);
  });
  it("실행 사용자와 시작 명령이 Dockerfile 과 같다(USER 101, 기반 이미지의 진입점)", () => {
    expect(dockerfile).toMatch(/^USER 101:101$/m);
    expect(inputs.run_as_uid).toBe(101);
    expect(inputs.processes).toHaveLength(1);
    expect(inputs.processes[0]?.argv[0]).toBe("/docker-entrypoint.sh");
  });
});

describe("Dockerfile 라벨", () => {
  it("exposure·inputs 는 ARG 로 받아 라벨로 단다. JOBS 는 없다", () => {
    expect(dockerfile).toMatch(/^ARG EXPOSURE$/m);
    expect(dockerfile).toMatch(/^ARG INPUTS$/m);
    expect(dockerfile).toContain('io.openit.exposure="${EXPOSURE}"');
    expect(dockerfile).toContain('io.openit.inputs="${INPUTS}"');
    expect(dockerfile).not.toMatch(/io\.openit\.jobs/);
  });
  it("선언 파일의 내용을 Dockerfile 에 글자 그대로 복사하지 않는다", () => {
    expect(dockerfile).not.toContain("HUMAN_OIDC");
    expect(dockerfile).not.toContain("run_as_uid");
  });
});
