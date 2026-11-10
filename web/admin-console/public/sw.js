// 웹 푸시 서비스 워커(RFC 8030 전달, RFC 8291 암호화, RFC 8292 VAPID). 브라우저가 푸시 본문을 풀어 push 이벤트로 준다.
// 본문은 계약 WebPushPayload(kind, alert_id, raised_at)다. 환자 정보는 담기지 않는다.
const TITLES = { RISK: "위험 알림", CALL_STAFF: "직원 호출", RESULT_READY: "결과 도착" };

self.addEventListener("push", (event) => {
  const payload = event.data ? event.data.json() : {};
  const title = TITLES[payload.kind] ?? "문진 알림";
  // tag: 같은 알림이 다시 오면 겹치지 않고 갱신한다
  event.waitUntil(self.registration.showNotification(title, { tag: payload.alert_id, data: { kind: payload.kind } }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      const open = windows.find((w) => "focus" in w);
      return open ? open.focus() : self.clients.openWindow("/alerts");
    }),
  );
});
