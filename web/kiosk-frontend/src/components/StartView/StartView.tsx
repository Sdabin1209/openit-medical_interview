// 시작 화면(start_view): 숫자 키패드로 6자리 시작 코드 입력(QR 없음), 문진표가 둘 이상이면 선택.
// 입력은 props 로 받고 서버 호출은 하지 않는다(ADR 0003). 시작 결과는 onStart 가 돌려준 오류로 받는다.
import { useState } from "react";

import type { components } from "../../contract/survey-service";
import "./StartView.css";

type Questionnaire = components["schemas"]["QuestionnaireSummary"];

/** 시작에 실패한 까닭. 계약 startSession 의 오류(422 START_CODE_INVALID, 409 START_CODE_EXPIRED·START_CODE_USED, 429)와 연결 실패다 */
export type StartViewError = "INVALID" | "EXPIRED" | "USED" | "RATE_LIMITED" | "UNAVAILABLE";

export interface StartInput {
  startCode: string;
  questionnaireId?: string;
}

export interface StartViewProps {
  /** 시작 코드의 자릿수(계약 StartCodeValue) */
  codeLength: number;
  /** 활성 문진표. 둘 이상이면 코드 입력 뒤에 고르게 한다 */
  questionnaires: readonly Questionnaire[];
  /** 시작을 요청하고 실패하면 그 까닭을, 성공하면 null 을 돌려준다 */
  onStart: (input: StartInput) => Promise<StartViewError | null>;
  /** 입력 중인 내용이 있는지 바뀔 때 알린다(유휴 초기화의 경고를 입력 중일 때만 보이려고) */
  onDirtyChange?: (dirty: boolean) => void;
}

const MESSAGES: Record<StartViewError, string> = {
  INVALID: "코드가 맞지 않습니다. 다시 입력해 주세요.",
  EXPIRED: "코드의 사용 시간이 지났습니다. 직원에게 새 코드를 받아 주세요.",
  USED: "이미 사용한 코드입니다. 직원에게 새 코드를 받아 주세요.",
  RATE_LIMITED: "잠시 후에 다시 입력해 주세요.",
  UNAVAILABLE: "지금은 연결할 수 없습니다. 잠시 후에 다시 눌러 주세요.",
};

// 왜 코드를 지운다: 틀리거나 못 쓰는 코드를 다시 입력하게 한다(브리프). 연결 실패는 같은 코드로 다시 누르면 되므로 지우지 않는다
const CLEARS_CODE: ReadonlySet<StartViewError> = new Set(["INVALID", "EXPIRED", "USED", "RATE_LIMITED"]);

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"] as const;

export function StartView({ codeLength, questionnaires, onStart, onDirtyChange }: StartViewProps) {
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"code" | "choose">("code");
  const [error, setError] = useState<StartViewError | null>(null);
  const [busy, setBusy] = useState(false);

  function update(next: string, nextStep: "code" | "choose" = step) {
    setCode(next);
    setStep(nextStep);
    onDirtyChange?.(next.length > 0);
  }

  function press(digit: string) {
    if (busy || code.length >= codeLength) return;
    setError(null);
    update(code + digit);
  }

  async function start(questionnaireId?: string) {
    setBusy(true);
    setError(null);
    const failure = await onStart(questionnaireId === undefined ? { startCode: code } : { startCode: code, questionnaireId });
    setBusy(false);
    if (failure === null) return;
    setError(failure);
    if (CLEARS_CODE.has(failure)) update("", "code");
  }

  function submit() {
    if (code.length !== codeLength || busy) return;
    if (questionnaires.length >= 2) {
      setStep("choose");
      return;
    }
    void start();
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (step !== "code") return;
    if (/^[0-9]$/.test(event.key)) press(event.key);
    else if (event.key === "Backspace") update(code.slice(0, -1));
    // 왜 버튼이 아닐 때만 Enter: 키패드 버튼에 초점이 있으면 Enter 가 그 버튼을 누르는 것이라 시작과 겹친다
    else if (event.key === "Enter" && !(event.target instanceof HTMLButtonElement)) submit();
  }

  if (step === "choose") {
    return (
      <section className="start-view" aria-labelledby="choose-title">
        <h1 id="choose-title">어떤 문진표를 작성하시겠어요?</h1>
        <ul className="choices">
          {questionnaires.map((q) => (
            <li key={q.questionnaire_id}>
              <button
                type="button"
                className="big-button"
                disabled={busy}
                onClick={() => {
                  void start(q.questionnaire_id);
                }}
              >
                {q.title}
              </button>
            </li>
          ))}
        </ul>
        {error !== null && (
          <p role="alert" className="error">
            {MESSAGES[error]}
          </p>
        )}
        <button
          type="button"
          className="secondary-button"
          disabled={busy}
          onClick={() => {
            update(code, "code");
          }}
        >
          코드 다시 입력
        </button>
      </section>
    );
  }

  return (
    <section className="start-view" aria-labelledby="start-title" tabIndex={-1} onKeyDown={onKeyDown}>
      <h1 id="start-title">시작 코드를 입력해 주세요</h1>
      <p className="hint">직원에게 받은 숫자 {String(codeLength)}자리입니다.</p>
      <div className="code-display" role="group" aria-label={`시작 코드 ${String(codeLength)}자리, 지금 ${String(code.length)}자리 입력함`}>
        {Array.from({ length: codeLength }, (_, index) => (
          <span key={index} className="code-slot" data-filled={index < code.length}>
            {code[index] ?? ""}
          </span>
        ))}
      </div>
      {error !== null && (
        <p role="alert" className="error">
          {MESSAGES[error]}
        </p>
      )}
      <div className="keypad">
        {KEYS.map((key) => (
          <button key={key} type="button" className="key" disabled={busy} onClick={() => { press(key); }}>
            {key}
          </button>
        ))}
        <button type="button" className="key key-aux" disabled={busy || code.length === 0} onClick={() => { update(""); }}>
          모두 지움
        </button>
        <button type="button" className="key" disabled={busy} onClick={() => { press("0"); }}>
          0
        </button>
        <button type="button" className="key key-aux" disabled={busy || code.length === 0} onClick={() => { update(code.slice(0, -1)); }}>
          지움
        </button>
      </div>
      <button type="button" className="big-button primary" disabled={busy || code.length !== codeLength} onClick={submit}>
        {busy ? "확인하고 있습니다…" : "시작하기"}
      </button>
    </section>
  );
}
