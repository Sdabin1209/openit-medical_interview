import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AlertView } from "../../src/components/AlertView";
import { FailureCaseDetail } from "../../src/components/FailureReviewView";
import { Layout } from "../../src/components/Layout";
import { QuestionSetView } from "../../src/components/QuestionSetView";
import { ReleaseView } from "../../src/components/ReleaseView";
import { ResultDetail } from "../../src/components/ResultDetail";
import { ResultList } from "../../src/components/ResultList";
import { StartCodeView } from "../../src/components/StartCodeView";
import type { components } from "../../src/contract/survey-service";

type S = components["schemas"];
afterEach(() => {
  vi.restoreAllMocks();
});

describe("StartCodeView", () => {
  const base = { questionnaires: [], issued: undefined, pending: false, problem: undefined };
  it("참조값이 비면 보내지 않고 오류를 보인다", async () => {
    const onIssue = vi.fn();
    render(<StartCodeView {...base} onIssue={onIssue} />);
    await userEvent.click(screen.getByRole("button", { name: "코드 발급" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("대상자 참조값");
    expect(onIssue).not.toHaveBeenCalled();
  });
  it("참조값과 고른 문진표를 보낸다", async () => {
    const onIssue = vi.fn();
    render(<StartCodeView {...base} questionnaires={[{ questionnaire_id: "nh", title: "건강검진" }]} onIssue={onIssue} />);
    await userEvent.type(screen.getByLabelText("대상자 참조값"), "subj-1");
    await userEvent.selectOptions(screen.getByLabelText("문진표"), "nh");
    await userEvent.click(screen.getByRole("button", { name: "코드 발급" }));
    expect(onIssue).toHaveBeenCalledWith({ subjectRef: "subj-1", questionnaireId: "nh" }, expect.anything());
  });
  it("6자리 코드를 한 숫자씩 칸에 보이고 QR 은 없다", () => {
    render(<StartCodeView {...base} issued={{ code: "482910", issued_at: "2026-11-10T09:00:00Z", expires_at: "2026-11-10T09:10:00Z" }} onIssue={vi.fn()} />);
    const code = screen.getByRole("img", { name: "시작 코드 4 8 2 9 1 0" });
    expect(within(code).getAllByText(/^\d$/)).toHaveLength(6);
    expect(screen.queryByText(/QR/)).toBeNull();
  });
  it("출력 버튼은 브라우저 인쇄를 부른다", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    render(<StartCodeView {...base} issued={{ code: "000000", issued_at: "2026-11-10T09:00:00Z", expires_at: "2026-11-10T09:10:00Z" }} onIssue={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "출력" }));
    expect(print).toHaveBeenCalled();
  });
  it("서버가 거절하면 칸별 사유를 보인다", () => {
    render(<StartCodeView {...base} problem={{ type: "about:blank", title: "요청이 계약과 다르다", status: 400, errors: [{ pointer: "/subject_ref", detail: "형식이 아니다" }] }} onIssue={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("/subject_ref: 형식이 아니다");
  });
});

describe("AlertView", () => {
  const alert = (over: Partial<S["StaffAlert"]>): S["StaffAlert"] => ({ alert_id: "a1", kind: "RISK", session_id: "s1", raised_at: "2026-11-10T08:00:00Z", ...over });
  const props = {
    alerts: [] as S["StaffAlert"][],
    connection: "open" as const,
    loading: false,
    errorMessage: undefined,
    hasMore: false,
    canIntervene: true,
    pushState: "off" as const,
    pushMessage: undefined,
    interventionError: undefined,
    onIntervene: vi.fn(),
    onLoadMore: vi.fn(),
    onReconnect: vi.fn(),
    onEnablePush: vi.fn(),
    renderResultLink: (id: string) => <a href={`/results/${id}`}>결과 보기</a>,
  };
  it("알림이 없으면 없다고 한다(빈 목록)", () => {
    render(<AlertView {...props} />);
    expect(screen.getByText("알림이 없다")).toBeVisible();
  });
  it("확인은 바로, 정지 해제는 대화상자 확인 뒤에만 보내고 Esc 로 닫으면 보내지 않는다", async () => {
    const onIntervene = vi.fn();
    render(<AlertView {...props} onIntervene={onIntervene} alerts={[alert({})]} />);
    await userEvent.click(screen.getByRole("button", { name: "확인" }));
    expect(onIntervene).toHaveBeenCalledWith("s1", "ACKNOWLEDGE");
    await userEvent.click(screen.getByRole("button", { name: "정지 해제" }));
    await userEvent.keyboard("{Escape}");
    expect(onIntervene).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "정지 해제" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "재개" }));
    expect(onIntervene).toHaveBeenLastCalledWith("s1", "RESUME");
  });
  it("풀린 알림과 결과 도착 알림에는 개입 버튼이 없고 결과 링크가 있다", () => {
    render(<AlertView {...props} alerts={[alert({ alert_id: "a2", kind: "RESULT_READY", session_id: "s2" }), alert({ resolved_at: "2026-11-10T08:05:00Z" })]} />);
    expect(screen.queryByRole("button", { name: "확인" })).toBeNull();
    expect(screen.getByRole("link", { name: "결과 보기" })).toBeVisible();
  });
  it("직원 역할이 아니면(의사) 개입 버튼이 없다", () => {
    render(<AlertView {...props} canIntervene={false} alerts={[alert({})]} />);
    expect(screen.queryByRole("button", { name: "정지 해제" })).toBeNull();
  });
  it("연결이 끊기면 다시 연결 버튼을 보인다", async () => {
    const onReconnect = vi.fn();
    render(<AlertView {...props} connection="closed" onReconnect={onReconnect} />);
    await userEvent.click(screen.getByRole("button", { name: "다시 연결" }));
    expect(onReconnect).toHaveBeenCalled();
  });
  it("푸시 지원 여부에 따라 안내가 다르다", () => {
    const { rerender } = render(<AlertView {...props} pushState="unsupported" />);
    expect(screen.getByText(/지원하지 않는다/)).toBeVisible();
    rerender(<AlertView {...props} pushState="on" />);
    expect(screen.getByText("푸시 알림을 받는 중")).toBeVisible();
  });
});

