# survey-service-001: 계약 타입 생성기가 securitySchemes 참조를 해석하지 못한다

처리됨(ca81f63)

## 상태
요청(2026-11-10, survey-service 작업자). 대상: tools/checks 의 소유자(헤드).

## 무엇이 막히나
`tools/new-area service survey-service` 가 계약 타입 생성 단계에서 멈춘다.

```
오류: openapi/survey-service.yaml: 해석할 수 없는 $ref '../components.yaml#/components/securitySchemes/device_mtls'
```

## 원인(읽어서 확인한 것)
- `contracts/openapi/survey-service.yaml` 524~527행과 `contracts/openapi/model-runtime.yaml` 163~166행은 `components.securitySchemes` 를 `$ref` 로 참조한다(OpenAPI 3.1 에서 허용되는 표준 참조).
- `tools/checks/src/openit_checks/contract_gen.py` 44행의 `REF` 정규식은 종류를 `schemas|responses|parameters|headers` 로만 받는다. `securitySchemes` 가 없어 `collect_schema_names` 가 오류를 낸다.
- 보안 체계는 값 타입이 아니라 생성할 모델이 없다. 닫힌 집합 계산에서 종류만 인식하고 건너뛰면 된다.

## 요청
- `REF` 의 종류에 `securitySchemes` 를 더하고, 이 종류는 `components` 에 있는지만 확인한 뒤 스키마 집합에는 넣지 않는다(`collect_schema_names` 의 `if kind == "schemas"` 가 이미 그렇게 거른다).
- 시험: 보안 체계 참조가 있는 openapi 로 생성이 성공하고, 생성물이 보안 체계 때문에 달라지지 않는지.

## 영향
- survey-service 와 model-runtime 은 이 수정 전에는 계약 타입을 만들 수 없어 구현을 시작하지 못한다. platform 은 보안 체계 참조가 없어 영향이 없다.
- 계약은 틀리지 않았다. 계약 변경은 필요 없다.

## 하지 않은 것
생성기를 영역에서 고쳐 쓰거나 생성물을 손으로 만드는 우회는 하지 않았다(영역은 tools/ 를 수정하지 않고 계약 타입은 생성 명령으로만 만든다, 브리프 공통 규칙).
