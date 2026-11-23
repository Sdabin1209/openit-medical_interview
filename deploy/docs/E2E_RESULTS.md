# E2E 결과

`./deploy e2e` 가 쓰는 **E2E 실행 기록 한 곳**이다. 새 실행이 맨 위에 쌓인다. 영역의 시험 상태는 각 영역 README 5절, 배포 통합 확인은 [INTEGRATION.md](INTEGRATION.md)다.
실행 규약(샌드박스, 두 모드, 시나리오 여덟 단계, 판정)은 [ADR 0025](../../docs/adr/0025-E2E-실행-규약과-두-모드.md)다.

## 실행 2026-11-23T07:25:06+00:00 · product · 통과

비고: 1118 어댑터(모델 입출력 v3)

- 모드: product
- 걸린 시간: 344초
- GPU: NVIDIA RTX A6000, 49140 MiB, 595.91.07
- 프로파일·기반 모델: rtx4090-24g · Qwen/Qwen3-8B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: 제품 기본값)
- 어댑터: 학습된 어댑터(호출자가 준 폴더)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 29.9.3
- 영역 이미지 리비전: survey-service 897e2ef2f153, model-runtime 897e2ef2f153, web-admin-console 897e2ef2f153, web-kiosk-frontend 897e2ef2f153
- 리포 리비전: 897e2ef
- compose 프로젝트: openit-e2e-794ebb
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 10.5 | 패키지 digest sha256:6121efb01663…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 통과 | 2.9 | getModelPackage 200(기반 모델 Qwen/Qwen3-8B, 어댑터 2개, 모델 입출력 model-io-v3); listModelPackages 에 게시한 패키지가 있다; activateModelPackage 202; getModelStatus READY(계약 적재 상한 180초 안), 활성 패키지가 게시한 것이다 |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.4 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 통과 | 95.2 | startSessionStream 세션 시작: delta 62개, 첫 delta 0.22초, result 1.96초; startSessionStream 200·SSE(결과는 SessionStarted, ACTIVE, 모델이 만든 첫 문장 97자, 지금 문항 Q1.D01); submitTurnStream 1번째 턴: delta 50개, 첫 delta 2.88초, result 4.31초; submitTurnStream 2번째 턴: delta 42개, 첫 delta 3.63초, result 4.81초; submitTurnStream 3번째 턴: delta 49개, 첫 delta 2.79초, result 4.19초; submitTurnStream 4번째 턴: delta 42개, 첫 delta 2.79초, result 3.98초; submitTurnStream 5번째 턴: delta 61개, 첫 delta 3.61초, result 5.30초; submitTurnStream 6번째 턴: delta 45개, 첫 delta 2.80초, result 4.29초; submitTurnStream 7번째 턴: delta 47개, 첫 delta 2.79초, result 4.14초; submitTurnStream 8번째 턴: delta 44개, 첫 delta 2.79초, result 4.03초; submitTurnStream 9번째 턴: delta 45개, 첫 delta 2.78초, result 4.05초; submitTurnStream 10번째 턴: delta 47개, 첫 delta 2.77초, result 4.09초; submitTurnStream 11번째 턴: delta 49개, 첫 delta 2.78초, result 4.16초; submitTurnStream 12번째 턴: delta 43개, 첫 delta 2.80초, result 4.02초; submitTurnStream 13번째 턴: delta 51개, 첫 delta 2.78초, result 4.23초; submitTurnStream 14번째 턴: delta 54개, 첫 delta 1.82초, result 3.35초; submitTurnStream 15번째 턴: delta 54개, 첫 delta 1.79초, result 3.27초; submitTurnStream 16번째 턴: delta 42개, 첫 delta 1.79초, result 2.92초; submitTurnStream 17번째 턴: delta 52개, 첫 delta 2.38초, result 3.78초; submitTurnStream 18번째 턴: delta 51개, 첫 delta 1.80초, result 3.18초; submitTurnStream 19번째 턴: delta 28개, 첫 delta 1.72초, result 2.46초; submitTurnStream 20번째 턴: delta 47개, 첫 delta 1.65초, result 2.97초; submitTurnStream 21번째 턴: delta 47개, 첫 delta 1.62초, result 2.94초; submitTurnStream 22번째 턴: delta 30개, 첫 delta 1.62초, result 2.50초; submitTurnStream 23번째 턴: delta 32개, 첫 delta 1.62초, result 2.59초; submitTurnStream 24번째 턴: delta 39개, 첫 delta 1.77초, result 2.92초; submitTurnStream 25번째 턴: delta 38개, 첫 delta 3.50초, result 4.55초; submitTurnStream 25번 모두 200·SSE·계약 일치(성공 25, 실패 신호 0, 한도 3에 닿아 건너뜀 0); endSession 200(ENDED_COMPLETE); 스트림 26건 합계: delta 1191개, 첫 delta 가장 빠른 값 0.22초 |
| ⑥ 결과 조회·확인 표시(의사) | 통과 | 0.2 | listResults·getResult 200(상태 ENDED_COMPLETE, 저장된 답 35개, 빈칸 7개); 모델 관찰(판정 밖): 대본의 기대 값 중 3/36개가 결과와 다르다: Q10.days: 결과 0.0 기대 3; Q9_1.days: 결과 0.0 기대 3; Q9_2.duration_minutes: 결과 (없음) 기대 40; acknowledgeResult 200, 결과에 확인한 의사와 시각이 남았다 |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 통과 | 0.1 | 기계 토큰(result-reader)으로 listResults·getResult 200, 의사가 본 결과와 같다. getResultFhir 200(QuestionnaireResponse, status completed) |
| ⑧ 직원 호출 알림 | 통과 | 1.8 | requestStaffCall 201(CALL_STAFF), 직원의 listStaffAlerts 에 알림이 있고 세션이 PAUSED(STAFF_CALL)다 |

