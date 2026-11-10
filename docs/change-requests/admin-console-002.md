# 변경 요청 admin-console-002: 승인할 모델 패키지를 찾을 방법이 없다

- 영역: admin-console
- 대상 계약: `contracts/openapi/model-runtime.yaml`(`getModelPackage`, `getModelStatus`)
- 상태: 헤드 결정 대기. 그동안 승인자가 digest 를 직접 입력한다.

## 문제
`getModelPackage` 는 digest 를 알아야 읽는다. `getModelStatus` 는 활성 패키지와 직전 패키지의 digest 만 준다. 레지스트리에 게시된, 아직 승인하지 않은 후보 패키지의 목록을 얻는 작업이 없다. 승인자는 digest(`sha256:` 과 64자리 16진수)를 어디선가 받아 화면에 붙여 넣어야 한다. 오타는 404 로 드러나지만, 어느 패키지가 승인 대기인지는 화면이 알 수 없다.

## 요청
model-runtime 에 게시된 패키지 목록 작업(예: `GET /v1/model-packages`, 쪽 나누기, 각 항목에 digest·게시한 때·활성 여부)을 더한다. 화면은 목록에서 골라 평가 보고서를 보게 한다. 같은 요청에 "digest 는 레지스트리의 어느 화면에서 복사하는가"가 정해져 있다면 그 절차를 문서에 적어도 된다.
