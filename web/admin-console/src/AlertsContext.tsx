// 직원 알림 스트림을 앱 전체에서 하나만 연다(메뉴의 열린 알림 수와 알림 화면이 같은 연결을 쓴다).
import { createContext, type ReactNode, use } from "react";

import { useStaffAlerts } from "./link/alerts";

type AlertsState = ReturnType<typeof useStaffAlerts>;

const AlertsContext = createContext<AlertsState | null>(null);

export function AlertsProvider({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const state = useStaffAlerts(enabled);
  return <AlertsContext value={state}>{children}</AlertsContext>;
}

export function useAlerts(): AlertsState {
  const state = use(AlertsContext);
  if (state === null) throw new Error("AlertsProvider 밖에서 알림을 읽었다");
  return state;
}
