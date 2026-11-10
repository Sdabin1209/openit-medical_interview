# 변경 요청 model-runtime-007: 모델 적재 완료의 시간 상한이 계약에 없다

처리됨(계약 9.1.0, `ModelLoadLimitSeconds` 와 `TimeBudgetTable.model_load`): 영역의 적재 상한 구현은 model-runtime ADR 0012, deploy 의 E2E 는 상한을 계약에서 읽는다.

- 영역: model-runtime(발견은 deploy 의 E2E 첫 실행, `deploy/docs/E2E_RESULTS.md`)
- 대상 계약: `TimeBudgetTable`, `activateModelPackage`·`rollbackModelPackage`(`openapi/model-runtime.yaml`)

## 문제
활성화 요청(202)부터 `getModelStatus` 가 READY 나 FAILED 가 되기까지의 상한이 계약 시간 표(D125)에 없었다. 호출자가 얼마나 기다릴지, 서버가 언제 적재를 실패로 끝낼지 정해지지 않아 E2E 가 사람 화면의 다른 상한(190초)을 빌려 썼다.

## 결정
선택 칸 `model_load`(180초)를 더했다(MINOR). 값은 측정하지 않았고 표준도 없으며, D125 의 안쪽이 바깥보다 짧다는 원칙으로 사람 화면 최대 대기 190초 안에 두었다(근거는 계약 `x-basis`). 필수 칸으로 올리면 9.0.0 표가 깨져 MAJOR 이므로 다음 MAJOR 에서 올린다. 배경: `contracts/README.md` 9.1.0 절.
