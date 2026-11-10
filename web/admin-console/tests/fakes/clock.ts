import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

/**
 * 가짜 시계. 실제 시간은 흐르지 않고 vi.advanceTimersByTime 으로만 넘어간다.
 * 왜: 제품의 재읽기 간격(예: 3초)을 실제로 기다리면 시험이 시스템 부하에 흔들린다.
 * Testing Library 의 waitFor/findBy 는 전역 `jest.advanceTimersByTime` 이 있으면 가짜 타이머로 판단해 시계를 직접 넘긴다(Vitest 와 잇는 표준 방법).
 */
export function useFakeClock() {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "setTimeout", "clearTimeout", "Date"] });
  (globalThis as { jest?: unknown }).jest = { advanceTimersByTime: (ms: number) => vi.advanceTimersByTime(ms) };
  return userEvent.setup({ delay: null, advanceTimers: (ms) => vi.advanceTimersByTime(ms) });
}

export function useRealClock() {
  vi.useRealTimers();
  delete (globalThis as { jest?: unknown }).jest;
}