describe("ResultList / ResultDetail", () => {
  const summary: S["ResultSummary"] = { session_id: "s1", status: "ENDED_PARTIAL", questionnaire_id: "nh", subject_ref: "subj-1", started_at: "2026-11-10T08:00:00Z" };
  it("빈 목록과 부분 결과 상태", () => {
    const common = { statusFilter: "" as const, loading: false, errorMessage: undefined, hasMore: false, onStatusFilter: vi.fn(), onLoadMore: vi.fn(), renderDetailLink: (_id: string, label: string) => <a href="#x">{label}</a> };
    const { rerender } = render(<ResultList {...common} rows={[]} />);
    expect(screen.getByText("결과가 없다")).toBeVisible();
    rerender(<ResultList {...common} rows={[summary]} />);
    expect(screen.getByRole("cell", { name: "부분(중간에 끝냄)" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "아직" })).toBeVisible();
  });
  it("상태 거르기를 바꾸면 알린다", async () => {
    const onStatusFilter = vi.fn();
    render(<ResultList rows={[]} statusFilter="" loading={false} errorMessage={undefined} hasMore={false} onStatusFilter={onStatusFilter} onLoadMore={vi.fn()} renderDetailLink={() => null} />);
    await userEvent.selectOptions(screen.getByLabelText("상태"), "EXPIRED");
    expect(onStatusFilter).toHaveBeenCalledWith("EXPIRED");
  });
  const result: S["SessionResult"] = { ...summary, question_set_version_id: "v1", answers: [{ key: "Q1.answer", value: true, precision: "exact" }, { key: "Q2.none", value: null, precision: "unspecified" }], blanks: [{ item_id: "Q5", reason: "REJECTED" }] };
  it("답과 빈칸을 읽기 좋게 보이고 값 없음과 예를 구분한다", () => {
    render(<ResultDetail result={result} canAcknowledge acknowledging={false} errorMessage={undefined} onAcknowledge={vi.fn()} />);
    expect(screen.getByRole("cell", { name: "예" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "값 없음" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "답하지 않겠다고 함" })).toBeVisible();
    expect(screen.getByRole("note")).toHaveTextContent("부분 결과");
  });
  it("확인 표시는 의사만, 이미 확인했으면 버튼 대신 확인한 사람을 보인다", async () => {
    const onAcknowledge = vi.fn();
    const { rerender } = render(<ResultDetail result={result} canAcknowledge acknowledging={false} errorMessage={undefined} onAcknowledge={onAcknowledge} />);
    await userEvent.click(screen.getByRole("button", { name: "확인했음 표시" }));
    expect(onAcknowledge).toHaveBeenCalled();
    rerender(<ResultDetail result={result} canAcknowledge={false} acknowledging={false} errorMessage={undefined} onAcknowledge={onAcknowledge} />);
    expect(screen.queryByRole("button", { name: "확인했음 표시" })).toBeNull();
    rerender(<ResultDetail result={{ ...result, acknowledged_by: "doc-1", acknowledged_at: "2026-11-10T09:00:00Z" }} canAcknowledge acknowledging={false} errorMessage={undefined} onAcknowledge={onAcknowledge} />);
    expect(screen.getByRole("status")).toHaveTextContent("doc-1");
    expect(screen.queryByRole("button", { name: "확인했음 표시" })).toBeNull();
  });
  it("인쇄는 브라우저 인쇄를 부른다", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    render(<ResultDetail result={result} canAcknowledge={false} acknowledging={false} errorMessage={undefined} onAcknowledge={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "인쇄" }));
    expect(print).toHaveBeenCalled();
  });
});

