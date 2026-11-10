import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// 왜 한 파일: Vite 와 Vitest 가 같은 설정(플러그인, 별칭)을 쓰는 것이 공식 권장이다.
export default defineConfig({
  // 왜 base: 입구가 /kiosk/ 로 들어온 요청을 경로를 바꾸지 않고 넘기므로 자원 경로(빌드 산출물)와 라우터 basename 이 같은 접두어를 가져야 한다(ADR 접두어 절). 두 화면이 한 출처에서 같은 (경로, 메서드)를 열 수 없어서다.
  base: "/kiosk/",
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["tests/setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}", "tests/contract/**/*.test.{ts,tsx}", "tests/boundaries/**/*.test.ts"],
  },
});
