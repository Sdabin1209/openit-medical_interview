// 가짜 survey-service 를 Playwright 의 page.route 에 연결한다(ADR 0012). 브라우저 시험용.
import type { Page } from "@playwright/test";

import type { FakeSurveyService } from "./survey-service";

export async function routeFake(page: Page, fake: FakeSurveyService): Promise<void> {
  await page.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const raw = request.postData();
    const result = fake.handle({ method: request.method(), path: url.pathname, ...(raw === null ? {} : { body: JSON.parse(raw) as unknown }) });
    await route.fulfill({ status: result.status, headers: result.headers ?? {}, body: JSON.stringify(result.body) });
  });
}