describe("QuestionSetView", () => {
  const version: S["QuestionSetVersion"] = {
    question_set_version_id: "v1",
    questionnaire_id: "nh",
    version_number: 2,
    runtime_contract_version: 1,
    content: { title: "건강검진", bank: { items: [] }, flow: { start_item: "Q1", rules: [] } },
    content_hash: "c".repeat(64),
    uploaded_by: "author-1",
    created_at: "2026-11-10T09:00:00Z",
  };
  const props = { versions: [version], loading: false, listError: undefined, hasMore: false, uploading: false, uploadProblem: undefined, uploaded: undefined, activating: false, activated: undefined, activateError: undefined, onUpload: vi.fn(), onActivate: vi.fn(), onLoadMore: vi.fn() };
  it("파일을 읽어 올린다", async () => {
    const onUpload = vi.fn();
    render(<QuestionSetView {...props} onUpload={onUpload} />);
    const upload = { questionnaire_id: "nh", runtime_contract_version: 1, content: version.content };
    await userEvent.upload(screen.getByLabelText("문항 세트 파일(JSON)"), new File([JSON.stringify(upload)], "qs.json", { type: "application/json" }));
    expect(onUpload).toHaveBeenCalledWith(upload);
  });
  it("JSON 이 아닌 파일은 보내지 않고 오류를 보인다", async () => {
    const onUpload = vi.fn();
    render(<QuestionSetView {...props} onUpload={onUpload} />);
    await userEvent.upload(screen.getByLabelText("문항 세트 파일(JSON)"), new File(["not json"], "qs.json", { type: "application/json" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("JSON");
    expect(onUpload).not.toHaveBeenCalled();
  });
  it("활성화는 대화상자 확인 뒤에만 보내고 Esc 는 취소다", async () => {
    const onActivate = vi.fn();
    render(<QuestionSetView {...props} onActivate={onActivate} />);
    await userEvent.click(screen.getByRole("button", { name: "nh 버전 2 활성화" }));
    await userEvent.keyboard("{Escape}");
    expect(onActivate).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "nh 버전 2 활성화" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "활성화" }));
    expect(onActivate).toHaveBeenCalledWith("v1");
  });
  it("빈 목록", () => {
    render(<QuestionSetView {...props} versions={[]} />);
    expect(screen.getByText("올린 문항 세트가 없다")).toBeVisible();
  });
});