## 실행 2026-11-23T07:20:07+00:00 · product · 통과

비고: 기준 어댑터 회귀(계약 9.4.0 뒤)

- 모드: product
- 걸린 시간: 298초
- GPU: NVIDIA RTX A6000, 49140 MiB, 595.91.07
- 프로파일·기반 모델: rtx4090-24g · Qwen/Qwen3-8B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: 제품 기본값)
- 어댑터: 학습된 어댑터(호출자가 준 폴더)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 29.9.3
- 영역 이미지 리비전: survey-service 897e2ef2f153, model-runtime 897e2ef2f153, web-admin-console 897e2ef2f153, web-kiosk-frontend 897e2ef2f153
- 리포 리비전: 897e2ef
- compose 프로젝트: openit-e2e-6c47a3
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 10.2 | 패키지 digest sha256:1ce740f22677…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 통과 | 2.9 | getModelPackage 200(기반 모델 Qwen/Qwen3-8B, 어댑터 2개, 모델 입출력 model-io-v2); listModelPackages 에 게시한 패키지가 있다; activateModelPackage 202; getModelStatus READY(계약 적재 상한 180초 안), 활성 패키지가 게시한 것이다 |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.4 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 통과 | 29.1 | startSessionStream 세션 시작: delta 61개, 첫 delta 0.20초, result 1.92초; startSessionStream 200·SSE(결과는 SessionStarted, ACTIVE, 모델이 만든 첫 문장 90자, 지금 문항 Q1.D01); submitTurnStream 1번째 턴: delta 46개, 첫 delta 2.88초, result 4.21초; submitTurnStream 2번째 턴: delta 42개, 첫 delta 3.64초, result 4.89초; submitTurnStream 3번째 턴: delta 46개, 첫 delta 2.79초, result 4.11초; submitTurnStream 4번째 턴: delta 42개, 첫 delta 3.61초, result 4.86초; submitTurnStream 5번째 턴: delta 46개, 첫 delta 2.78초, result 4.11초; submitTurnStream 6번째 턴: delta 42개, 첫 delta 3.60초, result 4.94초; submitTurnStream 6번 모두 200·SSE·계약 일치(성공 6, 실패 신호 0, 한도 3에 닿아 건너뜀 0); endSession 200(ENDED_PARTIAL); 스트림 7건 합계: delta 325개, 첫 delta 가장 빠른 값 0.20초; 모델 관찰(판정 밖): 문항 Q1.D01 이 3번 되돌아와(확인·되묻기 반복) 6턴에서 멈췄다; 문진이 끝까지 가지 않았다(ENDED_PARTIAL, 6턴) |
| ⑥ 결과 조회·확인 표시(의사) | 통과 | 0.2 | listResults·getResult 200(상태 ENDED_PARTIAL, 저장된 답 2개, 빈칸 29개); 모델 관찰(판정 밖): 대본의 기대 값 중 34/36개가 결과와 다르다: Q1.D02.diagnosed: 결과 (없음) 기대 False; Q1.D02.on_medication: 결과 (없음) 기대 False; Q1.D03.diagnosed: 결과 (없음) 기대 True; Q1.D03.on_medication: 결과 (없음) 기대 True; Q1.D04.diagnosed: 결과 (없음) 기대 False; Q1.D04.on_medication: 결과 (없음) 기대 False; Q1.D05.diagnosed: 결과 (없음) 기대 False; Q1.D05.on_medication: 결과 (없음) 기대 False; acknowledgeResult 200, 결과에 확인한 의사와 시각이 남았다 |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 통과 | 0.1 | 기계 토큰(result-reader)으로 listResults·getResult 200, 의사가 본 결과와 같다. getResultFhir 200(QuestionnaireResponse, status stopped) |
| ⑧ 직원 호출 알림 | 통과 | 1.9 | requestStaffCall 201(CALL_STAFF), 직원의 listStaffAlerts 에 알림이 있고 세션이 PAUSED(STAFF_CALL)다 |

