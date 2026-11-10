# model-lab 브리프

공통 규칙은 [README](README.md). 맡는 일과 컴포넌트는 [design.md 2절 model-lab](../design.md).

폴더는 `jobs/model-lab`(`tools/new-area job model-lab`). 상시 서비스가 아니다. HTTP 서버가 없고, 잡 단계(import_dataset, prepare, train, evaluate, publish)를 한 번씩 실행하는 명령으로 만든다(12-Factor XII, ADR 0019). 같은 입력이면 같은 결과, 여러 번 실행해도 안전해야 한다(D39). 잡 실행 결과는 표준 출력 JSON 한 줄과 종료 코드 0·75·1(D130, JobRunResult).

## 단계
- import_dataset: 데이터셋 담당이 확정한 학습·평가 데이터(학습 서버 `~/dataset/final`, `finaltest`)를 가져와 계약의 DatasetRow·모델 입출력 스키마로 검증한다.
- link_failure_cases: survey-service 의 listFailureCaseExports(기계 토큰 case-reader)로 CONFIRMED 실패 사례를 받는다. 시험에서는 가짜 survey-service.
- prepare: 학습 형식 변환, 실패 사례를 회귀 평가 집합으로.
- train: LoRA-A·LoRA-B 학습. 표준 도구(Hugging Face PEFT·TRL, Apache-2.0)로 학습 서버 GPU 에서 실행한다. 설정은 파일로 받는다. 데이터셋 담당의 학습 방식을 따라 하되 그 코드를 복사하지 않고 공개 표준 도구로 같은 결과를 낸다.
- evaluate: `libs/model-io` 로 평가 보고서(계약의 필수 지표, 의미 위반율은 ViolationCode 별 조각)를 만든다.
- publish: 어댑터·매니페스트·평가 보고서를 OCI 아티팩트로 레지스트리에 올리고 digest 를 낸다.

## 학습 서버
- 학습 서버는 읽기·실행만 허용된 곳이다. 쓰기는 지정된 작업 폴더 안에서만, GPU 는 지정 시간대에만. 이 브리프 범위의 시험은 GPU 없이 돈다(작은 가짜 모델 또는 단계별 가짜).

## 끝 조건(공통에 더해)
- GPU 없이: import_dataset(학습 파일 표본) → prepare → train(가짜) → evaluate(가짜 출력으로 보고서) → publish(로컬 레지스트리) 시나리오 시험 rc=0.
- 실제 학습·평가는 GPU 시간대에 따로 확인하고, 하지 않았으면 하지 않았다고 README 5절에 적는다.
