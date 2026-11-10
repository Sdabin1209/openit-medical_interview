// 기기 안 음성 인식(Web Speech API). 목소리를 외부로 보내지 않는다(UD-12, D88 U3).
// 왜 processLocally: 브라우저의 기본 음성 인식은 서버로 소리를 보내 처리하는 구현이 있다(MDN SpeechRecognition.processLocally).
// 기기 안 처리가 가능하다고 확인된 때만 쓰고, 확인하지 못하면 음성 입력을 끈다(글자 입력은 남는다). 언어 팩 내려받기(install)도 부르지 않는다.
import { useCallback, useEffect, useRef, useState } from "react";

/** 왜 선택 칸으로 다시 쓴다: lib.dom 의 타입은 항상 있다고 하지만 지원하지 않는 브라우저에는 없다 */
function recognitionCtor(): typeof SpeechRecognition | undefined {
  const scope = globalThis as { SpeechRecognition?: typeof SpeechRecognition; webkitSpeechRecognition?: typeof SpeechRecognition };
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition;
}

export type RecognitionState = "checking" | "unavailable" | "ready" | "listening";

export interface RecognitionOptions {
  /** BCP 47 언어 태그 */
  lang: string;
  /** 인식이 끝난 글(한 덩어리)이 나올 때마다 부른다 */
  onFinalText: (text: string) => void;
}

/** 이 브라우저에서 기기 안 음성 인식을 쓸 수 있는가. 시험에서 바꿔 끼울 수 있게 분리했다. */
export async function deviceRecognitionAvailable(lang: string): Promise<boolean> {
  const Ctor = recognitionCtor();
  // 왜 available 이 없으면 쓰지 않는다: 기기 안 처리인지 확인할 방법이 없는 구현은 외부 전송을 배제할 수 없다
  if (Ctor === undefined || typeof (Ctor as Partial<typeof SpeechRecognition>).available !== "function") return false;
  try {
    return (await Ctor.available({ langs: [lang], processLocally: true })) === "available";
  } catch {
    return false;
  }
}

export function useSpeechRecognition({ lang, onFinalText }: RecognitionOptions) {
  const [state, setState] = useState<RecognitionState>("checking");
  const [interim, setInterim] = useState("");
  const active = useRef<SpeechRecognition | null>(null);
  const onFinal = useRef(onFinalText);
  useEffect(() => {
    onFinal.current = onFinalText;
  });

  useEffect(() => {
    let cancelled = false;
    void deviceRecognitionAvailable(lang).then((ok) => {
      if (!cancelled) setState(ok ? "ready" : "unavailable");
    });
    return () => {
      cancelled = true;
      active.current?.abort();
    };
  }, [lang]);

  const start = useCallback(() => {
    const Ctor = recognitionCtor();
    if (Ctor === undefined) return;
    const recognition = new Ctor();
    recognition.lang = lang;
    recognition.processLocally = true;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      let finalText = "";
      let partial = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result?.[0]?.transcript ?? "";
        if (result?.isFinal === true) finalText += text;
        else partial += text;
      }
      setInterim(partial);
      if (finalText !== "") onFinal.current(finalText);
    };
    recognition.onend = () => {
      active.current = null;
      setInterim("");
      setState("ready");
    };
    recognition.onerror = () => {
      // 오류 뒤에도 onend 가 온다. 글자 입력은 그대로 쓸 수 있다
    };
    active.current = recognition;
    setState("listening");
    recognition.start();
  }, [lang]);

  const stop = useCallback(() => {
    active.current?.stop();
  }, []);

  return { state, interim, start, stop };
}
