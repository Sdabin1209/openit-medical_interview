# survey-service-005: 서비스 이미지의 잡 선언과 노출·입력 라벨을 만드는 길이 서비스 틀과 bake 에 없다

## 상태
요청(2026-11-10, survey-service 작업자). 대상: 헤드.

## 무엇이 어긋나나(읽어서 확인한 것)
- `design.md` 4절은 이미지 라벨 `io.openit.jobs`(JobsDeclaration), `io.openit.exposure`(Exposure), `io.openit.inputs`(ContainerInputs)를 정한다. 서비스 틀(`templates/service`)의 Dockerfile 과 `docker-bake.hcl` 의 `service` 대상에는 `io.openit.service`·`io.openit.contracts` 와 OCI 라벨만 있고 위 셋을 넣는 길이 없다. 잡 틀(`jobs/`)은 `jobs.json` 과 bake 의 `JOBS` 인자가 있다.
- 이 영역은 잡 둘(DETECT_FAILURES, PURGE_EXPIRED)을 가지며 `services/survey-service/jobs.json`(JobsDeclaration)에 선언을 두었다. deploy 가 서비스 이미지의 잡을 어떻게 부르는지(`python -m survey_service.jobs <잡> --requested-at <시각>` 은 영역의 선택)는 계약에 없다.
- 노출 경로와 나가는 호출 상대(model-runtime, 푸시 서비스, IdP)의 선언도 라벨로 나가지 않았다.

## 영역이 지금 한 것
선언 파일(`jobs.json`)만 두었고 이미지 라벨은 만들지 못했다. 노출·입력은 선언하지 않았다.

## 요청
서비스 이미지에도 `JOBS`(및 노출·입력) 인자를 넣는 틀과 bake 규칙을 정하고, deploy 가 서비스 잡을 부르는 호출 모양을 정해 달라. 정해지면 영역이 `jobs.json` 과 선언을 맞춘다.

## 하지 않은 것
계약과 생성물을 영역에서 고치지 않았다(계약은 동결이고 계약 타입은 생성 명령으로만 만든다).
