// 멈춤 화면: 직원 호출이나 위험 신호로 세션이 멈췄다. 직원이 풀 때까지 기다리며 직원을 다시 부를 수 있다. 서버 호출은 하지 않는다(ADR 0003).
import type { components } from "../../contract/survey-service";
import "./PausedView.css";

export interface PausedViewProps {
  /** 멈춘 까닭(계약 PauseReason) */
  reason: components["schemas"]["PauseReason"];
  onCallAgain: () => void;
  callBusy: boolean;
  /** 직원 다시 부르기가 서버에 닿지 않았다 */
  callFailed: boolean;
}

const TEXT: Record<PausedViewProps["reason"], string> = {
  STAFF_CALL: "직원을 불렀습니다. 잠시만 기다려 주세요.",
  RISK_SIGNAL: "잠시 멈추었습니다. 직원이 곧 도와드립니다. 자리에서 기다려 주세요.",
};

export function PausedView({ reason, onCallAgain, callBusy, callFailed }: PausedViewProps) {
  return (
    <section className="paused" aria-labelledby="paused-title">
      <h1 id="paused-title">잠시 기다려 주세요</h1>
      <p className="paused-text" role="status">
        {TEXT[reason]}
      </p>
      {callFailed && (
        <p className="error" role="alert">
          직원 호출이 전달되지 않았습니다. 다시 눌러 주세요.
        </p>
      )}
      <button type="button" className="big-button" disabled={callBusy} onClick={onCallAgain}>
        직원 다시 부르기
      </button>
    </section>
  );
}