## 실행 2026-11-23T05:41:34+00:00 · product · 통과

비고(헤드, 기록을 옮기며 더함): 첫 임대 서버의 탐색 실행. 리포 리비전 3598873 의 작업 트리에 커밋 전 변경이 있었다(판정 변경은 뒤에 86d68a6, nginx 취약점 임시 무시 목록은 커밋하지 않음). 환경 문제와 원인은 NoneCommit/TODO.md 의 I1~I6

- 모드: product
- 걸린 시간: 320초
- GPU: NVIDIA RTX A6000, 49140 MiB, 595.91.07
- 프로파일·기반 모델: rtx4090-24g · Qwen/Qwen3-8B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: 제품 기본값)
- 어댑터: 학습된 어댑터(호출자가 준 폴더)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 29.9.3
- 영역 이미지 리비전: survey-service 35988734134b, model-runtime 35988734134b, web-admin-console 35988734134b, web-kiosk-frontend 35988734134b
- 리포 리비전: 3598873
- compose 프로젝트: openit-e2e-7301cd
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 11.3 | 패키지 digest sha256:11bbd46be029…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 통과 | 3.0 | getModelPackage 200(기반 모델 Qwen/Qwen3-8B, 어댑터 2개, 모델 입출력 model-io-v2); listModelPackages 에 게시한 패키지가 있다; activateModelPackage 202; getModelStatus READY(계약 적재 상한 180초 안), 활성 패키지가 게시한 것이다 |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.4 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 통과 | 29.8 | startSessionStream 세션 시작: delta 61개, 첫 delta 0.23초, result 1.94초; startSessionStream 200·SSE(결과는 SessionStarted, ACTIVE, 모델이 만든 첫 문장 90자, 지금 문항 Q1.D01); submitTurnStream 1번째 턴: delta 46개, 첫 delta 2.93초, result 4.26초; submitTurnStream 2번째 턴: delta 42개, 첫 delta 3.69초, result 4.94초; submitTurnStream 3번째 턴: delta 46개, 첫 delta 2.86초, result 4.19초; submitTurnStream 4번째 턴: delta 42개, 첫 delta 3.68초, result 4.92초; submitTurnStream 5번째 턴: delta 46개, 첫 delta 2.81초, result 4.14초; submitTurnStream 6번째 턴: delta 42개, 첫 delta 3.64초, result 5.27초; submitTurnStream 6번 모두 200·SSE·계약 일치(성공 6, 실패 신호 0, 한도 3에 닿아 건너뜀 0); endSession 200(ENDED_PARTIAL); 스트림 7건 합계: delta 325개, 첫 delta 가장 빠른 값 0.23초; 모델 관찰(판정 밖): 문항 Q1.D01 이 3번 되돌아와(확인·되묻기 반복) 6턴에서 멈췄다; 문진이 끝까지 가지 않았다(ENDED_PARTIAL, 6턴) |
| ⑥ 결과 조회·확인 표시(의사) | 통과 | 0.2 | listResults·getResult 200(상태 ENDED_PARTIAL, 저장된 답 2개, 빈칸 29개); 모델 관찰(판정 밖): 대본의 기대 값 중 34/36개가 결과와 다르다: Q1.D02.diagnosed: 결과 (없음) 기대 False; Q1.D02.on_medication: 결과 (없음) 기대 False; Q1.D03.diagnosed: 결과 (없음) 기대 True; Q1.D03.on_medication: 결과 (없음) 기대 True; Q1.D04.diagnosed: 결과 (없음) 기대 False; Q1.D04.on_medication: 결과 (없음) 기대 False; Q1.D05.diagnosed: 결과 (없음) 기대 False; Q1.D05.on_medication: 결과 (없음) 기대 False; acknowledgeResult 200, 결과에 확인한 의사와 시각이 남았다 |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 통과 | 0.1 | 기계 토큰(result-reader)으로 listResults·getResult 200, 의사가 본 결과와 같다. getResultFhir 200(QuestionnaireResponse, status stopped) |
| ⑧ 직원 호출 알림 | 통과 | 1.9 | requestStaffCall 201(CALL_STAFF), 직원의 listStaffAlerts 에 알림이 있고 세션이 PAUSED(STAFF_CALL)다 |

