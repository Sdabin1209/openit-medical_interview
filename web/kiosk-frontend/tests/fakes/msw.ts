// 가짜 survey-service 를 MSW 의 Node 쪽 서버에 연결한다. 단위·계약 시험용. 처리기는 msw-handlers.ts(개발 서버와 공유).
import { setupServer } from "msw/node";

import { handlersFor } from "./msw-handlers";
import type { FakeSurveyService } from "./survey-service";

export function mswServerFor(fake: FakeSurveyService) {
  return setupServer(...handlersFor(fake));
}
