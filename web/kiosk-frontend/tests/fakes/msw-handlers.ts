// 가짜 survey-service 를 MSW(Mock Service Worker) 처리기로 만든다. Node(tests/fakes/msw.ts)와 브라우저(dev/main.tsx)가 함께 쓴다.
// 왜 따로: msw/node 는 브라우저에서 불러올 수 없어 처리기만 이 파일에 둔다.
import { http, HttpResponse } from "msw";

import type { FakeSurveyService } from "./survey-service";

export function handlersFor(fake: FakeSurveyService) {
  return [
    http.all("*/v1/*", async ({ request }) => {
      const url = new URL(request.url);
      const body: unknown = request.method === "POST" && request.headers.get("content-type")?.includes("json") === true ? await request.json() : undefined;
      const result = fake.handle({ method: request.method, path: url.pathname, ...(body === undefined ? {} : { body }) });
      if (result.chunks !== undefined) {
        const encoder = new TextEncoder();
        const chunks = result.chunks;
        return new HttpResponse(new ReadableStream({ start(controller) { for (const c of chunks) controller.enqueue(encoder.encode(c)); controller.close(); } }), { status: result.status, headers: result.headers ?? {} });
      }
      return HttpResponse.json(result.body as Record<string, unknown>, { status: result.status, headers: result.headers ?? {} });
    }),
  ];
}
