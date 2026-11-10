// 직원 알림 스트림(SSE, streamStaffAlerts)과 웹 푸시 구독(RFC 8030·8291·8292). 영역 밖 통신이라 link 에만 둔다.
import { useCallback, useEffect, useEffectEvent, useMemo, useState } from "react";

import type { components } from "../contract/survey-service";
import { ApiError, survey, unwrap } from "./http";
import { type StaffAlert, useAlertList } from "./survey";

// 왜 여기에 손으로 적었나: 생성 타입(src/contract)에 StaffAlertEvent·AlertEventName·AlertStreamHeartbeatSeconds 가 없다.
// 계약은 이들을 text/event-stream 의 x-event-data-schema 확장과 description 으로만 가리켜 openapi-typescript 가 버린다(docs/change-requests/admin-console-003.md).
// 값은 계약 components.yaml 의 StaffAlertEvent 와 같다(tests/contract/alerts.test.ts 가 계약 파일과 대조한다).
export type AlertEventName = "alert" | "resolved" | "heartbeat" | "resync";
export interface StaffAlertEvent {
  event: AlertEventName;
  sequence: components["schemas"]["EventSequence"];
  alert?: StaffAlert;
}
/** 계약 AlertStreamHeartbeatSeconds(const 15). */
export const HEARTBEAT_SECONDS = 15;
// 왜 3 배: heartbeat 를 세 번 연달아 놓치면 연결이 죽었다고 본다. EventSource 는 반쯤 끊긴 연결을 스스로 알아채지 못한다(계약 heartbeat 설명).
// 3 은 표준이 아니라 이 화면이 고른 값이고 측정하지 않았다(ADR 0004).
const STALE_AFTER_MS = HEARTBEAT_SECONDS * 3 * 1000;
export const STREAM_URL = "/v1/staff-alerts/stream";

export type Connection = "connecting" | "open" | "closed";

/** 이벤트를 알림 목록(alert_id 로 합친 맵)에 반영한다. alert 와 resolved 만 알림을 바꾼다. */
export function applyAlertEvent(current: ReadonlyMap<string, StaffAlert>, event: StaffAlertEvent): ReadonlyMap<string, StaffAlert> {
  if ((event.event !== "alert" && event.event !== "resolved") || event.alert === undefined) return current;
  const next = new Map(current);
  next.set(event.alert.alert_id, event.alert);
  return next;
}

const EVENT_NAMES: AlertEventName[] = ["alert", "resolved", "heartbeat", "resync"];

/** 스트림을 열고, 닫는 함수를 돌려준다. 끊기면 EventSource 가 Last-Event-ID 로 스스로 다시 잇는다. */
export function openAlertStream(handlers: { onEvent: (event: StaffAlertEvent) => void; onConnection: (state: Connection) => void }): () => void {
  let source: EventSource | undefined;
  let watchdog: ReturnType<typeof setTimeout> | undefined;
  let closed = false;

  const arm = () => {
    clearTimeout(watchdog);
    // 조용한 연결을 버리고 새로 연다(새 연결은 Last-Event-ID 가 없어 resync 로 목록을 다시 읽게 된다)
    watchdog = setTimeout(() => {
      source?.close();
      open();
    }, STALE_AFTER_MS);
  };

  const open = () => {
    if (closed) return;
    handlers.onConnection("connecting");
    const stream = new EventSource(STREAM_URL);
    source = stream;
    stream.onopen = () => {
      handlers.onConnection("open");
      arm();
    };
    stream.onerror = () => {
      // CONNECTING 이면 브라우저가 다시 잇는 중이다. CLOSED 이면 응답 코드 오류(401, 403 등)라 브라우저가 포기한 것이다.
      handlers.onConnection(stream.readyState === EventSource.CLOSED ? "closed" : "connecting");
    };
    for (const name of EVENT_NAMES) {
      stream.addEventListener(name, (message) => {
        arm();
        handlers.onEvent(JSON.parse((message as MessageEvent<string>).data) as StaffAlertEvent);
      });
    }
  };

  open();
  return () => {
    closed = true;
    clearTimeout(watchdog);
    source?.close();
  };
}

