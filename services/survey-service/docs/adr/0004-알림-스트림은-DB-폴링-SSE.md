# 0004. 알림 스트림은 Server-Sent Events 이고 새 이벤트는 DB 를 1초마다 읽어 찾는다

## 상태
승인(2026-11-10, 영역 작업자 판단)

## 맥락
직원 화면은 알림을 스트림으로 받는다(계약 streamStaffAlerts: text/event-stream, 이벤트 alert·resolved·heartbeat·resync, Last-Event-ID 로 이어 받기).

## 결정
알림과 이벤트를 같은 트랜잭션에서 `alert_event` 표에 순번(seq)과 함께 쓴다. 스트림은 1초마다 마지막 순번 뒤의 이벤트를 읽어 보내고 15초(계약 AlertStreamHeartbeatSeconds) 동안 없으면 heartbeat 를 보낸다. 순번이 서버가 아는 최신보다 크면 resync 를 먼저 보낸다. 새 연결은 지금 순번부터 받는다(지난 알림은 목록으로 읽는다).

## 왜
SSE 형식은 WHATWG HTML 9.2 다. 순번을 이벤트 id 로 쓰면 브라우저가 Last-Event-ID 로 자동으로 이어 받는다. 이벤트를 DB 에 남기므로 서버가 여러 개여도 같은 순서를 본다. 1초는 직원 알림에 초 단위면 충분하다는 선택이고 측정하지 않았다.

## 검토한 대안과 버리는 이유
- PostgreSQL LISTEN/NOTIFY: 지연이 짧지만 SQLite(시험)에서 같은 코드를 못 돌리고 연결을 오래 점유한다. 폴링으로 시작하고 측정에서 부담이 보이면 바꾼다.
- 메모리 큐: 서버가 둘이면 알림을 못 본다.
- WebSocket: 계약이 SSE 다.

## 결과
얻는 것: 단순하고 시험할 수 있다. 감수하는 것: 스트림마다 초당 1회 조회가 생긴다(연결 수가 많으면 부담). 계약 적합성 시험(Schemathesis)은 끝나지 않는 응답을 읽을 수 없어 이 작업을 빼고 tests/api/test_alerts_push_risk.py 가 스트림 생성기를 직접 본다.

## 되돌리는 조건
스트림 연결이 수십 개를 넘거나 지연이 문제로 측정되면 LISTEN/NOTIFY 로 바꾸는 새 ADR 을 쓴다.