## 실행 2026-11-23T05:18:40+00:00 · product · 실패

비고(헤드, 기록을 옮기며 더함): 첫 임대 서버의 탐색 실행. 리포 리비전 3598873 의 작업 트리에 커밋 전 변경이 있었다(판정 변경은 뒤에 86d68a6, nginx 취약점 임시 무시 목록은 커밋하지 않음). 환경 문제와 원인은 NoneCommit/TODO.md 의 I1~I6

- 모드: product
- 걸린 시간: 289초
- GPU: NVIDIA RTX A6000, 49140 MiB, 595.91.07
- 프로파일·기반 모델: rtx4090-24g · Qwen/Qwen3-8B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: 제품 기본값)
- 어댑터: 학습된 어댑터(호출자가 준 폴더)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 29.9.3
- 영역 이미지 리비전: survey-service 35988734134b, model-runtime 35988734134b, web-admin-console 35988734134b, web-kiosk-frontend 35988734134b
- 리포 리비전: 3598873
- compose 프로젝트: openit-e2e-30b560
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 17.3 | 패키지 digest sha256:00bcb8417e4d…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 통과 | 2.8 | getModelPackage 200(기반 모델 Qwen/Qwen3-8B, 어댑터 2개, 모델 입출력 model-io-v2); listModelPackages 에 게시한 패키지가 있다; activateModelPackage 202; getModelStatus READY(계약 적재 상한 180초 안), 활성 패키지가 게시한 것이다 |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.4 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 실패 | 13.1 | startSessionStream 세션 시작: delta 62개, 첫 delta 0.21초, result 1.95초; startSessionStream 200·SSE(결과는 SessionStarted, ACTIVE, 모델이 만든 첫 문장 97자, 지금 문항 Q1.D01); submitTurnStream 1번째 턴: delta 50개, 첫 delta 2.89초, result 4.32초; submitTurnStream 2번째 턴: delta 0개, 첫 delta -, result 6.83초 [StepFailure: product 모드에서 턴이 실패 신호(EXTRACTION_UNAVAILABLE)를 냈다(문항 Q1.D02, 2번째 턴). 실패한 턴을 다시 보내지 않는다] |
| ⑥ 결과 조회·확인 표시(의사) | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |
| ⑧ 직원 호출 알림 | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |

## 실행 2026-11-23T05:06:04+00:00 · product · 실패

비고(헤드, 기록을 옮기며 더함): 첫 임대 서버의 탐색 실행. 리포 리비전 3598873 의 작업 트리에 커밋 전 변경이 있었다(판정 변경은 뒤에 86d68a6, nginx 취약점 임시 무시 목록은 커밋하지 않음). 환경 문제와 원인은 NoneCommit/TODO.md 의 I1~I6

