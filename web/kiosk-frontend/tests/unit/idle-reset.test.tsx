// 유휴 초기화의 우리 논리(입력이 있으면 다시 센다, 경고, 끝나면 onIdle)를 가짜 타이머로 본다. 라이브러리 타이머나 실제 시간은 재지 않는다.
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IdleReset } from "../../src/components/IdleReset";

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

function advance(seconds: number) {
  act(() => {
    vi.advanceTimersByTime(seconds * 1000);
  });
}

describe("IdleReset", () => {
  it("입력 없이 60초가 지나면 onIdle", () => {
    const onIdle = vi.fn();
    render(<IdleReset active seconds={60} warnSeconds={20} onIdle={onIdle} />);
    advance(59);
    expect(onIdle).not.toHaveBeenCalled();
    advance(1);
    expect(onIdle).toHaveBeenCalledTimes(1);
  });
  it("끝나기 20초 전부터 남은 시간을 알린다", () => {
    render(<IdleReset active seconds={60} warnSeconds={20} onIdle={vi.fn()} />);
    advance(39);
    expect(screen.queryByRole("dialog")).toBeNull();
    advance(1);
    expect(screen.getByRole("dialog")).toHaveTextContent("20초 뒤에");
  });
  it("눌러서 입력하면 다시 센다", () => {
    const onIdle = vi.fn();
    render(<IdleReset active seconds={60} warnSeconds={20} onIdle={onIdle} />);
    advance(45);
    act(() => {
      document.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    });
    expect(screen.queryByRole("dialog")).toBeNull();
    advance(59);
    expect(onIdle).not.toHaveBeenCalled();
    advance(1);
    expect(onIdle).toHaveBeenCalledTimes(1);
  });
  it("계속하기 버튼으로 늘린다", () => {
    const onIdle = vi.fn();
    render(<IdleReset active seconds={60} warnSeconds={20} onIdle={onIdle} />);
    advance(50);
    act(() => {
      screen.getByRole("button", { name: "계속하기" }).click();
    });
    advance(30);
    expect(onIdle).not.toHaveBeenCalled();
  });
  it("꺼져 있으면 세지 않고, 켜면 처음부터 센다", () => {
    const onIdle = vi.fn();
    const { rerender } = render(<IdleReset active={false} seconds={60} warnSeconds={20} onIdle={onIdle} />);
    advance(120);
    expect(onIdle).not.toHaveBeenCalled();
    rerender(<IdleReset active seconds={60} warnSeconds={20} onIdle={onIdle} />);
    advance(59);
    expect(onIdle).not.toHaveBeenCalled();
    advance(1);
    expect(onIdle).toHaveBeenCalled();
  });
  it("warnSeconds 0 이면 경고 없이 조용히 초기화한다", () => {
    const onIdle = vi.fn();
    render(<IdleReset active seconds={60} warnSeconds={0} onIdle={onIdle} />);
    advance(59);
    expect(screen.queryByRole("dialog")).toBeNull();
    advance(1);
    expect(onIdle).toHaveBeenCalled();
  });
});
