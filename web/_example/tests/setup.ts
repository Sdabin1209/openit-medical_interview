import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// 왜: vitest 를 globals 없이 쓰면 Testing Library 의 자동 정리가 등록되지 않아 직접 건다(공식 안내).
afterEach(() => {
  cleanup();
});
