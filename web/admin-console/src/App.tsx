// 조립(app 층): 로그인한 사용자의 역할에 따라 메뉴와 경로를 보인다. 서버가 요청마다 역할을 다시 검사하므로 이것은 편의다(보안 경계가 아니다).
import type { ReactNode } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router";

import { AlertsProvider, useAlerts } from "./AlertsContext";
import { Layout, type NavItem } from "./components/Layout";
import { AlertsPage, CaseDetailPage, CasesPage, QuestionSetsPage, ReleasePage, ResultDetailPage, ResultsPage, StartCodePage } from "./Pages";
import { SIGN_OUT_URL, type CurrentUser, type UserRole, useCurrentUser } from "./link/session";

interface Screen {
  to: string;
  label: string;
  /** 이 역할 중 하나라도 있으면 보인다(계약 각 작업의 security 요구) */
  roles: UserRole[];
}

const SCREENS: Screen[] = [
  { to: "/start-codes", label: "시작 코드", roles: ["staff"] },
  { to: "/alerts", label: "알림", roles: ["staff", "clinician"] },
  { to: "/results", label: "결과", roles: ["clinician"] },
  { to: "/question-sets", label: "문항 세트", roles: ["author"] },
  { to: "/cases", label: "실패 사례", roles: ["reviewer"] },
  { to: "/release", label: "모델 패키지", roles: ["release-approver", "operator"] },
];

function allowed(user: CurrentUser, screen: Screen): boolean {
  return screen.roles.some((role) => user.roles.includes(role));
}

function Guard({ user, to, children }: { user: CurrentUser; to: string; children: ReactNode }) {
  const screen = SCREENS.find((s) => s.to === to);
  if (screen === undefined || !allowed(user, screen)) return <p role="alert">이 화면을 볼 권한이 없다</p>;
  return children;
}

function Shell({ user }: { user: CurrentUser }) {
  const alerts = useAlerts();
  const nav: NavItem[] = SCREENS.filter((s) => allowed(user, s)).map(({ to, label }) => ({ to, label }));
  const first = nav[0];
  const openAlerts = alerts.alerts.filter((a) => a.resolved_at === undefined).length;
  return (
    <Layout
      userName={user.name}
      nav={nav}
      openAlerts={user.roles.includes("staff") || user.roles.includes("clinician") ? openAlerts : undefined}
      signOutUrl={SIGN_OUT_URL}
      renderLink={(item) => <NavLink to={item.to}>{item.label}</NavLink>}
    >
      <Routes>
        <Route path="/" element={first ? <Navigate to={first.to} replace /> : <p role="alert">이 계정에 열 수 있는 화면이 없다. 역할 부여는 운영자에게 요청한다.</p>} />
        <Route path="/start-codes" element={<Guard user={user} to="/start-codes"><StartCodePage /></Guard>} />
        <Route path="/alerts" element={<Guard user={user} to="/alerts"><AlertsPage roles={user.roles} /></Guard>} />
        <Route path="/results" element={<Guard user={user} to="/results"><ResultsPage /></Guard>} />
        <Route path="/results/:sessionId" element={<Guard user={user} to="/results"><ResultDetailPage roles={user.roles} /></Guard>} />
        <Route path="/question-sets" element={<Guard user={user} to="/question-sets"><QuestionSetsPage /></Guard>} />
        <Route path="/cases" element={<Guard user={user} to="/cases"><CasesPage /></Guard>} />
        <Route path="/cases/:caseId" element={<Guard user={user} to="/cases"><CaseDetailPage /></Guard>} />
        <Route path="/release" element={<Guard user={user} to="/release"><ReleasePage roles={user.roles} /></Guard>} />
        <Route path="*" element={<p role="alert">없는 화면이다</p>} />
      </Routes>
    </Layout>
  );
}

export function App() {
  const user = useCurrentUser();
  if (user.isLoading) return <p>불러오는 중</p>;
  if (user.data === undefined) return <p role="alert">로그인 정보를 읽지 못했다</p>;
  const streams = user.data.roles.includes("staff") || user.data.roles.includes("clinician");
  return (
    <AlertsProvider enabled={streams}>
      <Shell user={user.data} />
    </AlertsProvider>
  );
}
