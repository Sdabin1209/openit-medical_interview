# platform-004: 포트의 최솟값과 경보 수신처 방식이 스키마 밖에서 거절된다

처리됨(848dbcb, platform a56d244): AlertReceiverUrl pattern 과 UnprivilegedListenPort(최솟값 1024)를 스키마에 두고 코드의 따로 검사를 지웠다(같은 9.0.0, 태그 전).

상태: 요청(2026-11-11, platform 작업). 대상 계약: `ListenPort`, `AlertReceiverUrl`(`PlatformEnv`).

## 무엇이 어긋나나
platform 의 설정 검증(`platform/src/openit_platform/settings.py`)에 스키마에 없는 거절 조건이 둘 남아 있다.

1. `OPENIT_LISTEN_PORT`·`OPENIT_SERVICE_PORT` 는 1024 이상이어야 한다. 입구(Envoy)와 영역 게이트웨이(Caddy)는 비 root 로 돌아 낮은 포트를 열지 못하기 때문이다(`ListenPort` 의 최솟값은 1).
2. `OPENIT_ALERT_RECEIVER_URL` 은 `https` 또는 `mailto` 여야 한다. 설명에는 그렇게 적혀 있으나 `AlertReceiverUrl` 은 `format: uri` 만 있고 `pattern` 이 없다.

## 제안
(1) `PlatformEnv` 의 두 포트 칸에 최솟값 1024 를 가진 스키마(예: `UnprivilegedListenPort`)를 쓴다. (2) `AlertReceiverUrl` 에 `pattern: "^(https://|mailto:)"` 를 더한다. 받아들이는 조건이 스키마에만 있게 된다. 답이 오기까지 platform 은 두 조건을 코드에 두고 이 문서를 가리킨다.
