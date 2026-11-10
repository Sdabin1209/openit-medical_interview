# 변경 요청 admin-console-005: 브라우저가 두 서비스를 한 출처에서 부르는 경로가 계약에 없다

처리됨(계약 9.0.0(5f3c616, 848dbcb), platform a56d244, 화면 0e5103a, ADR 0021): 각 서비스가 자기 Exposure 로 경로를 선언하고 입구가 합친다. 두 화면은 /console/·/kiosk/ 접두어로 나눴다. 알림 스트림은 입구가 전체 시간 제한을 끈다.

- 영역: admin-console
- 대상 계약: `contracts/components.yaml`(`Exposure`, `ExposureRoute`), 두 openapi 의 `servers`
- 상태: 확인 요청. 화면은 같은 출처의 상대 경로(`/v1/...`, `/oauth2/...`)를 쓴다(ADR admin-console 0002).

## 문제
두 openapi 의 `servers` 는 `https://survey-service`, `https://model-runtime` 이다. 이것은 영역 사이 호출 주소다. 브라우저는 admin-console 의 한 출처만 알고, 같은 출처의 `/v1/...` 를 게이트웨이가 survey-service 와 model-runtime 으로 나눠 보내야 화면이 동작한다. 두 서비스의 `/v1/` 경로는 겹치지 않는다(survey-service 는 `/v1/results` 등, model-runtime 은 `/v1/model-*`). 그러나 이 라우팅을 누가 어디에 선언하는지, 그리고 oauth2-proxy 가 `Authorization: Bearer` 를 싣는 구성은 계약에 없다.

## 요청
admin-console 의 `Exposure.routes` 에 위 경로 접두어와 보내는 곳, 로그인 앞단(oauth2-proxy)을 지나는 경로를 적을 자리와 값을 정한다. 이 작업에서는 확인하지 못했고(가짜 서버로 시험), 화면은 상대 경로만 안다.

## 덧붙임: 알림 스트림은 응답 시간 제한과 맞아야 한다
`streamStaffAlerts` 는 끝이 없는 응답이다. 게이트웨이와 oauth2-proxy 의 응답 시간 제한이 이 경로에서 스트림을 끊지 않는지(끊으면 15초 heartbeat 와 재연결이 동작해 화면은 회복한다) 확인이 필요하다. 화면은 측정하지 않았다.
