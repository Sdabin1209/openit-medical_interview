// 계약이 정한 값(영역 사이 값)을 이 화면이 쓰는 이름으로 모았다. 값은 계약의 const·pattern·maxLength 와 같아야 하고,
// tests/contract/limits.test.ts 가 contracts/components.yaml 과 대조한다(계약이 바뀌면 시험이 깨진다).
export const START_CODE_LENGTH = 6; // StartCodeValue pattern ^[0-9]{6}$
export const UTTERANCE_MAX_LENGTH = 300; // UtteranceText maxLength
export const KIOSK_IDLE_RESET_SECONDS = 60; // TimeBudgetTable.kiosk_idle_reset (UD-17)
export const KIOSK_REQUEST_LIMIT_SECONDS = 60; // kiosk_request
export const KIOSK_RETRY_BUDGET_SECONDS = 120; // kiosk_retry_budget
export const KIOSK_PROGRESS_NOTICE_SECONDS = 1; // kiosk_progress_notice
export const SESSION_STATE_POLL_SECONDS = 2; // session_state_poll

// 아래는 계약 밖, 이 화면 안의 값이다(영역 ADR 0004).
/** 유휴 경고를 보이는 시간. WCAG 2.1 SC 2.2.1 의 '20초 이상' 에서 왔다 */
export const IDLE_WARNING_SECONDS = 20;
/** Retry-After 가 없는 재시도 간격. 측정하지 않은 값이며 재시도 총 시간은 계약 예산(120초)이 막는다 */
export const FALLBACK_RETRY_SECONDS = 2;
/** 음성 인식·합성 언어(BCP 47) */
export const SPEECH_LANG = "ko-KR";
