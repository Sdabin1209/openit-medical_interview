import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { deviceRecognitionAvailable, pickLocalVoice, useSpeechRecognition, useSpeechSynthesis } from "../../src/components/speech";

afterEach(() => {
  vi.unstubAllGlobals();
});

const voice = (lang: string, localService: boolean, name = lang) => ({ lang, localService, name }) as SpeechSynthesisVoice;

describe("기기 안 음성 합성", () => {
  it("기기 안(localService) 한국어 목소리만 고른다", () => {
    expect(pickLocalVoice([voice("ko-KR", false, "원격"), voice("en-US", true)], "ko-KR")).toBeUndefined();
    expect(pickLocalVoice([voice("ko-KR", false, "원격"), voice("ko-KR", true, "내장")], "ko-KR")?.name).toBe("내장");
  });
  it("지역이 달라도 같은 언어의 기기 안 목소리를 쓴다", () => {
    expect(pickLocalVoice([voice("ko", true, "k")], "ko-KR")?.name).toBe("k");
  });
  it("기기 안 목소리가 없으면 읽지 않는다", () => {
    const speakFn = vi.fn();
    vi.stubGlobal("speechSynthesis", { getVoices: () => [voice("ko-KR", false)], addEventListener: vi.fn(), removeEventListener: vi.fn(), cancel: vi.fn(), speak: speakFn });
    const { result } = renderHook(() => useSpeechSynthesis("ko-KR"));
    expect(result.current.available).toBe(false);
    act(() => {
      result.current.speak("안녕하세요");
    });
    expect(speakFn).not.toHaveBeenCalled();
  });
  it("기기 안 목소리가 있으면 그 목소리로 읽는다", () => {
    const speakFn = vi.fn();
    const local = voice("ko-KR", true);
    vi.stubGlobal("speechSynthesis", { getVoices: () => [local], addEventListener: vi.fn(), removeEventListener: vi.fn(), cancel: vi.fn(), speak: speakFn });
    vi.stubGlobal("SpeechSynthesisUtterance", class { constructor(public text: string) {} voice?: SpeechSynthesisVoice; lang = "" });
    const { result } = renderHook(() => useSpeechSynthesis("ko-KR"));
    act(() => {
      result.current.speak("안녕하세요");
    });
    expect(speakFn).toHaveBeenCalledTimes(1);
    expect((speakFn.mock.calls[0]?.[0] as { voice: unknown }).voice).toBe(local);
  });
  it("speechSynthesis 가 없는 브라우저에서도 죽지 않는다", () => {
    vi.stubGlobal("speechSynthesis", undefined);
    const { result } = renderHook(() => useSpeechSynthesis("ko-KR"));
    expect(result.current.available).toBe(false);
  });
});

describe("기기 안 음성 인식", () => {
  it("인식을 지원하지 않으면 쓸 수 없다", async () => {
    expect(await deviceRecognitionAvailable("ko-KR")).toBe(false);
  });
  it("available 을 모르는 구현은 기기 안 처리를 확인할 수 없어 쓰지 않는다", async () => {
    vi.stubGlobal("SpeechRecognition", function Plain() {});
    expect(await deviceRecognitionAvailable("ko-KR")).toBe(false);
  });
  it("기기 안 처리가 available 일 때만 쓴다(processLocally 로 물어본다)", async () => {
    const available = vi.fn(() => Promise.resolve("available"));
    vi.stubGlobal("SpeechRecognition", Object.assign(function Fake() {}, { available }));
    expect(await deviceRecognitionAvailable("ko-KR")).toBe(true);
    expect(available).toHaveBeenCalledWith({ langs: ["ko-KR"], processLocally: true });
    vi.stubGlobal("SpeechRecognition", Object.assign(function Fake() {}, { available: () => Promise.resolve("downloadable") }));
    expect(await deviceRecognitionAvailable("ko-KR")).toBe(false);
  });
  it("시작하면 processLocally 를 켜고, 끝난 글을 알린다", async () => {
    const instances: { processLocally?: boolean; onresult?: (e: unknown) => void; onend?: () => void }[] = [];
    vi.stubGlobal(
      "SpeechRecognition",
      class {
        static available = () => Promise.resolve("available");
        processLocally = false;
        onresult?: (e: unknown) => void;
        onend?: () => void;
        constructor() {
          instances.push(this);
        }
        start() {}
        stop() {}
        abort() {}
      },
    );
    const onFinalText = vi.fn();
    const { result } = renderHook(() => useSpeechRecognition({ lang: "ko-KR", onFinalText }));
    await waitFor(() => { expect(result.current.state).toBe("ready"); });
    act(() => {
      result.current.start();
    });
    expect(result.current.state).toBe("listening");
    expect(instances[0]?.processLocally).toBe(true);
    act(() => {
      instances[0]?.onresult?.({ resultIndex: 0, results: [Object.assign([{ transcript: "하루 한 갑" }], { isFinal: true })] });
    });
    expect(onFinalText).toHaveBeenCalledWith("하루 한 갑");
    act(() => {
      instances[0]?.onend?.();
    });
    expect(result.current.state).toBe("ready");
  });
});
