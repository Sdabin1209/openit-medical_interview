import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConversationView, type ConversationViewProps } from "../../src/components/ConversationView";
import { EndView } from "../../src/components/EndView";
import { PausedView } from "../../src/components/PausedView";

function props(over: Partial<ConversationViewProps> = {}): ConversationViewProps {
  return {
    title: "국가건강검진 문진표",
    sentence: "담배를 피우시나요?",
    staffHelpNotice: false,
    draft: "",
    onDraftChange: vi.fn(),
    maxLength: 300,
    onSend: vi.fn(),
    busy: false,
    slow: false,
    failure: null,
    voiceInput: { state: "ready", interim: "", onToggle: vi.fn() },
    voiceOutput: { available: true, onReplay: vi.fn() },
    onEnd: vi.fn(),
    onStaffCall: vi.fn(),
    staffCallBusy: false,
    ...over,
  };
}

describe("ConversationView", () => {
  it("문장을 크게 보이고 빈 발화는 보낼 수 없다", () => {
    render(<ConversationView {...props()} />);
    expect(screen.getByText("담배를 피우시나요?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "보내기" })).toBeDisabled();
  });
  it("공백뿐인 발화도 보낼 수 없다(경계)", () => {
    render(<ConversationView {...props({ draft: "   " })} />);
    expect(screen.getByRole("button", { name: "보내기" })).toBeDisabled();
  });
  it("발화 상한을 입력칸에 건다(300자, 계약 UtteranceText)", () => {
    render(<ConversationView {...props({ draft: "가".repeat(300) })} />);
    expect(screen.getByRole("textbox", { name: "답변" })).toHaveAttribute("maxlength", "300");
    expect(screen.getByText("300 / 300자")).toBeInTheDocument();
  });
  it("글자를 쓰면 알리고 보내기를 누른다", async () => {
    const onDraftChange = vi.fn();
    const onSend = vi.fn();
    render(<ConversationView {...props({ draft: "하루 한 갑", onDraftChange, onSend })} />);
    await userEvent.type(screen.getByRole("textbox", { name: "답변" }), "요");
    expect(onDraftChange).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "보내기" }));
    expect(onSend).toHaveBeenCalled();
  });
  it("기다리는 중에는 입력과 보내기가 막히고, 늦으면 진행 표시를 보인다", () => {
    render(<ConversationView {...props({ draft: "네", busy: true, slow: true })} />);
    expect(screen.getByRole("textbox", { name: "답변" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "보내기" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("처리하고 있습니다");
  });
  it("실패 신호와 연결 실패를 알린다", () => {
    const { rerender } = render(<ConversationView {...props({ failure: "TURN_FAILED" })} />);
    expect(screen.getByRole("alert")).toHaveTextContent("잘 이해하지 못했습니다");
    rerender(<ConversationView {...props({ failure: "UNREACHABLE" })} />);
    expect(screen.getByRole("alert")).toHaveTextContent("연결이 원활하지 않습니다");
  });
  it("음성 인식을 쓸 수 없으면 말하기 버튼이 없고 글자 입력만 남는다", () => {
    render(<ConversationView {...props({ voiceInput: { state: "unavailable", interim: "", onToggle: vi.fn() }, voiceOutput: { available: false, onReplay: vi.fn() } })} />);
    expect(screen.queryByRole("button", { name: "말하기" })).toBeNull();
    expect(screen.queryByRole("button", { name: "다시 듣기" })).toBeNull();
    expect(screen.getByRole("textbox", { name: "답변" })).toBeEnabled();
  });
  it("듣는 중에는 인식 중인 글을 보이고 버튼이 말 끝내기가 된다", async () => {
    const onToggle = vi.fn();
    render(<ConversationView {...props({ voiceInput: { state: "listening", interim: "하루에", onToggle } })} />);
    expect(screen.getByRole("status")).toHaveTextContent("하루에");
    await userEvent.click(screen.getByRole("button", { name: "말 끝내기" }));
    expect(onToggle).toHaveBeenCalled();
  });
  it("직원 도움 안내가 오면 직원 부르기를 안내한다", () => {
    render(<ConversationView {...props({ staffHelpNotice: true })} />);
    expect(screen.getByRole("note")).toHaveTextContent("직원 부르기");
  });
  it("직원 부르기", async () => {
    const onStaffCall = vi.fn();
    render(<ConversationView {...props({ onStaffCall })} />);
    await userEvent.click(screen.getByRole("button", { name: "직원 부르기" }));
    expect(onStaffCall).toHaveBeenCalled();
  });
  it("끝내기는 확인을 거치고 Esc 로 닫으면 끝나지 않는다", async () => {
    const onEnd = vi.fn();
    render(<ConversationView {...props({ onEnd })} />);
    await userEvent.click(screen.getByRole("button", { name: "문진 끝내기" }));
    expect(await screen.findByRole("dialog", { name: "문진을 끝낼까요?" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(onEnd).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "문진 끝내기" }));
    await userEvent.click(await screen.findByRole("button", { name: "끝내기" }));
    expect(onEnd).toHaveBeenCalledTimes(1);
  });
});

describe("PausedView", () => {
  it.each([
    ["STAFF_CALL", "직원을 불렀습니다"],
    ["RISK_SIGNAL", "직원이 곧 도와드립니다"],
  ] as const)("%s 까닭을 구분해 안내한다", (reason, text) => {
    render(<PausedView reason={reason} onCallAgain={vi.fn()} callBusy={false} callFailed={false} />);
    expect(screen.getByRole("status")).toHaveTextContent(text);
  });
  it("직원 다시 부르기, 전달 실패 안내", async () => {
    const onCallAgain = vi.fn();
    render(<PausedView reason="STAFF_CALL" onCallAgain={onCallAgain} callBusy={false} callFailed />);
    expect(screen.getByRole("alert")).toHaveTextContent("전달되지 않았습니다");
    await userEvent.click(screen.getByRole("button", { name: "직원 다시 부르기" }));
    expect(onCallAgain).toHaveBeenCalled();
  });
});

describe("EndView", () => {
  it.each([
    ["COMPLETE", "문진이 끝났습니다"],
    ["PARTIAL", "저장되었습니다"],
    ["EXPIRED", "오래 입력이 없어"],
  ] as const)("%s", (outcome, text) => {
    render(<EndView outcome={outcome} onDone={vi.fn()} />);
    expect(screen.getByRole("heading")).toHaveTextContent(text);
  });
  it("마지막 문장과 처음으로 버튼", async () => {
    const onDone = vi.fn();
    render(<EndView outcome="COMPLETE" closingText="감사합니다." onDone={onDone} />);
    expect(screen.getByText("감사합니다.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "처음으로" }));
    expect(onDone).toHaveBeenCalled();
  });
});
