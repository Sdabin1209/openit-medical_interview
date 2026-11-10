// 브라우저 시험이 쓰는 vite preview 설정: 이미지의 nginx 와 같은 보안 헤더(CSP 등)를 붙여 같은 정책 아래에서 화면을 시험한다.
// 왜 nginx/security-headers.inc 를 읽는다: 정책의 정본을 한 곳에 두려고(같은 정책을 두 곳에 쓰지 않는다). 이 파일은 이미지에 들어가지 않는다.
import { readFileSync } from "node:fs";

import { defineConfig, mergeConfig } from "vitest/config";

import base from "./vite.config.ts";

const headers: Record<string, string> = {};
for (const match of readFileSync(new URL("./nginx/security-headers.inc", import.meta.url), "utf8").matchAll(/^add_header (\S+) "(.*)" always;$/gm)) {
  const [, name, value] = match;
  if (name !== undefined && value !== undefined) headers[name] = value;
}

export default mergeConfig(base, defineConfig({ preview: { headers } }));
