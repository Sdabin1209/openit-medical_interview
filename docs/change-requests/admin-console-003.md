# 변경 요청 admin-console-003: 알림 스트림 이벤트 타입이 생성 타입에 없다

- 영역: admin-console
- 대상 계약: `contracts/openapi/survey-service.yaml`(`streamStaffAlerts`), `contracts/components.yaml`(`StaffAlertEvent`, `AlertEventName`, `AlertStreamHeartbeatSeconds`)
- 상태: 헤드 결정 대기. 그동안 화면이 이 세 값을 `src/link/alerts.ts` 에 적고 `tests/contract/contract.test.ts` 가 계약 파일과 대조한다.

## 문제
`streamStaffAlerts` 는 이벤트 data 의 스키마를 미디어 유형의 `x-event-data-schema` 확장으로 가리킨다. `openapi-typescript` 는 이 확장을 따라가지 않아 `StaffAlertEvent`, `AlertEventName`, `AlertStreamHeartbeatSeconds` 가 `src/contract/survey-service.d.ts` 에 없다(생성 파일에서 세 이름을 찾아 확인). "계약 타입은 생성 명령으로만 만든다" 규칙(ADR 0020)을 지키려면 화면이 이 타입을 손으로 옮기는 일이 없어야 한다.

## 요청
이 세 스키마가 생성 타입에 들어오도록 계약에서 한 곳이라도 `$ref` 로 참조하게 한다(예: SSE 응답의 `x-event-data-schema` 와 별개로, 설명용 `examples` 나 `components.yaml` 의 참조 가능한 위치). 어떻게 할지는 헤드가 정한다.
