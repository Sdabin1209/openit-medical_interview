# E2E 결과

`./deploy e2e` 가 쓰는 **E2E 실행 기록 한 곳**이다. 새 실행이 맨 위에 쌓인다. 영역의 시험 상태는 각 영역 README 5절, 배포 통합 확인은 [INTEGRATION.md](INTEGRATION.md)다.
실행 규약(샌드박스, 두 모드, 시나리오 여덟 단계, 판정)은 [ADR 0025](../../docs/adr/0025-E2E-실행-규약과-두-모드.md)다.

## 실행 2026-11-10T17:23:36+00:00 · pipeline · 실패

비고: 도구 개발 확인(최종 E2E 아님). 최종 후보 커밋 a56426d 기준

- 모드: pipeline
- 걸린 시간: 235초
- GPU: NVIDIA GeForce RTX 4070 SUPER, 12282 MiB, 591.86
- 프로파일·기반 모델: gpu-12g · Qwen/Qwen3-1.7B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: --gpu-memory-utilization 0.7 --max-model-len 8192)
- 어댑터: 중립 어댑터(B=0, rank 16, 내용 해시 LORA_A 5da95e2668eb, LORA_B 8f5d6f5ca7ed)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 28.5.1
- 영역 이미지 리비전: survey-service 8eba9f6982d8, model-runtime 8eba9f6982d8, web-admin-console 8eba9f6982d8, web-kiosk-frontend 8eba9f6982d8
- 리포 리비전: a56426d
- compose 프로젝트: openit-e2e-9f6a62
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 12.2 | 패키지 digest sha256:e041c57a96b0…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 실패 | 2.9 | getModelPackage 200(기반 모델 Qwen/Qwen3-1.7B, 어댑터 2개, 모델 입출력 model-io-v2); activateModelPackage 202; getModelStatus READY(적재 상한 190초 안), 활성 패키지가 게시한 것이다 **[발견] listModelPackages 가 방금 게시한 패키지를 주지 않았다(목록 0개). getModelPackage 는 같은 digest 를 준다** |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.3 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 통과 | 12.6 | startSession 201(ACTIVE, 모델이 만든 첫 문장 43자, 지금 문항 Q1.D01); submitTurn 6번 모두 200·계약 일치(성공 0, 실패 신호 6); 실패 신호 EXTRACTION_UNAVAILABLE 6건 모두 세션 상태·지금 문항 불변; endSession 200(ENDED_PARTIAL) |
| ⑥ 결과 조회·확인 표시(의사) | 통과 | 0.2 | listResults·getResult 200(상태 ENDED_PARTIAL, 저장된 답 0개, 빈칸 30개); acknowledgeResult 200, 결과에 확인한 의사와 시각이 남았다 |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 통과 | 0.0 | 기계 토큰(result-reader)으로 listResults·getResult 200, 의사가 본 결과와 같다. getResultFhir 200(QuestionnaireResponse, status stopped) |
| ⑧ 직원 호출 알림 | 통과 | 0.3 | requestStaffCall 201(CALL_STAFF), 직원의 listStaffAlerts 에 알림이 있고 세션이 PAUSED(STAFF_CALL)다 |

## 실행 2026-11-10T17:19:37+00:00 · product · 실패

비고: 도구 개발 확인(최종 E2E 아님): product 입력 경로 점검용으로 중립 어댑터를 학습된 어댑터 자리에 넣었다(기대 값 실패가 정상)

- 모드: product
- 걸린 시간: 215초
- GPU: NVIDIA GeForce RTX 4070 SUPER, 12282 MiB, 591.86
- 프로파일·기반 모델: gpu-12g · Qwen/Qwen3-1.7B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: --gpu-memory-utilization 0.7 --max-model-len 8192)
- 어댑터: 학습된 어댑터(호출자가 준 폴더)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 28.5.1
- 영역 이미지 리비전: survey-service 8eba9f6982d8, model-runtime 8eba9f6982d8, web-admin-console 8eba9f6982d8, web-kiosk-frontend 8eba9f6982d8
- 리포 리비전: a56426d
- compose 프로젝트: openit-e2e-8f3d09
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 5.9 | 패키지 digest sha256:89dd3eef7f58…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 실패 | 3.0 | getModelPackage 200(기반 모델 Qwen/Qwen3-1.7B, 어댑터 2개, 모델 입출력 model-io-v2); activateModelPackage 202; getModelStatus READY(적재 상한 190초 안), 활성 패키지가 게시한 것이다 **[발견] listModelPackages 가 방금 게시한 패키지를 주지 않았다(목록 0개). getModelPackage 는 같은 digest 를 준다** |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.4 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 실패 | 1.0 | startSession 201(ACTIVE, 모델이 만든 첫 문장 43자, 지금 문항 Q1.D01) [StepFailure: product 모드에서 턴이 실패 신호(EXTRACTION_UNAVAILABLE)를 냈다(문항 Q1.D01, 1번째 턴). 실패한 턴을 다시 보내지 않는다] |
| ⑥ 결과 조회·확인 표시(의사) | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |
| ⑧ 직원 호출 알림 | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |

## 실행 2026-11-10T17:08:45+00:00 · pipeline · 실패

비고: 도구 개발 확인(최종 E2E 아님) 4

- 모드: pipeline
- 걸린 시간: 240초
- GPU: NVIDIA GeForce RTX 4070 SUPER, 12282 MiB, 591.86
- 프로파일·기반 모델: gpu-12g · Qwen/Qwen3-1.7B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: --gpu-memory-utilization 0.7 --max-model-len 8192)
- 어댑터: 중립 어댑터(B=0, rank 16, 내용 해시 LORA_A 5da95e2668eb, LORA_B 8f5d6f5ca7ed)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 28.5.1
- 영역 이미지 리비전: survey-service 8eba9f6982d8, model-runtime 8eba9f6982d8, web-admin-console 8eba9f6982d8, web-kiosk-frontend 8eba9f6982d8
- 리포 리비전: e39a646
- compose 프로젝트: openit-e2e-623210
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 12.1 | 패키지 digest sha256:7e966d5e5d74…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 실패 | 3.3 | getModelPackage 200(기반 모델 Qwen/Qwen3-1.7B, 어댑터 2개, 모델 입출력 model-io-v2); activateModelPackage 202; getModelStatus READY(적재 상한 190초 안), 활성 패키지가 게시한 것이다 **[발견] listModelPackages 가 방금 게시한 패키지를 주지 않았다(목록 0개). getModelPackage 는 같은 digest 를 준다** |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.4 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 통과 | 12.6 | startSession 201(ACTIVE, 모델이 만든 첫 문장 43자, 지금 문항 Q1.D01); submitTurn 6번 모두 200·계약 일치(성공 0, 실패 신호 6); 실패 신호 EXTRACTION_UNAVAILABLE 6건 모두 세션 상태·지금 문항 불변; endSession 200(ENDED_PARTIAL) |
| ⑥ 결과 조회·확인 표시(의사) | 통과 | 0.1 | listResults·getResult 200(상태 ENDED_PARTIAL, 저장된 답 0개, 빈칸 30개); acknowledgeResult 200, 결과에 확인한 의사와 시각이 남았다 |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 통과 | 0.1 | 기계 토큰(result-reader)으로 listResults·getResult 200, 의사가 본 결과와 같다. getResultFhir 200(QuestionnaireResponse, status stopped) |
| ⑧ 직원 호출 알림 | 통과 | 0.4 | requestStaffCall 201(CALL_STAFF), 직원의 listStaffAlerts 에 알림이 있고 세션이 PAUSED(STAFF_CALL)다 |
