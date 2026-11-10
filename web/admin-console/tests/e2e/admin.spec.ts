import { expect, test, type Page } from "@playwright/test";

import { createFakeBackend, DIGESTS, type FakeOptions } from "../fakes/backend";

// 서버(survey-service, model-runtime)와 oauth2-proxy 는 없다. 계약 타입으로 만든 가짜가 page.route 로 답한다(ADR 0012).
async function withBackend(page: Page, options: FakeOptions) {
  const backend = createFakeBackend(options);
  await page.route(
    (url) => url.pathname.startsWith("/v1/") || url.pathname.startsWith("/oauth2/"),
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const text = request.postData();
      const response = backend.handle({
        method: request.method(),
        path: decodeURIComponent(url.pathname),
        query: url.searchParams,
        headers: new Headers(request.headers()),
        body: text === null || text === "" ? undefined : (JSON.parse(text) as unknown),
      });
      await route.fulfill({ status: response.status, contentType: response.contentType, body: response.body });
    },
  );
  return backend;
}

test("시작 코드 발급 → 결과 확인 → 모델 활성화 승인", async ({ page }) => {
  const backend = await withBackend(page, { roles: ["staff", "clinician", "release-approver"] });
  // 가짜 시계(Playwright Clock API): 적재 중 재읽기 간격(3초)은 실제로 기다리지 않고 fastForward 로 넘긴다
  await page.clock.install();
  await page.goto("/console/");

  // 1. 직원이 시작 코드를 발급한다(첫 화면). 6자리 숫자가 보이고 QR 은 없다
  await expect(page.getByRole("heading", { name: "시작 코드 발급" })).toBeVisible();
  await page.getByLabel("대상자 참조값").fill("subj-000123");
  await page.getByLabel("문진표").selectOption("national-health");
  await page.getByRole("button", { name: "코드 발급" }).click();
  await expect(page.getByRole("img", { name: "시작 코드 4 8 2 9 1 0" })).toBeVisible();
  expect(backend.calls.find((c) => c.path === "/v1/start-codes")?.body).toEqual({ subject_ref: "subj-000123", questionnaire_id: "national-health" });

  // 2. 의사가 결과를 열어 확인 표시를 한다
  await page.getByRole("link", { name: "결과" }).click();
  await page.getByRole("link", { name: "subj-000123 결과 보기" }).click();
  await expect(page.getByRole("heading", { name: "문진 결과 subj-000123" })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "Q1.answer" })).toBeVisible();
  await page.getByRole("button", { name: "확인했음 표시" }).click();
  await expect(page.getByRole("status")).toContainText("doctor-1");
  await expect(page.getByRole("button", { name: "확인했음 표시" })).toHaveCount(0);

  // 3. 승인자가 평가 보고서를 보고 활성화를 승인한다
  await page.getByRole("link", { name: "모델 패키지" }).click();
  await expect(page.getByRole("status").first()).toContainText("준비됨");
  await expect(page.getByRole("row", { name: new RegExp(`${DIGESTS.candidate}.*비활성`) })).toBeVisible();
  await page.getByRole("button", { name: `${DIGESTS.candidate} 평가 보고서 보기` }).click();
  await expect(page.getByRole("row", { name: /next_item_accuracy/ })).toBeVisible();
  await page.getByRole("button", { name: "이 패키지 활성화 승인" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "승인" }).click();
  await expect(dialog.getByText("사유를 입력한다")).toBeVisible();
  await dialog.getByLabel("사유").fill("평가 보고서 확인");
  await dialog.getByRole("button", { name: "승인" }).click();
  await expect(dialog).toHaveCount(0);
  expect(backend.calls.find((c) => c.path === "/v1/model-activations")?.body).toEqual({ package_digest: DIGESTS.candidate, reason: "평가 보고서 확인" });
  // 적재 중이라고 보인 뒤 재읽기 간격만큼 시계를 넘기면 가짜는 다음 읽기에서 적재를 끝낸다. 활성 패키지가 승인한 것으로 바뀐다
  await expect(page.getByRole("status").first()).toContainText("적재 중");
  await page.clock.fastForward(3000);
  await expect(page.getByRole("status").first()).toContainText("준비됨");
  await expect(page.getByText(DIGESTS.candidate).first()).toBeVisible();
  // 목록의 활성 표시가 승인한 패키지로 옮겨진다
  await expect(page.getByRole("row", { name: new RegExp(`${DIGESTS.candidate}.*\\s활성`) })).toBeVisible();
});

