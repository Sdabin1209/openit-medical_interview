import { expect, test } from "@playwright/test";

// 브라우저로 실제 화면을 본다. 서버 API 는 없으므로 /readyz 는 가로채서 계약대로 답한다.
test("준비 상태를 보이고, 이름을 추가하면 표에 나타난다", async ({ page }) => {
  await page.route("**/readyz", (route) =>
    route.fulfill({ json: { status: "pass", service: "platform" } }),
  );
  await page.goto("/");
  await expect(page.getByRole("status")).toHaveText("준비됨");
  await page.getByLabel("이름").fill("다빈");
  await page.getByRole("button", { name: "추가" }).click();
  await page.getByRole("button", { name: "확인" }).click();
  await expect(page.getByRole("cell", { name: "다빈" })).toBeVisible();
});

test("준비 안 됨이면 실패한 점검 이름을 보인다", async ({ page }) => {
  await page.route("**/readyz", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/problem+json",
      body: JSON.stringify({ type: "about:blank", title: "의존이 준비되지 않았다", status: 503, detail: "준비되지 않은 점검: database" }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("database");
});

test("없는 경로도 화면이 열린다(SPA 라우팅)", async ({ page }) => {
  await page.route("**/readyz", (route) => route.fulfill({ json: { status: "pass", service: "platform" } }));
  await page.goto("/about");
  await expect(page.getByText("템플릿 예시 화면")).toBeVisible();
});