- 모드: product
- 걸린 시간: 390초
- GPU: NVIDIA RTX A6000, 49140 MiB, 595.91.07
- 프로파일·기반 모델: rtx4090-24g · Qwen/Qwen3-8B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: 제품 기본값)
- 어댑터: 학습된 어댑터(호출자가 준 폴더)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 29.9.3
- 영역 이미지 리비전: survey-service 35988734134b, model-runtime 35988734134b, web-admin-console 35988734134b, web-kiosk-frontend 35988734134b
- 리포 리비전: 3598873
- compose 프로젝트: openit-e2e-32d293
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 10.8 | 패키지 digest sha256:6651d7cccd22…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 통과 | 2.8 | getModelPackage 200(기반 모델 Qwen/Qwen3-8B, 어댑터 2개, 모델 입출력 model-io-v2); listModelPackages 에 게시한 패키지가 있다; activateModelPackage 202; getModelStatus READY(계약 적재 상한 180초 안), 활성 패키지가 게시한 것이다 |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.4 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 실패 | 137.0 | startSessionStream 세션 시작: delta 61개, 첫 delta 0.19초, result 1.91초; startSessionStream 200·SSE(결과는 SessionStarted, ACTIVE, 모델이 만든 첫 문장 90자, 지금 문항 Q1.D01); submitTurnStream 1번째 턴: delta 46개, 첫 delta 2.89초, result 4.22초; submitTurnStream 2번째 턴: delta 42개, 첫 delta 3.66초, result 4.90초; submitTurnStream 3번째 턴: delta 46개, 첫 delta 2.79초, result 4.12초; submitTurnStream 4번째 턴: delta 42개, 첫 delta 3.62초, result 4.86초; submitTurnStream 5번째 턴: delta 46개, 첫 delta 2.78초, result 4.11초; submitTurnStream 6번째 턴: delta 42개, 첫 delta 3.62초, result 5.13초; submitTurnStream 7번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 8번째 턴: delta 42개, 첫 delta 3.61초, result 4.86초; submitTurnStream 9번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 10번째 턴: delta 42개, 첫 delta 3.60초, result 4.85초; submitTurnStream 11번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 12번째 턴: delta 42개, 첫 delta 3.61초, result 4.85초; submitTurnStream 13번째 턴: delta 46개, 첫 delta 2.78초, result 4.11초; submitTurnStream 14번째 턴: delta 42개, 첫 delta 3.61초, result 4.85초; submitTurnStream 15번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 16번째 턴: delta 42개, 첫 delta 3.61초, result 4.85초; submitTurnStream 17번째 턴: delta 46개, 첫 delta 2.78초, result 4.11초; submitTurnStream 18번째 턴: delta 42개, 첫 delta 3.62초, result 4.87초; submitTurnStream 19번째 턴: delta 46개, 첫 delta 2.78초, result 4.11초; submitTurnStream 20번째 턴: delta 42개, 첫 delta 3.66초, result 4.91초; submitTurnStream 21번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 22번째 턴: delta 42개, 첫 delta 3.60초, result 4.85초; submitTurnStream 23번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 24번째 턴: delta 42개, 첫 delta 3.61초, result 4.85초; submitTurnStream 25번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 26번째 턴: delta 42개, 첫 delta 3.60초, result 4.85초; submitTurnStream 27번째 턴: delta 46개, 첫 delta 2.77초, result 4.10초; submitTurnStream 28번째 턴: delta 42개, 첫 delta 3.60초, result 4.85초; submitTurnStream 29번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 30번째 턴: delta 42개, 첫 delta 3.60초, result 4.85초; submitTurnStream 30번 모두 200·SSE·계약 일치(성공 30, 실패 신호 0, 한도 3에 닿아 건너뜀 0); endSession 200(ENDED_PARTIAL); 스트림 31건 합계: delta 1381개, 첫 delta 가장 빠른 값 0.19초 [StepFailure: product 모드는 문진이 끝까지 가야 한다(ENDED_COMPLETE). 실제 ENDED_PARTIAL] |
| ⑥ 결과 조회·확인 표시(의사) | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |
| ⑧ 직원 호출 알림 | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |

## 실행 2026-11-23T04:54:12+00:00 · product · 실패

비고(헤드, 기록을 옮기며 더함): 첫 임대 서버의 탐색 실행. 리포 리비전 3598873 의 작업 트리에 커밋 전 변경이 있었다(판정 변경은 뒤에 86d68a6, nginx 취약점 임시 무시 목록은 커밋하지 않음). 환경 문제와 원인은 NoneCommit/TODO.md 의 I1~I6

