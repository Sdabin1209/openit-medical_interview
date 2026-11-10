// 가짜 survey-service 를 MSW(Mock Service Worker, Node 쪽)에 연결한다. 단위·계약 시험용.
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { FakeSurveyService } from "./survey-service";

export function mswServerFor(fake: FakeSurveyService) {
  return setupServer(
    http.all("*/v1/*", async ({ request }) => {
      const url = new URL(request.url);
      const body: unknown = request.method === "POST" && request.headers.get("content-type")?.includes("json") === true ? await request.json() : undefined;
      const result = fake.handle({ method: request.method, path: url.pathname, ...(body === undefined ? {} : { body }) });
      return HttpResponse.json(result.body as Record<string, unknown>, { status: result.status, headers: result.headers ?? {} });
    }),
  );
}
