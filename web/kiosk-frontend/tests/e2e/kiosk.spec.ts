// 브라우저 시나리오: 키오스크 시작 → 턴 → 종료(브리프의 끝 조건). survey-service 는 계약 타입으로 만든 가짜(page.route)다(ADR 0012).
import { expect, test, type Page } from "@playwright/test";

import { routeFake } from "../fakes/playwright";
import { stubSpeech, type SpeechStub } from "./speech-stub";
import { CODES, createFakeSurveyService, type FakeSurveyService } from "../fakes/survey-service";

async function open(page: Page, fake: FakeSurveyService, speech: SpeechStub = { available: false }) {
  await stubSpeech(page, speech);
  await routeFake(page, fake);
  await page.goto("/kiosk/");
  await expect(page.getByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeVisible();
}

async function enterCode(page: Page, code: string) {
  for (const digit of code) await page.getByRole("button", { name: digit, exact: true }).click();
  await page.getByRole("button", { name: "시작하기" }).click();
}

async function say(page: Page, text: string) {
  await page.getByRole("textbox", { name: "답변" }).fill(text);
  await page.getByRole("button", { name: "보내기" }).click();
}

test("시작 코드 → 문진 세 문항 → 끝 화면 → 처음으로", async ({ page, baseURL }) => {
  const fake = createFakeSurveyService();
  const outside: string[] = [];
  const own = new URL(baseURL ?? "http://127.0.0.1").origin;
  page.on("request", (request) => {
    if (!request.url().startsWith("data:") && new URL(request.url()).origin !== own) outside.push(request.url());
  });
  await open(page, fake);
  await enterCode(page, CODES.ok);
  await expect(page.getByText(/문진을 시작하겠습니다/)).toBeVisible();
  await say(page, "안 피웁니다");
  await expect(page.getByText(/일주일에 술을 몇 번/)).toBeVisible();
  await say(page, "한 번이요");
  await expect(page.getByText(/운동은 일주일에/)).toBeVisible();
  await say(page, "두 번이요");
  await expect(page.getByRole("heading", { name: /문진이 끝났습니다/ })).toBeVisible();
  await page.getByRole("button", { name: "처음으로" }).click();
  await expect(page.getByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeVisible();
  // 외부로 나가는 요청이 없다(이 출처 밖으로 보내지 않는다, UD-12)
  expect(outside).toEqual([]);
});

test("틀린 코드는 알리고 다시 입력하게 하며, 이어서 맞는 코드로 시작한다", async ({ page }) => {
  await open(page, createFakeSurveyService());
  await enterCode(page, CODES.invalid);
  await expect(page.getByRole("alert")).toContainText("코드가 맞지 않습니다");
  await enterCode(page, CODES.ok);
  await expect(page.getByRole("textbox", { name: "답변" })).toBeVisible();
});

test("실패 신호는 다시 말하라고 알리고 같은 글을 남긴다", async ({ page }) => {
  await open(page, createFakeSurveyService());
  await enterCode(page, CODES.ok);
  await say(page, "실패 시키기");
  await expect(page.getByRole("alert")).toContainText("잘 이해하지 못했습니다");
  await expect(page.getByRole("textbox", { name: "답변" })).toHaveValue("실패 시키기");
});

test("직원 부르기 → 멈춤 화면 → 직원이 풀면 이어서 진행", async ({ page }) => {
  const fake = createFakeSurveyService();
  await open(page, fake);
  await enterCode(page, CODES.ok);
  await page.getByRole("button", { name: "직원 부르기" }).click();
  await expect(page.getByRole("heading", { name: "잠시 기다려 주세요" })).toBeVisible();
  fake.resume("직원이 다녀갔습니다. 이어서 답해 주세요.");
  // 계약 SessionStatePollSeconds(2초) 뒤의 읽기로 풀림을 안다. 시험 제한(5초 기본)보다 짧다
  await expect(page.getByText("직원이 다녀갔습니다. 이어서 답해 주세요.")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "답변" })).toBeVisible();
});

test("문진 끝내기는 확인 뒤 중간 종료 안내를 보인다", async ({ page }) => {
  await open(page, createFakeSurveyService());
  await enterCode(page, CODES.ok);
  await page.getByRole("button", { name: "문진 끝내기" }).click();
  await page.getByRole("button", { name: "끝내기", exact: true }).click();
  await expect(page.getByRole("heading", { name: /저장되었습니다/ })).toBeVisible();
});

test("고령자용 크기: 키패드 버튼은 높이 64px 이상, 글자는 24px 이상", async ({ page }) => {
  await open(page, createFakeSurveyService());
  for (const digit of ["0", "5", "9"]) {
    const box = await page.getByRole("button", { name: digit, exact: true }).boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(64);
    expect(box?.width ?? 0).toBeGreaterThanOrEqual(64);
  }
  const size = await page.getByRole("button", { name: "시작하기" }).evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  expect(size).toBeGreaterThanOrEqual(24);
});

test("기기 안 음성 인식이 되면 말하기로 답을 받아 적고 보낼 수 있다", async ({ page }) => {
  await open(page, createFakeSurveyService(), { available: true, transcript: "하루에 한 갑 피웁니다" });
  await enterCode(page, CODES.ok);
  await page.getByRole("button", { name: "말하기" }).click();
  await expect(page.getByRole("textbox", { name: "답변" })).toHaveValue("하루에 한 갑 피웁니다");
  expect(await page.evaluate(() => (window as unknown as { __processLocally: boolean }).__processLocally)).toBe(true);
  await page.getByRole("button", { name: "보내기" }).click();
  await expect(page.getByText(/일주일에 술을 몇 번/)).toBeVisible();
});

test("기기 안 음성 인식이 안 되면 말하기 버튼 없이 글자 입력만 쓴다(외부 전송 없음)", async ({ page }) => {
  await open(page, createFakeSurveyService(), { available: false });
  await enterCode(page, CODES.ok);
  await expect(page.getByRole("textbox", { name: "답변" })).toBeVisible();
  await expect(page.getByRole("button", { name: "말하기" })).toHaveCount(0);
});

test("없는 경로도 처음 화면으로 간다(SPA 라우팅)", async ({ page }) => {
  await stubSpeech(page, { available: false });
  await routeFake(page, createFakeSurveyService());
  await page.goto("/kiosk/talk");
  await expect(page.getByRole("heading", { name: "시작 코드를 입력해 주세요" })).toBeVisible();
});

test("보안 헤더: 연결은 같은 출처로만 허용한다(CSP connect-src 'self')", async ({ page }) => {
  await stubSpeech(page, { available: false });
  const response = await page.goto("/kiosk/");
  expect(response?.headers()["content-security-policy"]).toContain("connect-src 'self'");
});
