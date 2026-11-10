import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";

import type { components } from "../../contract/survey-service";

type StaffAlert = components["schemas"]["StaffAlert"];
type AlertKind = components["schemas"]["AlertKind"];
type InterventionAction = components["schemas"]["InterventionAction"];

const KIND_LABEL: Record<AlertKind, string> = { RISK: "위험", CALL_STAFF: "직원 호출", RESULT_READY: "결과 도착" };

interface Props {
  alerts: StaffAlert[];
  connection: "connecting" | "open" | "closed";
  loading: boolean;
  errorMessage: string | undefined;
  hasMore: boolean;
  /** 개입(확인·재개)을 할 수 있는가(직원 역할) */
  canIntervene: boolean;
  pushState: "unsupported" | "off" | "on";
  pushMessage: string | undefined;
  interventionError: string | undefined;
  onIntervene: (sessionId: string, action: InterventionAction) => void;
  onLoadMore: () => void;
  onReconnect: () => void;
  onEnablePush: () => void;
  /** 결과 도착 알림에서 결과로 가는 링크를 그리는 쪽(라우터)이 넘긴다 */
  renderResultLink: (sessionId: string) => React.ReactNode;
}

const CONNECTION_LABEL = { connecting: "연결 중", open: "실시간 연결됨", closed: "연결 끊김" } as const;

/** 직원 알림 목록과 개입(확인, 위험 정지 해제). 정지 해제는 되돌릴 수 없어 확인 대화상자를 거친다. */
export function AlertView(props: Props) {
  const [resuming, setResuming] = useState<StaffAlert | null>(null);
  return (
    <section aria-labelledby="alerts-title">
      <h1 id="alerts-title">직원 알림</h1>
      <p role="status">{CONNECTION_LABEL[props.connection]}</p>
      {props.connection === "closed" ? (
        <button type="button" onClick={props.onReconnect}>
          다시 연결
        </button>
      ) : null}
      {props.pushState === "off" ? (
        <button type="button" onClick={props.onEnablePush}>
          이 브라우저로 푸시 알림 받기
        </button>
      ) : null}
      {props.pushState === "on" ? <p>푸시 알림을 받는 중</p> : null}
      {props.pushState === "unsupported" ? <p>이 브라우저는 웹 푸시를 지원하지 않는다</p> : null}
      {props.pushMessage ? <p role="alert">{props.pushMessage}</p> : null}
      {props.errorMessage ? <p role="alert">{props.errorMessage}</p> : null}
      {props.interventionError ? <p role="alert">{props.interventionError}</p> : null}
      {props.loading ? <p>불러오는 중</p> : null}
      {!props.loading && props.alerts.length === 0 ? <p>알림이 없다</p> : null}
      <ul className="alerts">
        {props.alerts.map((alert) => {
          const open = alert.resolved_at === undefined;
          return (
            <li key={alert.alert_id} data-kind={alert.kind} data-open={open}>
              <strong>{KIND_LABEL[alert.kind]}</strong>
              {alert.device_id ? <span> 기기 {alert.device_id}</span> : null}
              {alert.questionnaire_title ? <span> {alert.questionnaire_title}</span> : null}
              <time dateTime={alert.raised_at}> {new Date(alert.raised_at).toLocaleTimeString("ko-KR")}</time>
              <span>{open ? " 열림" : " 풀림"}</span>
              {alert.kind === "RESULT_READY" ? props.renderResultLink(alert.session_id) : null}
              {props.canIntervene && open && alert.kind !== "RESULT_READY" ? (
                <>
                  <button type="button" onClick={() => { props.onIntervene(alert.session_id, "ACKNOWLEDGE"); }}>
                    확인
                  </button>
                  <button type="button" onClick={() => { setResuming(alert); }}>
                    정지 해제
                  </button>
                </>
              ) : null}
            </li>
          );
        })}
      </ul>
      {props.hasMore ? (
        <button type="button" onClick={props.onLoadMore}>
          더 보기
        </button>
      ) : null}
      <Dialog.Root open={resuming !== null} onOpenChange={(next) => { if (!next) setResuming(null); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="dialog">
            <Dialog.Title>세션 재개</Dialog.Title>
            <Dialog.Description>
              {resuming ? `${KIND_LABEL[resuming.kind]} 알림으로 멈춘 세션을 재개한다. 환자 곁에서 확인한 뒤에만 재개한다.` : ""}
            </Dialog.Description>
            <button
              type="button"
              onClick={() => {
                if (resuming) props.onIntervene(resuming.session_id, "RESUME");
                setResuming(null);
              }}
            >
              재개
            </button>
            <Dialog.Close asChild>
              <button type="button">취소</button>
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