/**
 * 알림 목록(쪽 나눔)과 스트림을 합친다. 스트림 이벤트는 목록 위에 덮어쓰고, resync 나 새 연결에서 목록을 다시 읽는다.
 * enabled 가 거짓이면(직원도 의사도 아니면) 서버를 부르지 않는다.
 */
export function useStaffAlerts(enabled: boolean) {
  const list = useAlertList(enabled);
  const [overlay, setOverlay] = useState<ReadonlyMap<string, StaffAlert>>(new Map());
  const [connection, setConnection] = useState<Connection>("connecting");
  const [reconnectTick, setReconnectTick] = useState(0);
  // 왜 useEffectEvent: 스트림 효과는 목록이 바뀔 때마다 다시 열리면 안 된다. 최신 refetch 만 읽는다(React 19.2 공식 방식).
  const resync = useEffectEvent(() =>
    list.refetch().then(() => {
      setOverlay(new Map());
    }),
  );

  useEffect(() => {
    if (!enabled) return undefined;
    let first = true;
    return openAlertStream({
      onConnection: (state) => {
        setConnection(state);
        // 다시 이어진 연결: 끊긴 동안 놓친 것이 있을 수 있어 목록을 다시 읽는다(첫 연결은 목록 읽기가 따로 한다)
        if (state === "open") {
          if (!first) void resync();
          first = false;
        }
      },
      onEvent: (event) => {
        if (event.event === "resync") void resync();
        else setOverlay((current) => applyAlertEvent(current, event));
      },
    });
  }, [enabled, reconnectTick]);

  const alerts = useMemo(() => {
    const merged = new Map<string, StaffAlert>();
    for (const page of list.data?.pages ?? []) for (const alert of page.items) merged.set(alert.alert_id, alert);
    for (const [id, alert] of overlay) merged.set(id, alert);
    // 최근 것이 먼저(계약 listStaffAlerts 의 순서). raised_at 은 RFC 3339 라 같은 시간대면 글자순이 시간순이지만 Date 로 비교한다.
    return [...merged.values()].sort((a, b) => Date.parse(b.raised_at) - Date.parse(a.raised_at));
  }, [list.data, overlay]);

  const reconnect = useCallback(() => {
    // 닫힌 연결(인증 만료 등)을 다시 열려면 효과를 다시 돌린다
    setConnection("connecting");
    setReconnectTick((tick) => tick + 1);
  }, []);

  return {
    alerts,
    connection,
    reconnect,
    isLoading: list.isLoading,
    error: list.error,
    hasMore: list.hasNextPage,
    loadMore: () => void list.fetchNextPage(),
  };
}

// ---- 웹 푸시 ----

/** VAPID 공개키(base64url, RFC 8292)를 pushManager.subscribe 가 받는 바이트로 바꾼다. */
export function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export type PushSupport = "supported" | "unsupported";

export function pushSupport(): PushSupport {
  return "serviceWorker" in navigator && "PushManager" in globalThis && "Notification" in globalThis ? "supported" : "unsupported";
}

/**
 * 웹 푸시를 켠다: 알림 권한 → 서비스 워커 등록 → VAPID 공개키로 구독 → 서버에 구독 등록.
 * 푸시 내용의 암호화(RFC 8291)와 전달(RFC 8030)은 브라우저와 푸시 서비스가 한다. 이 코드는 구독만 만든다.
 */
export async function enablePush(): Promise<void> {
  if (pushSupport() === "unsupported") throw new Error("이 브라우저는 웹 푸시를 지원하지 않는다");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("알림 권한이 허용되지 않았다");
  const { vapid_public_key: key } = unwrap(await survey.GET("/v1/push-config"));
  const registration = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: base64UrlToBytes(key) });
  const json = subscription.toJSON();
  if (json.endpoint === undefined || json.keys?.["p256dh"] === undefined || json.keys["auth"] === undefined) {
    throw new ApiError(0, undefined, "브라우저가 만든 푸시 구독이 불완전하다");
  }
  unwrap(await survey.POST("/v1/push-subscriptions", { body: { endpoint: json.endpoint, keys: { p256dh: json.keys["p256dh"], auth: json.keys["auth"] } } }));
}

export async function isPushEnabled(): Promise<boolean> {
  if (pushSupport() === "unsupported") return false;
  const registration = await navigator.serviceWorker.getRegistration("/sw.js");
  return (await registration?.pushManager.getSubscription()) != null;
}