- 모드: product
- 걸린 시간: 405초
- GPU: NVIDIA RTX A6000, 49140 MiB, 595.91.07
- 프로파일·기반 모델: rtx4090-24g · Qwen/Qwen3-8B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: 제품 기본값)
- 어댑터: 학습된 어댑터(호출자가 준 폴더)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 29.9.3
- 영역 이미지 리비전: survey-service 35988734134b, model-runtime 35988734134b, web-admin-console 35988734134b, web-kiosk-frontend 35988734134b
- 리포 리비전: 3598873
- compose 프로젝트: openit-e2e-bda226
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 10.9 | 패키지 digest sha256:e50a220101b8…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 통과 | 2.8 | getModelPackage 200(기반 모델 Qwen/Qwen3-8B, 어댑터 2개, 모델 입출력 model-io-v2); listModelPackages 에 게시한 패키지가 있다; activateModelPackage 202; getModelStatus READY(계약 적재 상한 180초 안), 활성 패키지가 게시한 것이다 |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.4 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 실패 | 138.1 | startSessionStream 세션 시작: delta 61개, 첫 delta 0.20초, result 1.91초; startSessionStream 200·SSE(결과는 SessionStarted, ACTIVE, 모델이 만든 첫 문장 90자, 지금 문항 Q1.D01); submitTurnStream 1번째 턴: delta 46개, 첫 delta 2.88초, result 4.20초; submitTurnStream 2번째 턴: delta 42개, 첫 delta 3.64초, result 4.89초; submitTurnStream 3번째 턴: delta 46개, 첫 delta 2.79초, result 4.11초; submitTurnStream 4번째 턴: delta 42개, 첫 delta 3.63초, result 4.87초; submitTurnStream 5번째 턴: delta 46개, 첫 delta 2.83초, result 4.15초; submitTurnStream 6번째 턴: delta 42개, 첫 delta 3.64초, result 5.44초; submitTurnStream 7번째 턴: delta 46개, 첫 delta 2.82초, result 4.61초; submitTurnStream 8번째 턴: delta 42개, 첫 delta 3.66초, result 4.91초; submitTurnStream 9번째 턴: delta 46개, 첫 delta 2.81초, result 4.13초; submitTurnStream 10번째 턴: delta 42개, 첫 delta 3.70초, result 4.94초; submitTurnStream 11번째 턴: delta 46개, 첫 delta 2.79초, result 4.11초; submitTurnStream 12번째 턴: delta 42개, 첫 delta 3.62초, result 4.86초; submitTurnStream 13번째 턴: delta 46개, 첫 delta 2.79초, result 4.12초; submitTurnStream 14번째 턴: delta 42개, 첫 delta 3.63초, result 4.87초; submitTurnStream 15번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 16번째 턴: delta 42개, 첫 delta 3.61초, result 4.86초; submitTurnStream 17번째 턴: delta 46개, 첫 delta 2.78초, result 4.11초; submitTurnStream 18번째 턴: delta 42개, 첫 delta 3.60초, result 4.85초; submitTurnStream 19번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 20번째 턴: delta 42개, 첫 delta 3.61초, result 4.85초; submitTurnStream 21번째 턴: delta 46개, 첫 delta 2.79초, result 4.11초; submitTurnStream 22번째 턴: delta 42개, 첫 delta 3.62초, result 4.87초; submitTurnStream 23번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 24번째 턴: delta 42개, 첫 delta 3.61초, result 4.85초; submitTurnStream 25번째 턴: delta 46개, 첫 delta 2.82초, result 4.14초; submitTurnStream 26번째 턴: delta 42개, 첫 delta 3.62초, result 4.87초; submitTurnStream 27번째 턴: delta 46개, 첫 delta 2.78초, result 4.11초; submitTurnStream 28번째 턴: delta 42개, 첫 delta 3.61초, result 4.85초; submitTurnStream 29번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 30번째 턴: delta 42개, 첫 delta 3.60초, result 4.85초; submitTurnStream 30번 모두 200·SSE·계약 일치(성공 30, 실패 신호 0, 한도 3에 닿아 건너뜀 0); endSession 200(ENDED_PARTIAL); 스트림 31건 합계: delta 1381개, 첫 delta 가장 빠른 값 0.20초 [StepFailure: product 모드는 문진이 끝까지 가야 한다(ENDED_COMPLETE). 실제 ENDED_PARTIAL] |
| ⑥ 결과 조회·확인 표시(의사) | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |
| ⑧ 직원 호출 알림 | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |

## 실행 2026-11-23T04:45:43+00:00 · product · 실패

비고(헤드, 기록을 옮기며 더함): 첫 임대 서버의 탐색 실행. 리포 리비전 3598873 의 작업 트리에 커밋 전 변경이 있었다(판정 변경은 뒤에 86d68a6, nginx 취약점 임시 무시 목록은 커밋하지 않음). 환경 문제와 원인은 NoneCommit/TODO.md 의 I1~I6

