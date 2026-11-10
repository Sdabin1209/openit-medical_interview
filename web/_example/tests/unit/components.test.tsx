import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "../../src/components/ConfirmDialog";
import { GreetingTable } from "../../src/components/GreetingTable";
import { HealthBadge } from "../../src/components/HealthBadge";
import { NameForm } from "../../src/components/NameForm";

describe("HealthBadge", () => {
  it("로딩 중", () => {
    render(<HealthBadge readyz={undefined} isLoading isError={false} />);
    expect(screen.getByRole("status")).toHaveTextContent("상태 확인 중");
  });
  it("준비됨", () => {
    render(<HealthBadge readyz={{ status: "ready", failed: [] }} isLoading={false} isError={false} />);
    expect(screen.getByRole("status")).toHaveTextContent("준비됨");
  });
  it("준비 안 됨은 점검 이름을 보인다", () => {
    render(<HealthBadge readyz={{ status: "not_ready", failed: ["database"] }} isLoading={false} isError={false} />);
    expect(screen.getByRole("alert")).toHaveTextContent("database");
  });
  it("읽기 실패", () => {
    render(<HealthBadge readyz={undefined} isLoading={false} isError />);
    expect(screen.getByRole("alert")).toHaveTextContent("읽지 못했다");
  });
});

describe("NameForm", () => {
  it("빈 이름은 제출되지 않고 오류를 보인다", async () => {
    const onSubmit = vi.fn();
    render(<NameForm onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: "추가" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("이름을 입력한다");
    expect(onSubmit).not.toHaveBeenCalled();
  });
  it("65자는 거부하고 64자는 받는다(경계 사례)", async () => {
    const onSubmit = vi.fn();
    render(<NameForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("이름"), "가".repeat(65));
    await userEvent.click(screen.getByRole("button", { name: "추가" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("64자");
    await userEvent.clear(screen.getByLabelText("이름"));
    await userEvent.type(screen.getByLabelText("이름"), "가".repeat(64));
    await userEvent.click(screen.getByRole("button", { name: "추가" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});

describe("GreetingTable", () => {
  it("행을 표로 보인다", () => {
    render(<GreetingTable rows={[{ id: 1, name: "다빈" }]} />);
    expect(screen.getByRole("columnheader", { name: "이름" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "다빈" })).toBeInTheDocument();
  });
  it("행이 없으면 머리글만 있다", () => {
    render(<GreetingTable rows={[]} />);
    expect(screen.queryAllByRole("cell")).toHaveLength(0);
    expect(screen.getAllByRole("columnheader")).toHaveLength(2);
  });
});

describe("ConfirmDialog", () => {
  it("확인과 취소를 알린다", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="제목" description="설명" onConfirm={onConfirm} onCancel={onCancel} />);
    expect(screen.getByRole("dialog", { name: "제목" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "확인" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "취소" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
  it("Esc 로 닫는다(접근성)", async () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="제목" description="설명" onConfirm={vi.fn()} onCancel={onCancel} />);
    await userEvent.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
  it("닫혀 있으면 아무것도 보이지 않는다", () => {
    render(<ConfirmDialog open={false} title="제목" description="설명" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
