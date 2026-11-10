// 기기 안 음성 합성(Web Speech API). 문장을 읽을 때도 외부로 보내지 않는다(UD-12).
// 왜 localService 만: 원격 목소리(localService=false)는 글을 서버로 보내 소리를 받아 온다(MDN SpeechSynthesisVoice.localService).
// 기기 안 한국어 목소리가 없으면 읽지 않고 글자만 보인다.
import { useCallback, useEffect, useState } from "react";

export function pickLocalVoice(voices: readonly SpeechSynthesisVoice[], lang: string): SpeechSynthesisVoice | undefined {
  const primary = lang.split("-")[0] ?? lang;
  return voices.find((v) => v.localService && v.lang === lang) ?? voices.find((v) => v.localService && v.lang.split(/[-_]/)[0] === primary);
}

export function useSpeechSynthesis(lang: string) {
  const [voice, setVoice] = useState<SpeechSynthesisVoice | undefined>(undefined);

  useEffect(() => {
    if (typeof globalThis.speechSynthesis === "undefined") return;
    const synth = globalThis.speechSynthesis;
    const refresh = () => {
      setVoice(pickLocalVoice(synth.getVoices(), lang));
    };
    refresh();
    // 왜 voiceschanged: 목소리 목록은 비동기로 채워지는 브라우저가 있다(MDN)
    synth.addEventListener("voiceschanged", refresh);
    return () => {
      synth.removeEventListener("voiceschanged", refresh);
      synth.cancel();
    };
  }, [lang]);

  const speak = useCallback(
    (text: string) => {
      if (voice === undefined) return;
      const synth = globalThis.speechSynthesis;
      synth.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = voice;
      utterance.lang = voice.lang;
      synth.speak(utterance);
    },
    [voice],
  );

  const cancel = useCallback(() => {
    if (typeof globalThis.speechSynthesis !== "undefined") globalThis.speechSynthesis.cancel();
  }, []);

  return { available: voice !== undefined, speak, cancel };
}
