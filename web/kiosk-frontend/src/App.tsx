// 조립(app 층): link 의 데이터를 components 에 props 로 이어 준다. 화면 이동은 react-router.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router";

import { ConversationView, type ConversationFailure } from "./components/ConversationView";
import { EndView } from "./components/EndView";
import { IdleReset } from "./components/IdleReset";
import { PausedView } from "./components/PausedView";
import { useSpeechRecognition, useSpeechSynthesis } from "./components/speech";
import { StartView, type StartInput, type StartViewError } from "./components/StartView";
import {
  FALLBACK_RETRY_SECONDS,
  IDLE_WARNING_SECONDS,
  KIOSK_IDLE_RESET_SECONDS,
  KIOSK_PROGRESS_NOTICE_SECONDS,
  KIOSK_REQUEST_LIMIT_SECONDS,
  KIOSK_RETRY_BUDGET_SECONDS,
  SESSION_STATE_POLL_SECONDS,
  SPEECH_LANG,
  START_CODE_LENGTH,
  UTTERANCE_MAX_LENGTH,
} from "./limits";
import { createSurveyLink, SurveyError, type SessionState, type SurveyLink } from "./link/survey";
import { applyStatus, fromStarted, type ActiveSession, type EndOutcome } from "./session";

function startErrorOf(error: unknown): StartViewError {
  if (!(error instanceof SurveyError)) return "UNAVAILABLE";
  if (error.status === 429) return "RATE_LIMITED";
  if (error.reason === "START_CODE_INVALID") return "INVALID";
  if (error.reason === "START_CODE_EXPIRED") return "EXPIRED";
  if (error.reason === "START_CODE_USED") return "USED";
  return "UNAVAILABLE";
}

/** 응답을 기다린 지 `seconds` 가 지나면 참(진행 표시, 계약 kiosk_progress_notice) */
function useSlow(busy: boolean, seconds: number): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!busy) return;
    const timer = setTimeout(() => {
      setSlow(true);
    }, seconds * 1000);
    return () => {
      clearTimeout(timer);
      setSlow(false);
    };
  }, [busy, seconds]);
  return slow;
}

export interface AppProps {
  /** 시험에서 바꿔 끼운다. 기본은 같은 출처의 survey-service */
  link?: SurveyLink;
}

