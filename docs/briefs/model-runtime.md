# model-runtime 브리프

공통 규칙은 [README](README.md). 맡는 일과 컴포넌트는 [design.md 2절 model-runtime](../design.md).

## 구현할 계약 작업(`contracts/openapi/model-runtime.yaml`, 6개 + healthz·readyz·metrics)
- survey-service(영역 mTLS + 기계 토큰 inference-caller): extractAction, generateResponse, getModelStatus
- admin-console(OIDC): getModelStatus, getModelPackage, activateModelPackage, rollbackModelPackage. 승인자 신원은 토큰의 sub.

## 공유 라이브러리 `libs/model-io`(이 영역이 채운다)
- 모델 입력 직렬화: 데이터셋 정본(`contracts/inputs/labels.py`, `IO_SPEC.md`)과 계약의 ModelInputSerialization(D77). 학습 데이터의 user 메시지 글자와 바이트까지 같아야 한다.
- 출력 검증(output_guard): 계약의 ActionExtractionRules 와 칸 규격으로 ViolationCode 10개를 한 번에 검사하고, D115 의 값 고쳐 쓰기를 적용한다. 결과는 검증된 출력 또는 출력 불가. 의미 위반율은 고쳐 쓰기 전 출력으로 센다.
- model-lab 의 평가가 같은 라이브러리를 쓴다(D97: 운영과 같은 검증기).
- 시험: 학습 파일의 정답 출력이 위반 0 이어야 한다(학습 서버 파일은 ssh 로 읽기만, 서버에 파일을 두지 않는다). 계약의 합격 조건마다 위반 사례 시험.

## 추론
- 추론 엔진은 vLLM(Apache-2.0)의 OpenAI 호환 서버를 별도 컨테이너로 두고, 기반 모델 + LoRA-A·LoRA-B 어댑터를 올린다(multi-LoRA). inference 컴포넌트는 OpenAI 호환 API 로 부른다. 선택과 설정은 ADR.
- 기반 모델 가중치는 도커 볼륨(외부 모델 허브에서 받음).
- GPU 가 없는 환경의 시험은 계약 타입으로 만든 가짜 엔진을 쓴다. 실제 GPU 확인은 별도 표시(GPU 시간대에만).

## 모델 패키지
- 레지스트리의 OCI 아티팩트(artifactType `application/vnd.openit.model.package.v1`, 계약 ModelPackageOciManifest), digest 로 받는다(ORAS 등 표준 클라이언트, ADR).
- 적재 전 검증: 매니페스트, 어댑터 해시, model_io_version, runtime_contract_version.
- 활성 포인터와 활성화·롤백 기록(승인자, 시각, 사유)의 저장 방식은 ADR 로 정한다.
- 추출 요청의 runtime_contract_version 이 적재 패키지와 다르면 409 QUESTION_BANK_VERSION_MISMATCH.

## 모델 패키지 게시 도구(package_publish)
- model-lab 을 나중에 만들기 전까지 모델 패키지를 만드는 유일한 경로다. 이미 학습한 LoRA-A·B 어댑터 폴더와 평가 집합(학습 서버 finaltest)을 받아 `libs/model-io` 로 평가 보고서를 만들고, 계약의 ModelPackageOciManifest 대로 레지스트리에 올린 뒤 digest 를 낸다.
- 표준 OCI 클라이언트(ORAS 등)로 올린다. 레지스트리 TLS 신뢰는 사설 루트(ADR 0013).
- 평가에 쓰는 추론은 실제 엔진이 필요하므로 GPU 에서 돈다. GPU 없는 시험은 가짜 엔진.

## 끝 조건(공통에 더해)
- 가짜 엔진으로: package_publish(로컬 레지스트리) → 패키지 적재 → 활성화 → 추출(정상, 위반 → 출력 불가, 고쳐 쓰기) → 응답 문장 → 롤백 시나리오 시험 rc=0.
- libs/model-io 시험 rc=0, 학습 파일 정답 출력 위반 0(측정 결과를 영역 README 5절에).