test("직원 알림: 스트림으로 새 위험 알림이 뜨고 정지 해제는 확인 뒤에 보낸다", async ({ page }) => {
  const backend = await withBackend(page, { roles: ["staff"] });
  await page.goto("/console/alerts");
  await expect(page.getByText("기기 kiosk-02")).toBeVisible(); // 스트림이 준 RISK 알림
  await expect(page.getByText("기기 kiosk-01")).toBeVisible(); // 목록이 준 직원 호출
  // 가짜 스트림은 이벤트 하나를 주고 끝나므로 연결 상태 문구는 여기서 보지 않는다(단위 시험이 본다)
  await page.getByRole("listitem").filter({ hasText: "kiosk-02" }).getByRole("button", { name: "정지 해제" }).click();
  await page.keyboard.press("Escape");
  expect(backend.calls.some((c) => c.path.endsWith("/intervention"))).toBe(false);
  await page.getByRole("listitem").filter({ hasText: "kiosk-02" }).getByRole("button", { name: "정지 해제" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "재개" }).click();
  await expect.poll(() => backend.calls.find((c) => c.path.endsWith("/intervention"))?.body).toEqual({ action: "RESUME" });
});

test("역할에 없는 화면은 메뉴에도 없고 주소로 들어가도 열리지 않는다", async ({ page }) => {
  await withBackend(page, { roles: ["author"] });
  await page.goto("/console/release");
  await expect(page.getByText("이 화면을 볼 권한이 없다")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "화면 메뉴" }).getByRole("link")).toHaveText(["문항 세트"]);
});

test("로그인이 끝나면(401) oauth2-proxy 로그인으로 보낸다", async ({ page }) => {
  let started = "";
  await page.route("**/oauth2/userinfo", (route) => route.fulfill({ status: 401, body: "" }));
  await page.route("**/oauth2/start**", (route) => {
    started = new URL(route.request().url()).search;
    return route.fulfill({ status: 200, contentType: "text/html", body: "로그인" });
  });
  await page.goto("/console/results");
  await expect.poll(() => started).toBe("?rd=%2Fconsole%2Fresults");
});

test("문항 세트 올리기와 실패 사례 검토", async ({ page }) => {
  const backend = await withBackend(page, { roles: ["author", "reviewer"] });
  await page.goto("/console/question-sets");
  const upload = { questionnaire_id: "nh2", runtime_contract_version: 1, content: { title: "새 세트", bank: { items: [] }, flow: { start_item: "Q1", rules: [] } } };
  await page.getByLabel("문항 세트 파일(JSON)").setInputFiles({ name: "q.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(upload)) });
  await expect(page.getByText(/새 세트 버전 2/)).toBeVisible();
  await expect(page.getByRole("button", { name: "national-health 버전 1 활성화" })).toBeDisabled(); // 이미 활성인 버전
  await page.getByRole("button", { name: "nh2 버전 2 활성화" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "활성화" }).click();
  await expect(page.getByText(/활성 버전을/)).toBeVisible();
  await expect(page.getByRole("button", { name: "nh2 버전 2 활성화" })).toBeDisabled();

  await page.getByRole("link", { name: "실패 사례" }).click();
  await page.getByRole("link", { name: /Q7_1/ }).click();
  await expect(page.getByText("가끔 한잔 정도").first()).toBeVisible();
  await page.getByLabel("검토 결과").selectOption("CONFIRMED");
  await page.getByRole("button", { name: "검토 결과 게시" }).click();
  await expect(page.getByText("검토 결과를 게시했다")).toBeVisible();
  expect(backend.calls.find((c) => c.path.endsWith("/reviews"))?.body).toMatchObject({ base_case_version: 1, review_status: "CONFIRMED" });
});

test("없는 경로도 화면이 열린다(SPA 라우팅)", async ({ page }) => {
  await withBackend(page, { roles: ["staff"] });
  await page.goto("/console/nowhere");
  await expect(page.getByText("없는 화면이다")).toBeVisible();
});