export function App({ link: injected }: AppProps) {
  const link = useMemo(
    () =>
      injected ??
      createSurveyLink({
        baseUrl: globalThis.location.origin,
        requestLimitSeconds: KIOSK_REQUEST_LIMIT_SECONDS,
        retryBudgetSeconds: KIOSK_RETRY_BUDGET_SECONDS,
        fallbackRetrySeconds: FALLBACK_RETRY_SECONDS,
      }),
    [injected],
  );
  const navigate = useNavigate();
  const [session, setSession] = useState<ActiveSession | null>(null);
  const [end, setEnd] = useState<{ outcome: EndOutcome; text?: string | undefined } | null>(null);
  const [startKey, setStartKey] = useState(0);
  const [startDirty, setStartDirty] = useState(false);
  const [draft, setDraft] = useState("");
  const [failure, setFailure] = useState<ConversationFailure | null>(null);
  const [callFailed, setCallFailed] = useState(false);

  // 처음 화면으로 돌아간다: 이 기기 화면의 모든 입력과 세션을 지운다(다음 사람에게 남기지 않는다)
  function reset() {
    setSession(null);
    setEnd(null);
    setDraft("");
    setFailure(null);
    setCallFailed(false);
    setStartDirty(false);
    setStartKey((key) => key + 1);
    void navigate("/");
  }

  function finish(outcome: EndOutcome, text?: string) {
    setSession(null);
    setEnd({ outcome, text });
    void navigate("/end");
  }

  function apply(current: ActiveSession, next: Parameters<typeof applyStatus>[1]) {
    const result = applyStatus(current, next);
    if (result.end !== null) finish(result.end, next.text);
    else setSession(result.session);
  }

  const questionnaires = useQuery({ queryKey: ["questionnaires", startKey], queryFn: ({ signal }) => link.listActiveQuestionnaires(signal) });

  const start = useMutation({ mutationFn: (input: StartInput) => link.startSession({ start_code: input.startCode, ...(input.questionnaireId === undefined ? {} : { questionnaire_id: input.questionnaireId }) }) });
  const turn = useMutation({
    mutationFn: ({ current, utterance }: { current: ActiveSession; utterance: string }) =>
      // 왜 턴마다 새 UUID: 같은 turn_id 의 재전송(연결 실패)은 link 가 한다. 실패 신호 뒤 다시 보내는 것은 새 턴이다
      link.submitTurn(current.sessionId, crypto.randomUUID(), utterance),
  });
  const staffCall = useMutation({ mutationFn: (id: string) => link.requestStaffCall(id) });
  const endMutation = useMutation({ mutationFn: (id: string) => link.endSession(id) });

  // 멈춘 동안 2초마다 상태를 읽어 직원이 풀었는지 안다(계약 SessionStatePollSeconds, D66(6))
  const pausedId = session?.paused != null ? session.sessionId : null;
  // 직원이 풀었거나 세션이 끝났으면 화면에 반영한다(응답을 받은 때 한 번)
  function onPolled(state: SessionState) {
    if (session === null || state.status === "PAUSED") return;
    apply(session, { status: state.status, pause_reason: state.pause_reason, text: state.resume_text });
  }
  useQuery({
    queryKey: ["state", pausedId],
    queryFn: async ({ signal }) => {
      const state = await link.getSessionState(pausedId ?? "", signal);
      onPolled(state);
      return state;
    },
    enabled: pausedId !== null,
    refetchInterval: SESSION_STATE_POLL_SECONDS * 1000,
    retry: false,
  });

  const recognition = useSpeechRecognition({
    lang: SPEECH_LANG,
    onFinalText: (text) => {
      setDraft((current) => `${current}${current === "" ? "" : " "}${text}`.slice(0, UTTERANCE_MAX_LENGTH));
    },
  });
  const synthesis = useSpeechSynthesis(SPEECH_LANG);
  const sentence = session?.sentence;
  const speak = synthesis.speak;
  useEffect(() => {
    if (sentence !== undefined) speak(sentence);
  }, [sentence, speak]);

  const waiting = turn.isPending || endMutation.isPending;
  const slow = useSlow(waiting, KIOSK_PROGRESS_NOTICE_SECONDS);

  async function onStart(input: StartInput): Promise<StartViewError | null> {
    try {
      const started = await start.mutateAsync(input);
      setSession(fromStarted(started));
      setDraft("");
      setFailure(null);
      void navigate("/talk");
      return null;
    } catch (error) {
      return startErrorOf(error);
    }
  }

  function onSend() {
    if (session === null) return;
    const utterance = draft.trim();
    setFailure(null);
    turn.mutate(
      { current: session, utterance },
      {
        onSuccess: (response) => {
          if (response.failure_signal !== undefined) {
            setFailure("TURN_FAILED");
            return;
          }
          setDraft("");
          apply(session, { status: response.status, pause_reason: response.pause_reason, text: response.response_text, staffHelpNotice: response.staff_help_notice });
        },
        onError: (error) => {
          if (error instanceof SurveyError && error.reason === "SESSION_NOT_ACTIVE") {
            // 끝났거나 멈춘 세션이다. 서버의 지금 상태를 읽어 맞춘다
            void link
              .getSessionState(session.sessionId)
              .then((state) => {
                apply(session, { status: state.status, pause_reason: state.pause_reason, text: state.resume_text });
              })
              .catch(() => {
                setFailure("UNREACHABLE");
              });
            return;
          }
          setFailure("UNREACHABLE");
        },
      },
    );
  }

  function onEnd() {
    if (session === null) return;
    endMutation.mutate(session.sessionId, {
      onSuccess: (ended) => {
        finish(ended.status === "ENDED_COMPLETE" ? "COMPLETE" : "PARTIAL");
      },
      onError: () => {
        setFailure("UNREACHABLE");
      },
    });
  }

  function onStaffCall() {
    if (session === null) return;
    setCallFailed(false);
    const current = session;
    staffCall.mutate(current.sessionId, {
      onSuccess: () => {
        // 호출하면 세션이 멈춘다(계약 requestStaffCall)
        setSession({ ...current, paused: "STAFF_CALL" });
      },
      onError: (error) => {
        if (error instanceof SurveyError && error.reason === "SESSION_NOT_ACTIVE") {
          void link.getSessionState(current.sessionId).then(
            (state) => {
              apply(current, { status: state.status, pause_reason: state.pause_reason, text: state.resume_text });
            },
            () => {
              setCallFailed(true);
            },
          );
          return;
        }
        setCallFailed(true);
      },
    });
  }

  const listening = recognition.state === "listening";
  const conversationIdle = session !== null && session.paused === null && !waiting && !listening;

  return (
    <main className="kiosk-shell">
      {/* 멈춘 세션은 만료하지 않는다(계약 SessionStatus EXPIRED) */}
      <Routes>
        <Route
          path="/"
          element={
            <>
              <StartView
                key={startKey}
                codeLength={START_CODE_LENGTH}
                questionnaires={questionnaires.data?.questionnaires ?? []}
                onStart={onStart}
                onDirtyChange={setStartDirty}
              />
              <IdleReset active={startDirty} seconds={KIOSK_IDLE_RESET_SECONDS} warnSeconds={IDLE_WARNING_SECONDS} onIdle={reset} />
            </>
          }
        />
        <Route
          path="/talk"
          element={
            session === null ? (
              // 왜 end 를 본다: 세션이 끝난 순간 이 경로가 먼저 다시 그려지므로 끝 화면으로 보낸다
              <Navigate to={end === null ? "/" : "/end"} replace />
            ) : session.paused !== null ? (
              <PausedView reason={session.paused} onCallAgain={onStaffCall} callBusy={staffCall.isPending} callFailed={callFailed} />
            ) : (
              <>
                <ConversationView
                  title={session.title}
                  sentence={session.sentence}
                  staffHelpNotice={session.staffHelpNotice}
                  draft={draft}
                  onDraftChange={setDraft}
                  maxLength={UTTERANCE_MAX_LENGTH}
                  onSend={onSend}
                  busy={waiting}
                  slow={slow}
                  failure={failure}
                  voiceInput={{ state: recognition.state, interim: recognition.interim, onToggle: listening ? recognition.stop : recognition.start }}
                  voiceOutput={{ available: synthesis.available, onReplay: () => { synthesis.speak(session.sentence); } }}
                  onEnd={onEnd}
                  onStaffCall={onStaffCall}
                  staffCallBusy={staffCall.isPending}
                />
                <IdleReset active={conversationIdle} seconds={KIOSK_IDLE_RESET_SECONDS} warnSeconds={IDLE_WARNING_SECONDS} onIdle={reset} />
              </>
            )
          }
        />
        <Route
          path="/end"
          element={
            end === null ? (
              <Navigate to="/" replace />
            ) : (
              <>
                <EndView outcome={end.outcome} closingText={end.text} onDone={reset} />
                <IdleReset active seconds={KIOSK_IDLE_RESET_SECONDS} warnSeconds={0} onIdle={reset} />
              </>
            )
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </main>
  );
}
