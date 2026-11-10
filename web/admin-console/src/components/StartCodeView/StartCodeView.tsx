import { useForm } from "react-hook-form";

import type { components } from "../../contract/survey-service";

type StartCode = components["schemas"]["StartCode"];
type Questionnaire = components["schemas"]["QuestionnaireSummary"];
type ProblemDetails = components["schemas"]["ProblemDetails"];

export interface IssueValues {
  subjectRef: string;
  /** 빈 글이면 문진표를 묶지 않는다 */
  questionnaireId: string;
}

interface Props {
  questionnaires: Questionnaire[];
  issued: StartCode | undefined;
  pending: boolean;
  problem: ProblemDetails | undefined;
  onIssue: (values: IssueValues) => void;
}

/** 시작 코드를 6자리 숫자로 크게 보인다(QR 없음). 직원이 말로 불러 주거나 적어 주거나 출력한다. */
export function StartCodeView({ questionnaires, issued, pending, problem, onIssue }: Props) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<IssueValues>({ defaultValues: { subjectRef: "", questionnaireId: "" } });
  return (
    <section aria-labelledby="start-code-title">
      <h1 id="start-code-title" className="no-print">시작 코드 발급</h1>
      <form className="no-print" onSubmit={(event) => void handleSubmit(onIssue)(event)} noValidate>
        <label htmlFor="subject-ref">대상자 참조값</label>
        {/* 형식 조건(길이·글자)은 계약이 정하고 서버가 검사한다. 어긋나면 아래에 서버 사유를 보인다 */}
        <input id="subject-ref" autoComplete="off" aria-invalid={errors.subjectRef ? "true" : "false"} {...register("subjectRef", { required: "대상자 참조값을 입력한다" })} />
        {errors.subjectRef ? <p role="alert">{errors.subjectRef.message}</p> : null}
        <label htmlFor="questionnaire">문진표</label>
        <select id="questionnaire" {...register("questionnaireId")}>
          <option value="">정하지 않음(기기 설정을 따름)</option>
          {questionnaires.map((q) => (
            <option key={q.questionnaire_id} value={q.questionnaire_id}>
              {q.title}
            </option>
          ))}
        </select>
        <button type="submit" disabled={pending}>
          {pending ? "발급 중" : "코드 발급"}
        </button>
      </form>
      {problem ? (
        <div role="alert" className="no-print">
          <p>{problem.title}</p>
          {problem.detail ? <p>{problem.detail}</p> : null}
          {problem.errors?.map((e) => (
            <p key={e.pointer}>
              {e.pointer}: {e.detail}
            </p>
          ))}
        </div>
      ) : null}
      {issued ? (
        <div aria-live="polite" className="issued-code">
          <p>시작 코드</p>
          {/* 숫자 여섯 칸. 스크린 리더에는 한 숫자씩 읽히게 글자 사이를 띄운 이름을 준다 */}
          <p className="code-digits" role="img" aria-label={`시작 코드 ${issued.code.split("").join(" ")}`}>
            {issued.code.split("").map((digit, index) => (
              <span key={index}>{digit}</span>
            ))}
          </p>
          <p>
            <time dateTime={issued.expires_at}>{new Date(issued.expires_at).toLocaleString("ko-KR")}</time> 까지 한 번만 쓸 수 있다
          </p>
          <button type="button" className="no-print" onClick={() => { window.print(); }}>
            출력
          </button>
        </div>
      ) : null}
    </section>
  );
}
