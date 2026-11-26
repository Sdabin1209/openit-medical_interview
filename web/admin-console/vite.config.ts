import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

// 개발 서버(npm run dev)에서만 가짜 survey-service·model-runtime·oauth2-proxy 를 MSW 브라우저 모드로 붙인다(영역 ADR 0011).
// 왜 플러그인: 진입점을 dev/main.tsx 로 바꾸고 워커 파일 폴더를 dev/public 으로 바꾸는 일을 serve 에만 건다.
// 빌드·미리보기·시험(vitest)에는 걸리지 않아 src 와 이미지는 그대로다. 끄려면 VITE_DEV_MOCK=off npm run dev
// 감수: 이 모드에서는 public/sw.js(웹 푸시)를 서빙하지 않는다. 한 범위(/console/)에 서비스 워커는 하나라 MSW 워커와 함께 둘 수 없다
function devMock(): Plugin {
  return {
    name: "openit-dev-mock",
    apply: (_config, env) => env.command === "serve" && env.isPreview !== true && env.mode !== "test" && process.env["VITE_DEV_MOCK"] !== "off",
    config: () => ({ publicDir: "dev/public" }),
    // 왜 pre: Vite 가 base 접두어를 붙이기 전의 index.html 에서 바꾼다
    transformIndexHtml: { order: "pre", handler: (html) => html.replace('src="/src/main.tsx"', 'src="/dev/main.tsx"') },
  };
}

export default defineConfig({
  base: "/console/",
  plugins: [react(), devMock()],
  test: {
    environment: "jsdom",
    setupFiles: ["tests/setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}", "tests/contract/**/*.test.{ts,tsx}", "tests/boundaries/**/*.test.ts"],
  },
});
