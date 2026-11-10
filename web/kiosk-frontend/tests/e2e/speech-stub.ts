// 브라우저의 Web Speech API 를 시험용 대역으로 바꾼다. 왜: Playwright 공식 이미지(headless Chromium)에서는
// SpeechRecognition.available() 를 부르면 렌더러가 죽는다(이 영역에서 재현·확인, 영역 ADR 0004). 그래서 실제 소리와 모델은 시험하지 않고
// "기기 안 처리가 가능하다고 답하는 브라우저"와 "가능하지 않다고 답하는 브라우저"의 두 경우로 우리 코드를 시험한다.
import type { Page } from "@playwright/test";

export type SpeechStub = { available: boolean; transcript?: string };

export async function stubSpeech(page: Page, stub: SpeechStub): Promise<void> {
  await page.addInitScript((config: SpeechStub) => {
    class FakeRecognition {
      static available(): Promise<string> {
        return Promise.resolve(config.available ? "available" : "unavailable");
      }
      processLocally = false;
      lang = "";
      interimResults = false;
      continuous = false;
      onresult: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;
      start(): void {
        // 왜 processLocally 를 기록: 화면이 기기 안 처리를 요구했는지 시험이 본다
        (window as unknown as { __processLocally: boolean }).__processLocally = this.processLocally;
        setTimeout(() => {
          const result = Object.assign([{ transcript: config.transcript ?? "" }], { isFinal: true });
          this.onresult?.({ resultIndex: 0, results: [result] });
          this.onend?.();
        }, 50);
      }
      stop(): void {}
      abort(): void {}
    }
    Object.assign(window, { SpeechRecognition: FakeRecognition, webkitSpeechRecognition: FakeRecognition });
  }, stub);
}
