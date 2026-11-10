# kiosk-frontend-002: 유휴 초기화 때 세션의 마무리 주체가 계약에 없다

처리됨(계약 9.0.0(5f3c616, 848dbcb), 영역 e47d70e, 화면 877a72e): 유휴 만료의 주체는 서버(마지막 활동 뒤 60초).

## 상태
요청(2026-11-10, kiosk-frontend 작업자). 대상: 헤드.

## 무엇이 어긋나나(읽어서 확인한 것)
- `SessionStatus.EXPIRED` 는 "유휴 초기화 60초로 끝남"이고 `KioskIdleResetSeconds` 는 "키오스크가 환자의 입력 없이 기다리다 세션을 초기화하는 시간"이다. 키오스크가 초기화하는데 EXPIRED 를 서버에 알리는 작업이 없다. `endSession` 은 ENDED_COMPLETE 또는 ENDED_PARTIAL 만 낸다(`SessionEnded.status` 설명).
- 서버가 스스로 유휴를 재는지, 재면 `getSessionState`·`submitTurn` 이 마지막 활동에 드는지 계약에 적혀 있지 않다.

## 영역이 지금 한 것
60초 입력이 없으면 화면만 초기화하고 서버에는 아무것도 보내지 않는다(영역 ADR 0004). 서버가 스스로 만료시키지 않으면 세션이 열린 채 남는다. 멈춘 세션은 초기화하지 않는다(계약 `SessionStatus`). 2초 읽기는 멈춘 동안에만 한다.

## 요청
유휴 만료의 주체를 정해 달라. 서버가 `kiosk_idle_reset` 만큼 입력(턴)이 없으면 EXPIRED 로 하는 것이라면 그 기준(어떤 호출이 활동인가)을 `getSessionState` 설명에 적어 달라. 키오스크가 알리는 것이라면 EXPIRED 로 끝내는 작업이나 `endSession` 의 사유 칸을 더해 달라.

## 하지 않은 것
계약과 생성물을 영역에서 고치지 않았다.
