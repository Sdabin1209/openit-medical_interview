import type { components } from "../../contract/survey-service";

type SessionResult = components["schemas"]["SessionResult"];
type SessionStatus = components["schemas"]["SessionStatus"];
type BlankReason = components["schemas"]["BlankReason"];
type ValuePrecision = components["schemas"]["ValuePrecision"];
type SlotAnswer = components["schemas"]["SlotAnswer"];

const STATUS_LABEL: Record<SessionStatus, string> = {
  ACTIVE: "진행 중",
  PAUSED: "멈춤",
  ENDED_COMPLETE: "완료",
  ENDED_PARTIAL: "부분(중간에 끝냄)",
  EXPIRED: "만료",
};
const BLANK_LABEL: Record<BlankReason, string> = {
  UNKNOWN: "모름",
  REJECTED: "답하지 않겠다고 함",
  UNCLEAR: "알아듣지 못함",
  REASK_LIMIT: "되묻기 한도",
  UNASKED: "묻지 않음",
};
const PRECISION_LABEL: Record<ValuePrecision, string> = { exact: "정확", approximate: "대략", unspecified: "정하지 않음" };

function formatAnswer(value: SlotAnswer): string {
  if (value === null) return "값 없음";
  if (typeof value === "boolean") return value ? "예" : "아니오";
  return String(value);
}

interface Props {
  result: SessionResult;
  canAcknowledge: boolean;
  acknowledging: boolean;
  errorMessage: string | undefined;
  onAcknowledge: () => void;
}

/** 결과 상세와 인쇄, 확인 표시. 인쇄는 브라우저 인쇄(print.css 가 메뉴를 숨긴다). */
export function ResultDetail({ result, canAcknowledge, acknowledging, errorMessage, onAcknowledge }: Props) {
  const acknowledged = result.acknowledged_at !== undefined;
  return (
    <article aria-labelledby="result-title">
      <h1 id="result-title">문진 결과 {result.subject_ref}</h1>
      <dl>
        <dt>문진표</dt>
        <dd>{result.questionnaire_title ?? result.questionnaire_id}</dd>
        <dt>상태</dt>
        <dd>{STATUS_LABEL[result.status]}</dd>
        <dt>시작</dt>
        <dd>{new Date(result.started_at).toLocaleString("ko-KR")}</dd>
        {result.ended_at ? (
          <>
            <dt>끝</dt>
            <dd>{new Date(result.ended_at).toLocaleString("ko-KR")}</dd>
          </>
        ) : null}
        {result.device_id ? (
          <>
            <dt>기기</dt>
            <dd>{result.device_id}</dd>
          </>
        ) : null}
      </dl>
      {result.status !== "ENDED_COMPLETE" ? <p role="note">끝까지 마치지 않은 문진의 부분 결과다.</p> : null}
      <h2>답</h2>
      {result.answers.length === 0 ? (
        <p>저장된 답이 없다</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">칸</th>
              <th scope="col">값</th>
              <th scope="col">정밀도</th>
            </tr>
          </thead>
          <tbody>
            {result.answers.map((answer) => (
              <tr key={answer.key}>
                <th scope="row">{answer.key}</th>
                <td>{formatAnswer(answer.value)}</td>
                <td>{PRECISION_LABEL[answer.precision]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h2>빈칸</h2>
      {result.blanks.length === 0 ? (
        <p>빈칸이 없다</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">문항</th>
              <th scope="col">칸</th>
              <th scope="col">까닭</th>
            </tr>
          </thead>
          <tbody>
            {result.blanks.map((blank, index) => (
              <tr key={`${blank.item_id}-${blank.key ?? ""}-${String(index)}`}>
                <th scope="row">{blank.item_id}</th>
                <td>{blank.key ?? ""}</td>
                <td>{BLANK_LABEL[blank.reason]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {acknowledged ? (
        <p role="status">
          {result.acknowledged_by} 이(가) {new Date(result.acknowledged_at ?? "").toLocaleString("ko-KR")} 에 확인했다
        </p>
      ) : null}
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      <div className="no-print">
        {canAcknowledge && !acknowledged ? (
          <button type="button" disabled={acknowledging} onClick={onAcknowledge}>
            확인했음 표시
          </button>
        ) : null}
        <button type="button" onClick={() => { window.print(); }}>
          인쇄
        </button>
      </div>
    </article>
  );
}
