import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// 왜 한 파일: Vite 와 Vitest 가 같은 설정(플러그인, 별칭)을 쓰는 것이 공식 권장이다.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["tests/setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}", "tests/contract/**/*.test.{ts,tsx}", "tests/boundaries/**/*.test.ts"],
  },
});
