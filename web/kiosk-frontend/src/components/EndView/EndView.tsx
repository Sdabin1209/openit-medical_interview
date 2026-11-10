// 끝 화면: 문진이 끝났다는 인사와 처음으로 가는 버튼. 서버 호출은 하지 않는다(ADR 0003).
import "./EndView.css";

/** COMPLETE: 모든 문항을 마침, PARTIAL: 중간에 끝냄. 만료(EXPIRED)는 끝 화면 없이 처음 화면으로 간다(ADR 0004) */
export type EndOutcome = "COMPLETE" | "PARTIAL";

export interface EndViewProps {
  outcome: EndOutcome;
  /** 서비스가 준 마지막 문장(있으면 보인다) */
  closingText?: string | undefined;
  onDone: () => void;
}

const TEXT: Record<EndOutcome, string> = {
  COMPLETE: "문진이 끝났습니다. 수고하셨습니다.",
  PARTIAL: "문진을 마쳤습니다. 지금까지 답한 내용은 저장되었습니다.",
};

export function EndView({ outcome, closingText, onDone }: EndViewProps) {
  return (
    <section className="end" aria-labelledby="end-title">
      <h1 id="end-title">{TEXT[outcome]}</h1>
      {closingText !== undefined && <p className="closing">{closingText}</p>}
      <p className="closing">직원에게 알려 주세요.</p>
      <button type="button" className="big-button primary" onClick={onDone}>
        처음으로
      </button>
    </section>
  );
}
