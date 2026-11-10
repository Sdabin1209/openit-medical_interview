# deploy-001: 영역이 어느 영구 경로가 백업할 상태인지 선언할 칸이 없다

상태: 요청(2026-11-11, 배포 담당). 대상 계약: `WritablePath`(`ContainerInputs.writable_paths`).

## 무엇이 어긋나나(읽어서 확인한 것)
- 계약은 영역이 쓰는 경로와 그것이 유지되는지(`persistent`)를 선언하게 한다. 어느 유지 경로가 **백업해야 하는 상태**이고 어느 것이 **다시 받을 수 있는 캐시**인지는 선언하지 않는다.
- model-runtime 은 쓰기 경로 하나(`/var/lib/openit/model-runtime`)만 선언하고 그 안에 활성화·롤백 기록(상태)과 받은 패키지·모델 가중치(캐시)가 함께 있다(`cache/model-runtime/release-log.jsonl` 과 `cache/model-runtime/packages/…`).
- 그래서 deploy 는 백업 대상 경로를 compose 라벨(`io.openit.backup.paths`)에 직접 적는다(배포 ADR 0027). 이 경로는 영역 내부 구조(상태 폴더 이름, 기록 파일 이름)를 deploy 가 아는 것이다(구조 규칙 1). 지금은 `tools/checks` 시험이 영역 소스와 라벨이 같은지 본다.

## 요청
`WritablePath` 에 백업 여부(예: `backup: boolean` 또는 백업할 하위 경로 목록)를 더하는 것을 검토해 달라. 정해지면 deploy 는 compose 라벨 대신 이미지 선언(`io.openit.inputs`)을 읽고 model-runtime 이 `inputs.json` 에 선언한다.

## 지금 한 것
계약을 바꾸지 않았다. compose 라벨과 정적 시험으로 막았다. 선언이 생기면 라벨을 없앤다.