- 모드: product
- 걸린 시간: 435초
- GPU: NVIDIA RTX A6000, 49140 MiB, 595.91.07
- 프로파일·기반 모델: rtx4090-24g · Qwen/Qwen3-8B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: 제품 기본값)
- 어댑터: 학습된 어댑터(호출자가 준 폴더)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 29.9.3
- 영역 이미지 리비전: survey-service 35988734134b, model-runtime 35988734134b, web-admin-console 35988734134b, web-kiosk-frontend 35988734134b
- 리포 리비전: 3598873
- compose 프로젝트: openit-e2e-6437bd
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 11.2 | 패키지 digest sha256:b43f86915675…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 통과 | 2.9 | getModelPackage 200(기반 모델 Qwen/Qwen3-8B, 어댑터 2개, 모델 입출력 model-io-v2); listModelPackages 에 게시한 패키지가 있다; activateModelPackage 202; getModelStatus READY(계약 적재 상한 180초 안), 활성 패키지가 게시한 것이다 |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.4 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 실패 | 137.1 | startSessionStream 세션 시작: delta 61개, 첫 delta 0.21초, result 1.91초; startSessionStream 200·SSE(결과는 SessionStarted, ACTIVE, 모델이 만든 첫 문장 90자, 지금 문항 Q1.D01); submitTurnStream 1번째 턴: delta 46개, 첫 delta 2.90초, result 4.22초; submitTurnStream 2번째 턴: delta 42개, 첫 delta 3.66초, result 4.91초; submitTurnStream 3번째 턴: delta 46개, 첫 delta 2.79초, result 4.12초; submitTurnStream 4번째 턴: delta 42개, 첫 delta 3.62초, result 4.87초; submitTurnStream 5번째 턴: delta 46개, 첫 delta 2.80초, result 4.12초; submitTurnStream 6번째 턴: delta 42개, 첫 delta 3.61초, result 5.23초; submitTurnStream 7번째 턴: delta 46개, 첫 delta 2.79초, result 4.11초; submitTurnStream 8번째 턴: delta 42개, 첫 delta 3.62초, result 4.86초; submitTurnStream 9번째 턴: delta 46개, 첫 delta 2.80초, result 4.12초; submitTurnStream 10번째 턴: delta 42개, 첫 delta 3.61초, result 4.86초; submitTurnStream 11번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 12번째 턴: delta 42개, 첫 delta 3.62초, result 4.86초; submitTurnStream 13번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 14번째 턴: delta 42개, 첫 delta 3.61초, result 4.86초; submitTurnStream 15번째 턴: delta 46개, 첫 delta 2.79초, result 4.11초; submitTurnStream 16번째 턴: delta 42개, 첫 delta 3.60초, result 4.85초; submitTurnStream 17번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 18번째 턴: delta 42개, 첫 delta 3.61초, result 4.86초; submitTurnStream 19번째 턴: delta 46개, 첫 delta 2.78초, result 4.11초; submitTurnStream 20번째 턴: delta 42개, 첫 delta 3.61초, result 4.85초; submitTurnStream 21번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 22번째 턴: delta 42개, 첫 delta 3.61초, result 4.85초; submitTurnStream 23번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 24번째 턴: delta 42개, 첫 delta 3.60초, result 4.85초; submitTurnStream 25번째 턴: delta 46개, 첫 delta 2.80초, result 4.12초; submitTurnStream 26번째 턴: delta 42개, 첫 delta 3.62초, result 4.86초; submitTurnStream 27번째 턴: delta 46개, 첫 delta 2.78초, result 4.10초; submitTurnStream 28번째 턴: delta 42개, 첫 delta 3.60초, result 4.85초; submitTurnStream 29번째 턴: delta 46개, 첫 delta 2.79초, result 4.11초; submitTurnStream 30번째 턴: delta 42개, 첫 delta 3.61초, result 4.85초; submitTurnStream 30번 모두 200·SSE·계약 일치(성공 30, 실패 신호 0, 한도 3에 닿아 건너뜀 0); endSession 200(ENDED_PARTIAL); 스트림 31건 합계: delta 1381개, 첫 delta 가장 빠른 값 0.21초 [StepFailure: product 모드는 문진이 끝까지 가야 한다(ENDED_COMPLETE). 실제 ENDED_PARTIAL] |
| ⑥ 결과 조회·확인 표시(의사) | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |
| ⑧ 직원 호출 알림 | 건너뜀 | 0.0 |  [앞 단계가 실패했다] |

## 실행 2026-11-23T04:36:27+00:00 · product · 실패

비고(헤드, 기록을 옮기며 더함): 첫 임대 서버의 탐색 실행. 리포 리비전 3598873 의 작업 트리에 커밋 전 변경이 있었다(판정 변경은 뒤에 86d68a6, nginx 취약점 임시 무시 목록은 커밋하지 않음). 환경 문제와 원인은 NoneCommit/TODO.md 의 I1~I6

