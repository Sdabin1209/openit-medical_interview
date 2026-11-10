import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StartView, type StartViewError } from "../../src/components/StartView";

const one = [{ questionnaire_id: "a", title: "A 문진표" }];
const two = [...one, { questionnaire_id: "b", title: "B 문진표" }];

async function typeCode(code: string) {
  for (const digit of code) await userEvent.click(screen.getByRole("button", { name: digit }));
}

describe("StartView 시작 코드 키패드", () => {
  it("6자리가 차야 시작하기가 눌린다", async () => {
    render(<StartView codeLength={6} questionnaires={one} onStart={vi.fn()} />);
    const start = screen.getByRole("button", { name: "시작하기" });
    await typeCode("12345");
    expect(start).toBeDisabled();
    await typeCode("6");
    expect(start).toBeEnabled();
  });
  it("6자리를 넘겨 입력되지 않는다(경계)", async () => {
    render(<StartView codeLength={6} questionnaires={one} onStart={vi.fn()} />);
    await typeCode("1234567");
    expect(screen.getByRole("group", { name: /6자리 입력함/ })).toBeInTheDocument();
  });
  it("지움과 모두 지움", async () => {
    render(<StartView codeLength={6} questionnaires={one} onStart={vi.fn()} />);
    await typeCode("123");
    await userEvent.click(screen.getByRole("button", { name: "지움" }));
    expect(screen.getByRole("group", { name: /2자리 입력함/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "모두 지움" }));
    expect(screen.getByRole("group", { name: /0자리 입력함/ })).toBeInTheDocument();
  });
  it("물리 키보드의 숫자·Backspace·Enter 도 받는다", async () => {
    const onStart = vi.fn(() => Promise.resolve(null));
    render(<StartView codeLength={6} questionnaires={one} onStart={onStart} />);
    screen.getByRole("region", { name: "시작 코드를 입력해 주세요" }).focus();
    await userEvent.keyboard("1234577{Backspace}6{Enter}");
    expect(onStart).toHaveBeenCalledWith({ startCode: "123456" });
  });
  it("문진표가 하나면 바로 시작한다(questionnaire_id 없이)", async () => {
    const onStart = vi.fn(() => Promise.resolve(null));
    render(<StartView codeLength={6} questionnaires={one} onStart={onStart} />);
    await typeCode("123456");
    await userEvent.click(screen.getByRole("button", { name: "시작하기" }));
    expect(onStart).toHaveBeenCalledWith({ startCode: "123456" });
  });
  it("문진표가 둘 이상이면 코드 뒤에 고르게 하고 고른 id 를 보낸다", async () => {
    const onStart = vi.fn(() => Promise.resolve(null));
    render(<StartView codeLength={6} questionnaires={two} onStart={onStart} />);
    await typeCode("123456");
    await userEvent.click(screen.getByRole("button", { name: "시작하기" }));
    expect(onStart).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "B 문진표" }));
    expect(onStart).toHaveBeenCalledWith({ startCode: "123456", questionnaireId: "b" });
  });
  it.each<[StartViewError, RegExp]>([
    ["INVALID", /코드가 맞지 않습니다/],
    ["EXPIRED", /사용 시간이 지났습니다/],
    ["USED", /이미 사용한 코드/],
    ["RATE_LIMITED", /잠시 후에 다시 입력/],
  ])("%s 이면 알리고 코드를 지워 다시 입력하게 한다", async (failure, message) => {
    render(<StartView codeLength={6} questionnaires={one} onStart={() => Promise.resolve(failure)} />);
    await typeCode("123456");
    await userEvent.click(screen.getByRole("button", { name: "시작하기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("group", { name: /0자리 입력함/ })).toBeInTheDocument();
  });
  it("연결 실패는 코드를 지우지 않아 다시 누르면 된다", async () => {
    render(<StartView codeLength={6} questionnaires={one} onStart={() => Promise.resolve("UNAVAILABLE")} />);
    await typeCode("123456");
    await userEvent.click(screen.getByRole("button", { name: "시작하기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("연결할 수 없습니다");
    expect(screen.getByRole("button", { name: "시작하기" })).toBeEnabled();
  });
  it("입력 중인지 알린다", async () => {
    const onDirtyChange = vi.fn();
    render(<StartView codeLength={6} questionnaires={one} onStart={vi.fn()} onDirtyChange={onDirtyChange} />);
    await typeCode("1");
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    await userEvent.click(screen.getByRole("button", { name: "모두 지움" }));
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
  });
});
