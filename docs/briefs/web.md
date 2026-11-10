# kiosk-frontend, admin-console 브리프

공통 규칙은 [README](README.md). 컴포넌트는 [design.md 2절](../design.md). 기술은 ADR 0010~0012(React, Vite, TS strict, nginx-unprivileged, Playwright).

## kiosk-frontend(환자용)
- survey-service 의 키오스크 작업(listActiveQuestionnaires, startSession, submitTurn, endSession, getSessionState, requestStaffCall)을 부른다. 기기 인증은 기기 인증서(브라우저·OS 가 제시), 화면 코드는 신원을 다루지 않는다.
- 시작 코드: 숫자 키패드로 6자리 입력(QR 없음). 틀리면 다시 입력.
- 음성: 기기 안 음성 인식·합성(Web Speech API 등 기기 내장, 외부로 보내지 않음, UD-12).
- 유휴 60초 초기화(UD-17).
- 발화 300자 상한은 계약이 정한다. 화면은 계약 타입으로 막는다.

## admin-console(직원·의사·관리자)
- 로그인: oauth2-proxy + Keycloak(OIDC). 역할에 따라 화면을 보인다.
- 화면: 시작 코드 발급(6자리 표시), 직원 알림(SSE streamStaffAlerts, 웹 푸시 구독)과 개입, 결과 목록·상세·인쇄·확인 표시, 문항 세트 올리기·활성화, 실패 사례 검토, 모델 패키지(평가 보고서) 확인·활성화 승인·롤백(model-runtime 작업).

## 끝 조건(공통에 더해)
- 가짜 survey-service·model-runtime(계약 타입)으로 Playwright 시나리오: 키오스크 시작 → 턴 → 종료, 관리 화면 시작 코드 발급 → 결과 확인 → 모델 활성화 승인. rc=0.
