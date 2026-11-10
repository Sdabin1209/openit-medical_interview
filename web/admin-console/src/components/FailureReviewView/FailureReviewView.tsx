import { useState } from "react";
import { useForm } from "react-hook-form";

import type { components } from "../../contract/survey-service";

type FailureCase = components["schemas"]["FailureCase"];
type CaseReview = components["schemas"]["CaseReview"];
type ReviewStatus = components["schemas"]["ReviewStatus"];
type DeidentifiedTrace = components["schemas"]["DeidentifiedTrace"];
type ActionExtraction = components["schemas"]["ActionExtraction"];
type ProblemDetails = components["schemas"]["ProblemDetails"];

export const REVIEW_LABEL: Record<ReviewStatus, string> = { UNREVIEWED: "검토 전", CONFIRMED: "실패로 확정", DISMISSED: "실패 아님" };
const KIND_LABEL: Record<FailureCase["kind"], string> = { EXTRACT_FAILED: "추출 실패", REASK_STREAK: "되묻기 연속" };

interface ListProps {
  cases: FailureCase[];
  statusFilter: ReviewStatus | "";
  loading: boolean;
  errorMessage: string | undefined;
  hasMore: boolean;
  onStatusFilter: (status: ReviewStatus | "") => void;
  onLoadMore: () => void;
  renderCaseLink: (caseId: string, label: string) => React.ReactNode;
}

/** 실패 사례 목록. 환자 발화 원문은 검토자에게만 나간다(계약). */
export function FailureCaseList(props: ListProps) {
  return (
    <section aria-labelledby="cases-title">
      <h1 id="cases-title">실패 사례 검토</h1>
      <label htmlFor="review-filter">검토 상태</label>
      <select id="review-filter" value={props.statusFilter} onChange={(event) => { props.onStatusFilter(event.target.value as ReviewStatus | ""); }}>
        <option value="">모두</option>
        {(Object.keys(REVIEW_LABEL) as ReviewStatus[]).map((s) => (
          <option key={s} value={s}>
            {REVIEW_LABEL[s]}
          </option>
        ))}
      </select>
      {props.errorMessage ? <p role="alert">{props.errorMessage}</p> : null}
      {props.loading ? <p>불러오는 중</p> : null}
      {!props.loading && props.cases.length === 0 ? <p>사례가 없다</p> : null}
      <ul>
        {props.cases.map((c) => (
          <li key={c.case_id}>
            {props.renderCaseLink(c.case_id, `${c.questionnaire_id} ${c.item_id} ${KIND_LABEL[c.kind]}`)} <span>{REVIEW_LABEL[c.review_status]}</span>
          </li>
        ))}
      </ul>
      {props.hasMore ? (
        <button type="button" onClick={props.onLoadMore}>
          더 보기
        </button>
      ) : null}
    </section>
  );
}

interface FormValues {
  reviewStatus: ReviewStatus;
  reviewedInput: string;
  expectedJson: string;
}

interface DetailProps {
  failureCase: FailureCase;
  trace: DeidentifiedTrace | undefined;
  traceError: string | undefined;
  saving: boolean;
  problem: ProblemDetails | undefined;
  saved: boolean;
  onSubmit: (review: CaseReview) => void;
  onReload: () => void;
}

/** 사례 하나: 발화, 모델 출력, 비식별 턴 기록, 검토 결과(상태, 기대 출력, 고쳐 쓴 입력) 게시. */
export function FailureCaseDetail({ failureCase: c, trace, traceError, saving, problem, saved, onSubmit, onReload }: DetailProps) {
  const [jsonError, setJsonError] = useState<string>();
  const { register, handleSubmit } = useForm<FormValues>({
    defaultValues: {
      reviewStatus: c.review_status,
      reviewedInput: c.reviewed_input ?? "",
      // 기대 출력의 시작값: 이미 검토한 기대 출력, 없으면 모델 출력
      expectedJson: JSON.stringify(c.expected ?? c.model_output ?? {}, null, 2),
    },
  });

  function submit(values: FormValues) {
    setJsonError(undefined);
    let expected: ActionExtraction | undefined;
    try {
      expected = JSON.parse(values.expectedJson) as ActionExtraction; // 구조 검사는 서버가 한다
    } catch {
      setJsonError("기대 출력이 JSON 이 아니다");
      return;
    }
    onSubmit({
      base_case_version: c.case_version,
      review_status: values.reviewStatus,
      expected,
      ...(values.reviewedInput === "" ? {} : { reviewed_input: values.reviewedInput }),
    });
  }

  const conflict = problem?.reason === "CASE_VERSION_MISMATCH";
  return (
    <article aria-labelledby="case-title">
      <h1 id="case-title">
        사례 {c.questionnaire_id} {c.item_id}
      </h1>
      <p>
        {KIND_LABEL[c.kind]} · {REVIEW_LABEL[c.review_status]} · 버전 {c.case_version}
      </p>
      <h2>환자 발화(원문)</h2>
      <blockquote>{c.utterance ?? "(없음)"}</blockquote>
      <h2>모델 출력</h2>
      <pre>{JSON.stringify(c.model_output ?? null, null, 2)}</pre>
      <h2>비식별 턴 기록</h2>
      {traceError ? <p role="alert">{traceError}</p> : null}
      {trace ? (
        <dl>
          <dt>발화</dt>
          <dd>{trace.utterance ?? "(없음)"}</dd>
          <dt>응답 문장</dt>
          <dd>{trace.response_text ?? "(없음)"}</dd>
          <dt>실패 신호</dt>
          <dd>{trace.failure_signal ?? "(없음)"}</dd>
        </dl>
      ) : null}
      <h2>검토</h2>
      <form onSubmit={(event) => void handleSubmit(submit)(event)} noValidate>
        <label htmlFor="review-status">검토 결과</label>
        <select id="review-status" {...register("reviewStatus")}>
          {(Object.keys(REVIEW_LABEL) as ReviewStatus[]).map((s) => (
            <option key={s} value={s}>
              {REVIEW_LABEL[s]}
            </option>
          ))}
        </select>
        <label htmlFor="reviewed-input">고쳐 쓴 입력(개인정보를 뺀 문장)</label>
        <textarea id="reviewed-input" rows={3} {...register("reviewedInput")} />
        <label htmlFor="expected-json">기대 출력(JSON)</label>
        <textarea id="expected-json" rows={12} spellCheck={false} {...register("expectedJson")} />
        {jsonError ? <p role="alert">{jsonError}</p> : null}
        <button type="submit" disabled={saving}>
          검토 결과 게시
        </button>
      </form>
      {saved ? <p role="status">검토 결과를 게시했다</p> : null}
      {problem ? (
        <div role="alert">
          <p>{conflict ? "다른 검토자가 먼저 고쳤다. 다시 불러온 뒤 검토한다." : problem.title}</p>
          {problem.detail ? <p>{problem.detail}</p> : null}
          {problem.errors?.map((e) => (
            <p key={e.pointer}>
              {e.pointer}: {e.detail}
            </p>
          ))}
          {conflict ? (
            <button type="button" onClick={onReload}>
              다시 불러오기
            </button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
