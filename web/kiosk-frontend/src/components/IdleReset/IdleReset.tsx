// 유휴 초기화(idle_reset): 입력 없이 `seconds` 가 지나면 onIdle 을 부른다(계약 TimeBudgetTable.kiosk_idle_reset, UD-17).
// 끝나기 `warnSeconds` 전부터 남은 시간과 계속하기 버튼을 보인다. 왜: WCAG 2.1 SC 2.2.1(시간 조절 가능)은 시간 제한이 있으면
// 끝나기 전에 알리고 20초 이상 쉬운 동작으로 늘릴 수 있게 하라고 한다. 서버 호출은 하지 않는다(ADR 0003).
import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useRef, useState } from "react";

import "./IdleReset.css";

export interface IdleResetProps {
  /** 지켜보는 중인가. 응답을 기다리는 중이나 음성 입력 중처럼 환자가 입력할 수 없을 때는 끈다 */
  active: boolean;
  seconds: number;
  /** 0 이면 경고를 보이지 않고 조용히 초기화한다 */
  warnSeconds: number;
  onIdle: () => void;
}

/** 환자 입력으로 보는 이벤트. 눌러서 쓰는 화면이라 포인터·키·터치다 */
const ACTIVITY_EVENTS = ["pointerdown", "keydown", "touchstart"] as const;

function Timer({ seconds, warnSeconds, onIdle }: Omit<IdleResetProps, "active">) {
  // 왜 시작 시각과 1초 간격: 남은 시간은 시작 시각과 지금의 차이로 계산해 타이머가 늦게 불려도 어긋나지 않는다
  const [remaining, setRemaining] = useState<number | null>(null);
  const startedAt = useRef(0);
  const idleRef = useRef(onIdle);
  useEffect(() => {
    idleRef.current = onIdle;
  });

  useEffect(() => {
    startedAt.current = Date.now();
    const tick = setInterval(() => {
      const left = seconds - Math.floor((Date.now() - startedAt.current) / 1000);
      if (left <= 0) {
        clearInterval(tick);
        idleRef.current();
      } else {
        setRemaining(warnSeconds > 0 && left <= warnSeconds ? left : null);
      }
    }, 1000);
    const touch = () => {
      startedAt.current = Date.now();
      setRemaining(null);
    };
    for (const name of ACTIVITY_EVENTS) document.addEventListener(name, touch, true);
    return () => {
      clearInterval(tick);
      for (const name of ACTIVITY_EVENTS) document.removeEventListener(name, touch, true);
    };
  }, [seconds, warnSeconds]);

  return (
    <Dialog.Root open={remaining !== null}>
      <Dialog.Portal>
        <Dialog.Overlay className="idle-overlay" />
        <Dialog.Content className="idle-dialog" onInteractOutside={(event) => { event.preventDefault(); }}>
          <Dialog.Title>계속 하시겠어요?</Dialog.Title>
          <Dialog.Description>{String(remaining ?? 0)}초 뒤에 처음 화면으로 돌아갑니다.</Dialog.Description>
          <button
            type="button"
            className="big-button primary"
            onClick={() => {
              startedAt.current = Date.now();
              setRemaining(null);
            }}
          >
            계속하기
          </button>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function IdleReset({ active, ...rest }: IdleResetProps) {
  // 왜 active 일 때만 마운트: 꺼졌다 켜지면 처음부터 다시 센다(안쪽 상태가 새로 시작한다)
  return active ? <Timer {...rest} /> : null;
}
