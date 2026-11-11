// 대화 화면(conversation_view): 질문·응답 문장을 크게 보이고, 환자의 발화를 받는다(음성 또는 글자). 서버 호출은 하지 않는다(ADR 0003).
import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";

import "./ConversationView.css";

/** 턴이 값을 만들지 못했거나(계약 failure_signal) 서버에 닿지 못했다. 둘 다 같은 발화를 다시 보낼 수 있다(D75(1)) */
export type ConversationFailure = "TURN_FAILED" | "UNREACHABLE";

export interface VoiceInput {
  /** unavailable: 기기 안 음성 인식을 쓸 수 없다(글자 입력만) */
  state: "checking" | "unavailable" | "ready" | "listening";
  /** 아직 끝나지 않은 인식 중인 글 */
  interim: string;
  onToggle: () => void;
}

export interface VoiceOutput {
  /** 기기 안 한국어 목소리가 있는가 */
  available: boolean;
  onReplay: () => void;
}

export interface ConversationViewProps {
  title?: string | undefined;
  /** 화면에 보일 질문·응답 문장(계약 ResponseSentence) */
  sentence: string;
  /** 문장을 스트림으로 받아 그리는 중이다. 조각마다 읽어 주지 않도록 끝날 때까지 보조 기술의 알림을 미룬다(WAI-ARIA aria-busy) */
  streaming?: boolean;
  /** 서비스의 고정 문장으로 직원 도움을 안내하는 중이다(계약 staff_help_notice) */
  staffHelpNotice: boolean;
  draft: string;
  onDraftChange: (text: string) => void;
  /** 발화 상한(계약 UtteranceText) */
  maxLength: number;
  onSend: () => void;
  /** 응답을 기다리는 중 */
  busy: boolean;
  /** 응답이 늦어 진행 표시를 보인다(계약 kiosk_progress_notice) */
  slow: boolean;
  failure: ConversationFailure | null;
  voiceInput: VoiceInput;
  voiceOutput: VoiceOutput;
  onEnd: () => void;
  onStaffCall: () => void;
  staffCallBusy: boolean;
}

export function ConversationView(props: ConversationViewProps) {
  const [confirmEnd, setConfirmEnd] = useState(false);
  const { draft, maxLength, busy } = props;
  const listening = props.voiceInput.state === "listening";
  const canSend = !busy && draft.trim().length > 0;

  return (
    <section className="conversation" aria-labelledby="sentence">
      {props.title !== undefined && <p className="questionnaire-title">{props.title}</p>}
      <p id="sentence" className="sentence" aria-live="polite" aria-busy={props.streaming === true}>
        {props.sentence}
      </p>
      {props.staffHelpNotice && (
        <p className="staff-help" role="note">
          직원의 도움이 필요하면 아래 ‘직원 부르기’ 를 눌러 주세요.
        </p>
      )}
      {props.voiceOutput.available && (
        <button type="button" className="secondary-button" onClick={props.voiceOutput.onReplay}>
          다시 듣기
        </button>
      )}

      <label htmlFor="utterance" className="label">
        답변
      </label>
      <textarea
        id="utterance"
        className="utterance"
        rows={3}
        maxLength={maxLength}
        value={draft}
        disabled={busy}
        placeholder={props.voiceInput.state === "unavailable" ? "여기에 답변을 적어 주세요" : "말씀하시거나 적어 주세요"}
        onChange={(event) => {
          props.onDraftChange(event.target.value);
        }}
      />
      <p className="counter" aria-live="off">
        {String(draft.length)} / {String(maxLength)}자
      </p>
      {listening && (
        <p className="listening" role="status">
          듣고 있습니다… {props.voiceInput.interim}
        </p>
      )}
      {props.slow && busy && (
        <p className="progress" role="status">
          처리하고 있습니다. 잠시만 기다려 주세요.
        </p>
      )}
      {props.failure !== null && (
        <p className="error" role="alert">
          {props.failure === "TURN_FAILED"
            ? "잘 이해하지 못했습니다. 한 번 더 말씀해 주세요."
            : "연결이 원활하지 않습니다. 잠시 후에 다시 보내 주세요."}
        </p>
      )}

      <div className="actions">
        {props.voiceInput.state !== "unavailable" && (
          <button
            type="button"
            className="big-button"
            disabled={busy || props.voiceInput.state === "checking"}
            aria-pressed={listening}
            onClick={props.voiceInput.onToggle}
          >
            {listening ? "말 끝내기" : "말하기"}
          </button>
        )}
        <button type="button" className="big-button primary" disabled={!canSend} onClick={props.onSend}>
          보내기
        </button>
      </div>
      <div className="actions">
        <button type="button" className="secondary-button" disabled={props.staffCallBusy} onClick={props.onStaffCall}>
          직원 부르기
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={() => {
            setConfirmEnd(true);
          }}
        >
          문진 끝내기
        </button>
      </div>

      <Dialog.Root open={confirmEnd} onOpenChange={setConfirmEnd}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="dialog">
            <Dialog.Title>문진을 끝낼까요?</Dialog.Title>
            <Dialog.Description>지금까지 답한 내용은 저장됩니다. 아직 답하지 않은 질문은 비어 있게 됩니다.</Dialog.Description>
            <div className="actions">
              <button
                type="button"
                className="big-button primary"
                onClick={() => {
                  setConfirmEnd(false);
                  props.onEnd();
                }}
              >
                끝내기
              </button>
              <Dialog.Close asChild>
                <button type="button" className="big-button">
                  계속하기
                </button>
              </Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
