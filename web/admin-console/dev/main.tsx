// 개발 서버 진입점(영역 ADR 0011). 가짜 survey-service·model-runtime·oauth2-proxy 를 MSW 브라우저 워커로 띄운 뒤 원래 진입점을 부른다.
// 시험과 같은 가짜(tests/fakes/backend.ts)라 계약 타입과 어긋나면 tsc 가 막는다. 새로 고침하면 가짜 상태도 처음으로 돌아간다.
// 역할: 기본은 모든 역할이다. 주소에 ?roles=staff,clinician 처럼 주면 그 역할로 본다(메뉴·권한 화면 확인용).
import { http, HttpResponse } from "msw";
import { setupWorker } from "msw/browser";

import { createFakeBackend } from "../tests/fakes/backend";

const roles = new URLSearchParams(globalThis.location.search).get("roles");
const backend = createFakeBackend(roles === null ? {} : { roles: roles.split(",").filter((r) => r !== "") });

await setupWorker(
  http.all(/\/(v1|oauth2)\//, async ({ request }) => {
    const url = new URL(request.url);
    const text = request.method === "GET" || request.method === "HEAD" ? "" : await request.text();
    const response = backend.handle({
      method: request.method,
      path: decodeURIComponent(url.pathname),
      query: url.searchParams,
      headers: request.headers,
      body: text === "" ? undefined : (JSON.parse(text) as unknown),
    });
    return new HttpResponse(response.body, { status: response.status, headers: { "content-type": response.contentType } });
  }),
).start({
  serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
  onUnhandledFrame: "bypass",
});
await import("../src/main");
