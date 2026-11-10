// 로그인 상태와 역할. 로그인은 oauth2-proxy 가 앞에서 맡고(OIDC, Keycloak) 화면 코드는 토큰을 만지지 않는다.
// 이 화면이 oauth2-proxy 에 묻는 것은 /oauth2/userinfo 하나뿐이다(oauth2-proxy 의 표준 엔드포인트). 계약에는 역할을 묻는 작업이 없고 oauth2-proxy 의 groups 를 쓰기로 확정했다(계약 README 9.0.0, ADR 0002).
import { useQuery } from "@tanstack/react-query";

import type { components } from "../contract/components";

// 계약 UserRole(Keycloak realm 역할 이름)은 생성 타입(src/contract/components.d.ts)에서 얻는다(변경 요청 admin-console-003).
// 걸러낼 때 쓸 실행 시점 목록은 Record 로 둔다: 키가 UserRole 과 하나라도 다르면 tsc 가 막아 계약과 어긋나지 않는다.
export type UserRole = components["schemas"]["UserRole"];
const USER_ROLE_SET: Record<UserRole, true> = { staff: true, clinician: true, author: true, reviewer: true, "release-approver": true, operator: true, admin: true };

export interface CurrentUser {
  /** 화면에 보일 이름(preferredUsername, 없으면 email) */
  name: string;
  roles: UserRole[];
}

/** oauth2-proxy 로그인 시작 주소로 보낸다. 돌아올 곳(rd)은 지금 경로다. */
export function redirectToSignIn(): void {
  const here = globalThis.location.pathname + globalThis.location.search;
  globalThis.location.assign(`/oauth2/start?rd=${encodeURIComponent(here)}`);
}

export const SIGN_OUT_URL = "/oauth2/sign_out";

/** oauth2-proxy userinfo 응답에서 쓰는 칸. 그 밖의 칸은 무시한다(oauth2-proxy 문서의 모양). */
interface UserInfo {
  user?: string;
  email?: string;
  preferredUsername?: string;
  groups?: string[];
}

export function parseUser(info: UserInfo): CurrentUser {
  const roles = (info.groups ?? []).filter((group): group is UserRole => Object.hasOwn(USER_ROLE_SET, group));
  return { name: info.preferredUsername ?? info.email ?? info.user ?? "", roles };
}

export async function fetchCurrentUser(signal?: AbortSignal): Promise<CurrentUser> {
  const response = await fetch("/oauth2/userinfo", { headers: { Accept: "application/json" }, ...(signal ? { signal } : {}) });
  if (response.status === 401) {
    redirectToSignIn();
    throw new Error("로그인이 필요하다");
  }
  if (!response.ok) throw new Error(`/oauth2/userinfo 응답 코드 ${String(response.status)}`);
  return parseUser((await response.json()) as UserInfo);
}

export function useCurrentUser() {
  // 왜 staleTime Infinity: 역할은 로그인 세션 동안 바뀌지 않는다고 본다(바뀌면 다시 로그인). 서버가 매 요청에서 역할을 다시 검사한다.
  return useQuery({ queryKey: ["current-user"], queryFn: ({ signal }) => fetchCurrentUser(signal), staleTime: Infinity, retry: false });
}
