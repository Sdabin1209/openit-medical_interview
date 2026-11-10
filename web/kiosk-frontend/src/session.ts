// 화면의 세션 상태(app 층). 서버가 준 상태를 화면이 보일 모양으로 옮긴다.
import type { SessionStarted, SessionState } from "./link/survey";

export type EndOutcome = "COMPLETE" | "PARTIAL" | "EXPIRED";

export interface ActiveSession {
  sessionId: string;
  title: string | undefined;
  sentence: string;
  staffHelpNotice: boolean;
  /** 멈춘 까닭. 멈추지 않았으면 null */
  paused: "RISK_SIGNAL" | "STAFF_CALL" | null;
}

export function fromStarted(started: SessionStarted): ActiveSession {
  return { sessionId: started.session_id, title: started.questionnaire_title, sentence: started.response_text, staffHelpNotice: false, paused: null };
}

export function outcomeOf(status: SessionState["status"]): EndOutcome | null {
  if (status === "ENDED_COMPLETE") return "COMPLETE";
  if (status === "ENDED_PARTIAL") return "PARTIAL";
  if (status === "EXPIRED") return "EXPIRED";
  return null;
}

/** 서버가 정한 상태 하나를 화면의 세션에 반영한다. 끝난 상태면 end 를 돌려준다. */
export function applyStatus(
  session: ActiveSession,
  next: { status: SessionState["status"]; pause_reason?: "RISK_SIGNAL" | "STAFF_CALL" | undefined; text?: string | undefined; staffHelpNotice?: boolean | undefined },
): { session: ActiveSession; end: EndOutcome | null } {
  const end = outcomeOf(next.status);
  if (end !== null) return { session, end };
  if (next.status === "PAUSED") {
    // 왜 STAFF_CALL 기본값: 멈춤인데 까닭이 없으면 직원이 와야 한다는 점은 같다(계약 pause_reason 은 선택 칸)
    return { session: { ...session, paused: next.pause_reason ?? "STAFF_CALL" }, end: null };
  }
  return {
    session: { ...session, paused: null, sentence: next.text ?? session.sentence, staffHelpNotice: next.staffHelpNotice ?? false },
    end: null,
  };
}
