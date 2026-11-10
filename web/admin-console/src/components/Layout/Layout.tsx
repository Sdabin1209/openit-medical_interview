import type { ReactNode } from "react";

export interface NavItem {
  to: string;
  label: string;
}

interface Props {
  userName: string;
  nav: NavItem[];
  /** 열린 알림 수(직원·의사만) */
  openAlerts: number | undefined;
  signOutUrl: string;
  /** 링크를 그리는 쪽(react-router 의 NavLink)은 조립이 넘긴다. 컴포넌트는 라우터를 모른다. */
  renderLink: (item: NavItem) => ReactNode;
  children: ReactNode;
}

/** 머리글(이름, 로그아웃), 역할에 맞는 메뉴, 본문. 인쇄할 때는 머리글과 메뉴를 숨긴다(print.css). */
export function Layout({ userName, nav, openAlerts, signOutUrl, renderLink, children }: Props) {
  return (
    <div className="layout">
      <header className="no-print">
        <strong>문진 업무 화면</strong>
        <span aria-label="로그인한 사용자">{userName}</span>
        <a href={signOutUrl}>로그아웃</a>
      </header>
      <nav aria-label="화면 메뉴" className="no-print">
        <ul>
          {nav.map((item) => (
            <li key={item.to}>
              {renderLink(item)}
              {item.to === "/alerts" && openAlerts !== undefined && openAlerts > 0 ? <span aria-label={`열린 알림 ${String(openAlerts)}건`}> ({openAlerts})</span> : null}
            </li>
          ))}
        </ul>
      </nav>
      <main>{children}</main>
    </div>
  );
}
