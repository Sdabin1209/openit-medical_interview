# 0012. 화면 시험과 Playwright 컨테이너

## 상태
승인(2026-11-10, 헤드 위임)

## 맥락
화면은 단위(컴포넌트), 계약(link가 받는 응답), 경계, 브라우저(e2e), 이미지 스모크로 시험한다. Playwright의 브라우저는 시스템 라이브러리(nss, nspr, alsa)가 필요한데, 이 환경은 관리자 권한(sudo) 없이 설치할 수 없었다(`ldd`로 4개 라이브러리 없음을 확인).

## 결정
- 단위·계약·경계: Vitest(jsdom) + @testing-library/react. 컴포넌트마다 경계 사례(65자 이름, 빈 목록, Esc 닫기)를 둔다.
- 브라우저: Playwright 시험은 `tests/e2e/`에 있고 `npm run test:e2e`로 호스트에서 돌릴 수 있다. 시스템 라이브러리가 없는 환경에서는 `tools/web-e2e <영역>`이 Playwright 공식 이미지(`mcr.microsoft.com/playwright:v<버전>-noble`, Apache-2.0)에서 같은 시험을 돌린다. 이미지 태그는 영역이 설치한 `@playwright/test` 버전과 같아야 해서 잠금된 설치본에서 읽는다.
- 서버 API는 e2e에서 `page.route`로 가로채 계약대로 답한다(이웃 영역 없이 혼자 시험, 워크스페이스 규칙).
- 포트: Playwright 설정이 빈 포트를 골라 환경 변수에 담는다(워커가 같은 값을 물려받아야 하기 때문. 처음에는 워커마다 다른 포트를 골라 실패했다).
- 이미지 스모크: `tests/smoke/smoke.mjs`(node)가 격리된 docker 환경으로 이미지를 띄우고 `/healthz`·`/readyz`·SPA 폴백·비root·읽기 전용 루트·HEALTHCHECK를 확인한다. `tools/smoke web <영역>`이 빌드와 실행을 맡는다.

## 왜
- 공식 이미지는 브라우저 버전과 라이브러리를 함께 고정해서 호스트마다 결과가 달라지는 일을 막는다(Playwright 문서가 CI에서 권하는 방식).
- 브라우저 시험이 호스트 설치에 의존하면 이 환경처럼 권한이 없는 곳에서 시험이 빠진다.

## 검토한 대안과 버리는 이유
- **`playwright install-deps`:** apt와 sudo가 필요하다. 사용자 시스템을 바꾸므로 쓰지 않았다.
- **jsdom만 쓰기:** 실제 브라우저의 라우팅·포커스 동작을 못 본다.

## 결과
- **얻는 것:** 어디서나 같은 브라우저 시험. 이 환경에서 3개 시험 통과.
- **감수하는 것:** 공식 이미지 태그는 digest가 아니라 `@playwright/test` 버전으로 고정된다(이미지 digest를 코드에 박으면 버전과 어긋난다). 첫 실행에 이미지 내려받기 시간이 든다. `tools/web-e2e`는 이 환경(Docker Desktop WSL)에서만 확인했다.

## 되돌리는 조건
호스트에서 브라우저 라이브러리를 설치할 수 있는 표준 환경이 확보되면 `npm run test:e2e`를 기본으로 하고 컨테이너 방식은 보조로 둔다.