describe("FailureCaseDetail", () => {
  const c: S["FailureCase"] = { case_id: "c1", case_version: 3, kind: "EXTRACT_FAILED", review_status: "UNREVIEWED", questionnaire_id: "nh", item_id: "Q7_1", utterance: "가끔", model_output: { action: "NEXT", next_item: "Q2", values: [] }, created_at: "2026-11-10T09:00:00Z" };
  const props = { failureCase: c, trace: undefined, traceError: undefined, saving: false, problem: undefined, saved: false, onSubmit: vi.fn(), onReload: vi.fn() };
  it("검토 결과를 base_case_version 과 함께 게시한다", async () => {
    const onSubmit = vi.fn();
    render(<FailureCaseDetail {...props} onSubmit={onSubmit} />);
    await userEvent.selectOptions(screen.getByLabelText("검토 결과"), "CONFIRMED");
    await userEvent.type(screen.getByLabelText(/고쳐 쓴 입력/), "가끔 한 잔");
    await userEvent.click(screen.getByRole("button", { name: "검토 결과 게시" }));
    expect(onSubmit).toHaveBeenCalledWith({ base_case_version: 3, review_status: "CONFIRMED", expected: c.model_output, reviewed_input: "가끔 한 잔" });
  });
  it("기대 출력이 JSON 이 아니면 보내지 않는다", async () => {
    const onSubmit = vi.fn();
    render(<FailureCaseDetail {...props} onSubmit={onSubmit} />);
    const box = screen.getByLabelText("기대 출력(JSON)");
    await userEvent.clear(box);
    await userEvent.type(box, "nope");
    await userEvent.click(screen.getByRole("button", { name: "검토 결과 게시" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("JSON");
    expect(onSubmit).not.toHaveBeenCalled();
  });
  it("버전 충돌(409 CASE_VERSION_MISMATCH)이면 다시 불러오기를 권한다", async () => {
    const onReload = vi.fn();
    render(<FailureCaseDetail {...props} onReload={onReload} problem={{ type: "about:blank", title: "충돌", status: 409, reason: "CASE_VERSION_MISMATCH" }} />);
    await userEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));
    expect(onReload).toHaveBeenCalled();
  });
});

describe("ReleaseView", () => {
  const manifest = {
    base_model: "Qwen/Qwen3-4B",
    runtime_contract_version: 1,
    model_io_version: "model-io-v2" as const,
    model_runtime_version: "1.0.0",
    adapters: [],
    lineage: { dataset_version_id: "d1", base_model: "Qwen/Qwen3-4B", training_run_ids: [] },
    evaluation: { dataset_version_id: "d2", metrics: [{ name: "next_item_accuracy" as const, value: 0.97, unit: "ratio" as const, sample_count: 2000 }], created_at: "2026-11-10T09:00:00Z" },
    created_at: "2026-11-10T09:00:00Z",
  };
  const base = {
    status: { state: "READY" as const, package_digest: `sha256:${"a".repeat(64)}`, previous_package_digest: `sha256:${"9".repeat(64)}` },
    statusError: undefined,
    canActivate: true,
    canRollback: true,
    manifest,
    viewedDigest: `sha256:${"b".repeat(64)}`,
    manifestLoading: false,
    manifestProblem: undefined,
    actionPending: false,
    actionProblem: undefined,
    onViewPackage: vi.fn(),
    onActivate: vi.fn(),
    onRollback: vi.fn(),
  };
  it("평가 보고서의 지표를 표로 보인다", () => {
    render(<ReleaseView {...base} />);
    expect(screen.getByRole("row", { name: /next_item_accuracy.*전체.*0.97.*ratio.*2000/ })).toBeVisible();
  });
  it("활성화 승인은 사유를 적어야 보낸다", async () => {
    const onActivate = vi.fn();
    render(<ReleaseView {...base} onActivate={onActivate} />);
    await userEvent.click(screen.getByRole("button", { name: "이 패키지 활성화 승인" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "승인" }));
    expect(await screen.findByText("사유를 입력한다")).toBeVisible();
    expect(onActivate).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText("사유"), "평가 통과");
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "승인" }));
    expect(onActivate).toHaveBeenCalledWith(`sha256:${"b".repeat(64)}`, "평가 통과");
  });
  it("Esc 로 닫으면 승인하지 않고 사유 입력도 비운다", async () => {
    const onActivate = vi.fn();
    render(<ReleaseView {...base} onActivate={onActivate} />);
    await userEvent.click(screen.getByRole("button", { name: "이 패키지 활성화 승인" }));
    await userEvent.type(screen.getByLabelText("사유"), "초안");
    await userEvent.keyboard("{Escape}");
    expect(onActivate).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "이 패키지 활성화 승인" }));
    expect(screen.getByLabelText("사유")).toHaveValue("");
  });
  it("운영자(활성화 권한 없음)는 승인 버튼이 없고 롤백만 한다", async () => {
    const onRollback = vi.fn();
    render(<ReleaseView {...base} canActivate={false} onRollback={onRollback} />);
    expect(screen.queryByRole("button", { name: "이 패키지 활성화 승인" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "직전 패키지로 롤백" }));
    await userEvent.type(screen.getByLabelText("사유"), "문제 발생");
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "롤백" }));
    expect(onRollback).toHaveBeenCalledWith(`sha256:${"9".repeat(64)}`, "문제 발생");
  });
  it("직전 패키지가 없으면 롤백 버튼이 없다", () => {
    render(<ReleaseView {...base} status={{ state: "READY", package_digest: base.status.package_digest }} />);
    expect(screen.queryByRole("button", { name: "직전 패키지로 롤백" })).toBeNull();
  });
  it("적재 상태 문구와 서버 사유(ROLLBACK_TARGET_INVALID)를 보인다", () => {
    render(<ReleaseView {...base} status={{ state: "LOADING" }} actionProblem={{ type: "about:blank", title: "되돌아갈 수 없다", status: 409, reason: "ROLLBACK_TARGET_INVALID" }} />);
    expect(screen.getByRole("status")).toHaveTextContent("적재 중");
    expect(screen.getByRole("alert")).toHaveTextContent("ROLLBACK_TARGET_INVALID");
  });
  it("digest 를 비우고 보면 보내지 않는다", async () => {
    const onViewPackage = vi.fn();
    render(<ReleaseView {...base} manifest={undefined} viewedDigest={undefined} onViewPackage={onViewPackage} />);
    await userEvent.click(screen.getByRole("button", { name: "평가 보고서 보기" }));
    expect(await screen.findByText("digest 를 입력한다")).toBeVisible();
    expect(onViewPackage).not.toHaveBeenCalled();
  });
});

describe("Layout", () => {
  it("열린 알림 수는 알림 메뉴에만 붙고 0 이면 보이지 않는다", () => {
    const nav = [{ to: "/alerts", label: "알림" }, { to: "/results", label: "결과" }];
    const renderLink = (item: { to: string; label: string }) => <a href={item.to}>{item.label}</a>;
    const { rerender } = render(<Layout userName="김" nav={nav} openAlerts={2} signOutUrl="/oauth2/sign_out" renderLink={renderLink}>본문</Layout>);
    expect(screen.getByLabelText("열린 알림 2건")).toBeVisible();
    rerender(<Layout userName="김" nav={nav} openAlerts={0} signOutUrl="/oauth2/sign_out" renderLink={renderLink}>본문</Layout>);
    expect(screen.queryByLabelText(/열린 알림/)).toBeNull();
    expect(screen.getByRole("link", { name: "로그아웃" })).toHaveAttribute("href", "/oauth2/sign_out");
  });
});
