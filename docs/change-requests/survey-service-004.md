# survey-service-004: 계약 타입 생성기가 format uri 와 같이 있는 pattern 을 버려 PeerBaseUrl 의 https 조건이 생성 모델에서 빠진다

처리됨(생성기 af13587, 영역 e47d70e): 생성기가 format uri 와 pattern 이 같이 있으면 pattern 을 모델에 싣는다. 영역의 따로 확인하는 코드를 지웠다.

## 상태
요청(2026-11-10, survey-service 작업자). 대상: 헤드.

## 무엇이 어긋나나(읽어서 확인한 것)
- `PeerBaseUrl` 은 `format: uri` 와 `pattern: ^https://` 를 함께 갖는다(영역 사이 모든 HTTP 는 TLS, C14). `openit-gen-contract` 가 만든 모델은 `AnyUrl` 이라 `http://` 도 받는다(시험으로 확인: `OPENIT_MODEL_RUNTIME_URL=http://model-runtime` 이 통과했다).
- 같은 조합의 다른 값(`EgressProxyUrl` 등)도 같은 영향이 있을 수 있다(확인하지 않았다).

## 영역이 지금 한 것
영역이 설정 읽기에서 https 만 받도록 따로 확인한다(`settings.load_env`). 계약 조건이 코드에 한 번 더 적혀 있다.

## 요청
생성기가 `format: uri` 와 `pattern` 이 함께 있을 때 둘 다 모델에 싣게 고치거나(`AnyUrl` 에 `UrlConstraints`), 계약의 `pattern` 을 `format` 대신 쓰게 해 달라. 고쳐지면 영역의 따로 확인하는 코드를 지운다.

## 하지 않은 것
계약과 생성물을 영역에서 고치지 않았다(계약은 동결이고 계약 타입은 생성 명령으로만 만든다).
