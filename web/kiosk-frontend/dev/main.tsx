// 개발 서버 진입점(영역 ADR 0009). 가짜 survey-service 를 MSW 브라우저 워커로 띄운 뒤 원래 진입점을 부른다.
// 시험과 같은 가짜(tests/fakes/survey-service.ts)라 계약 타입과 어긋나면 tsc 가 막는다. 새로 고침하면 가짜 상태도 처음으로 돌아간다.
// 시작 코드: 123456(정상), 000000(틀림), 111111(만료), 222222(사용됨), 333333(시도 한도). 답에 "실패"가 들어가면 턴 실패 신호를 본다.
import { setupWorker } from "msw/browser";

import { handlersFor } from "../tests/fakes/msw-handlers";
import { createFakeSurveyService } from "../tests/fakes/survey-service";

await setupWorker(...handlersFor(createFakeSurveyService())).start({
  serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
  onUnhandledFrame: "bypass",
});
await import("../src/main.tsx");