- 모드: product
- 걸린 시간: 56초
- compose 프로젝트: openit-e2e-5e0332
- 프로파일·기반 모델: rtx4090-24g · Qwen/Qwen3-8B
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| 준비·설치 | 실패 | 0.0 |  [StepFailure: ./deploy bootstrap rc=1 330eb885e04de130b768d6db4e10469e2311879c7e5c699f6d2d8a1c74 Pulled   Image postgres:16.10-bookworm@sha256:38471f330eb885e04de130b768d6db4e10469e2311879c7e5c699f6d2d8a1c74 Pulled   Container openit-e2e-5e0332-registry-store-1 Running   Container openit-e2e-5e0332-step-ca-1 Running   Container openit-e2e-5e0332-registry-1 Running   Network openit-e2e-5e0332_model-runtime-area Creating   Volume openit-e2e-5e0332_alertmanager-data Creating   Volume openit-e2e-5e0332_ingress-certs Creating   Network openit-e2e-5e0332_admin-console-area Creating   Volume openit-e2e-5e0332_kiosk-frontend-certs Creating   Network openit-e2e-5e0332_survey-service-area Creating   Volume openit-e2e-5e0332_model-runtime-data Creating   Volume openit-e2e-5e0332_postgres-data Creating   Container openit-e2e-5e0332-pushgateway-1 Creating   Volume openit-e2e-5e0332_model-runtime-certs Creating   Volume openit-e2e-5e0332_admin-console-certs Creating   Volume openit-e2e-5e0332_prometheus-data Creating   Volume openit-e2e-5e0332_survey-db-data Creating   Volume openit-e2e-5e0332_survey-service-certs Creating   Container openit-e2e-5e0332-blackbox-1 Creating   Network openit-e2e-5e0332_kiosk-frontend-area Creating   Volume openit-e2e-5e0332_alertmanager-data Created   Container openit-e2e-5e0332-alertmanager-1 Creating   Volume openit-e2e-5e0332_ingress-certs Created   Volume openit-e2e-5e0332_postgres-data Created   Container openit-e2e-5e0332-postgres-1 Creating   Volume ope] |

## 실행 2026-11-10T18:01:59+00:00 · pipeline · 통과

- 모드: pipeline
- 걸린 시간: 258초
- GPU: NVIDIA GeForce RTX 4070 SUPER, 12282 MiB, 591.86
- 프로파일·기반 모델: gpu-12g · Qwen/Qwen3-1.7B
- 추론 엔진: vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e (크기 인자: --gpu-memory-utilization 0.7 --max-model-len 8192)
- 어댑터: 중립 어댑터(B=0, rank 16, 내용 해시 LORA_A 5da95e2668eb, LORA_B 8f5d6f5ca7ed)
- 기반 모델 가중치 볼륨: 재사용
- Docker 엔진: 28.5.1
- 영역 이미지 리비전: survey-service dabd173d6368, model-runtime f446bb1a596e, web-admin-console dabd173d6368, web-kiosk-frontend dabd173d6368
- 리포 리비전: f446bb1
- compose 프로젝트: openit-e2e-565eff
- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개

| 단계 | 결과 | 시간(초) | 확인한 것 |
|---|---|---:|---|
| ① 어댑터 게시(package-publish) | 통과 | 13.8 | 패키지 digest sha256:d4a62ecdce9d…가 레지스트리에 올라감; 평가 보고서 지표 value_precision, value_recall, precision_match_rate, next_item_accuracy, schema_valid_raw 2개, semantic_violation_rate 11개, length_p95_seconds, ungrounded_number_rate, forbidden_expression_rate, response_call_p95_seconds(총 21개, 점검용 작은 평가 집합) |
| ② 패키지 조회·활성화·적재(승인자) | 통과 | 3.5 | getModelPackage 200(기반 모델 Qwen/Qwen3-1.7B, 어댑터 2개, 모델 입출력 model-io-v2); listModelPackages 에 게시한 패키지가 있다; activateModelPackage 202; getModelStatus READY(계약 적재 상한 180초 안), 활성 패키지가 게시한 것이다 |
| ③ 문항 세트 올리기·활성화(작성자) | 통과 | 0.5 | uploadQuestionSet 201(문항 31개, 칸 52개, 버전 1); activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다 |
| ④ 시작 코드 발급(직원) | 통과 | 0.0 | issueStartCode 201(6자리 코드, 만료 시각 있음) |
| ⑤ 키오스크 세션(기기 인증서) | 통과 | 22.8 | startSession 201(ACTIVE, 모델이 만든 첫 문장 24자, 지금 문항 Q1.D01); submitTurn 6번 모두 200·계약 일치(성공 0, 실패 신호 6); 실패 신호 EXTRACTION_UNAVAILABLE 6건 모두 세션 상태·지금 문항 불변; endSession 200(ENDED_PARTIAL) |
| ⑥ 결과 조회·확인 표시(의사) | 통과 | 0.1 | listResults·getResult 200(상태 ENDED_PARTIAL, 저장된 답 0개, 빈칸 30개); acknowledgeResult 200, 결과에 확인한 의사와 시각이 남았다 |
| ⑦ 결과·FHIR 당겨 가기(병원 시스템) | 통과 | 0.1 | 기계 토큰(result-reader)으로 listResults·getResult 200, 의사가 본 결과와 같다. getResultFhir 200(QuestionnaireResponse, status stopped) |
| ⑧ 직원 호출 알림 | 통과 | 0.3 | requestStaffCall 201(CALL_STAFF), 직원의 listStaffAlerts 에 알림이 있고 세션이 PAUSED(STAFF_CALL)다 |

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
