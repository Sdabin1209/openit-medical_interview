// 로그인 상태와 역할. 로그인은 oauth2-proxy 가 앞에서 맡고(OIDC, Keycloak) 화면 코드는 토큰을 만지지 않는다.
// 이 화면이 oauth2-proxy 에 묻는 것은 /oauth2/userinfo 하나뿐이다(oauth2-proxy 의 표준 엔드포인트). 계약에는 역할을 묻는 작업이 없다: docs/change-requests/admin-console-001.md
import { useQuery } from "@tanstack/react-query";

// 계약 components.yaml 의 UserRole(Keycloak realm 역할 이름). 어떤 작업도 UserRole 을 스키마로 쓰지 않고 security 요구에만 이름으로 적어
// 생성 타입(src/contract)에 들어오지 않는다. 그래서 여기에 한 번 적고, tests/contract/roles.test.ts 가 계약의 enum 과 같은지 본다.
export const USER_ROLES = ["staff", "clinician", "author", "reviewer", "release-approver", "operator", "admin"] as const;
export type UserRole = (typeof USER_ROLES)[number];

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
  const roles = (info.groups ?? []).filter((group): group is UserRole => (USER_ROLES as readonly string[]).includes(group));
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
