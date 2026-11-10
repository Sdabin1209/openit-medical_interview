# 0010. 화면은 `/console/` 접두어 아래에서 서비스한다

## 상태
승인(2026-11-11, 헤드 결정을 영역에서 구현). [0009](0009-노출-선언과-이미지-라벨-원본-파일.md) 의 노출 경로 `/` 를 대체한다.

## 맥락
admin-console 과 kiosk-frontend 의 `exposure.json` 이 둘 다 경로 접두어 `/`, 메서드 GET 이었다. 공개 입구(Envoy)는 서로 다른 영역이 같은 (경로, 메서드)를 열면 시작하지 않는다(platform ADR 0003, 계약 README). 두 화면은 한 출처에서 나가야 하는데 `Exposure` 에는 호스트 칸이 없다.

## 결정
- 이 화면은 `/console/` 아래에서 서비스한다(`exposure.json` 의 `path_prefix`, 메서드 GET, 대상 `HUMAN_OIDC`). 다른 화면은 `/kiosk/` 다.
- Vite `base` 를 `/console/` 로 둔다(빌드 산출물의 자원 경로). 라우터는 `BrowserRouter basename={import.meta.env.BASE_URL}` 로 같은 값을 얻어 접두어를 코드에 두 번 쓰지 않는다.
- 입구는 경로를 바꾸지 않고(prefix rewrite 없음) 넘기므로 nginx 가 `/console/…` 요청을 그대로 받는다. 이미지는 빌드 결과를 `/usr/share/nginx/html/console/` 에 두고, `location /console/` 가 정적 파일과 SPA 폴백(`/console/index.html`)을 내고 `location /console/assets/` 가 해시 파일을 오래 캐시한다. `/healthz`, `/readyz` 는 영역 안 감시용이므로 접두어 밖 루트에 그대로 둔다.
- 화면이 부르는 API(`/v1/…`, `/oauth2/…`)는 접두어 밖의 절대 경로다. 입구가 각 서비스의 `Exposure` 로 나눈다.
- 로그인 뒤 돌아오는 주소(`/oauth2/start?rd=`)는 지금 경로(`location.pathname`)라 접두어를 포함한다. 화면 안 링크는 라우터가 만들어 basename 이 붙는다. 서비스 워커는 `${BASE_URL}sw.js` 로 등록하고(범위는 `/console/`) 알림을 누르면 범위 아래 `alerts` 로 간다.
- `tests/contract/declarations.test.ts` 가 노출 접두어, Vite `base`, nginx 경로, Dockerfile 배치가 같은지 본다.

## 왜
- 한 출처에서 여러 앱을 내는 표준적인 방법은 경로 접두어다. 접두어는 `Exposure` 가 이미 가진 칸(`path_prefix`)만 쓰고 계약을 바꾸지 않는다.
- Vite 의 `base` 와 React Router 의 `basename` 은 하위 경로 배포를 위한 각 도구의 공식 설정이다. `import.meta.env.BASE_URL` 은 Vite 가 `base` 로 채우는 값이다.
- 파일을 하위 폴더에 두는 이유는 nginx 가 `alias` 와 `try_files` 를 함께 쓸 때의 알려진 문제를 피하고, 요청 경로와 파일 경로가 같아 설정이 단순해지기 때문이다. 대안 비교를 측정으로 하지는 않았다.

## 검토한 대안과 버리는 이유
- 호스트 이름 분리(`console.<도메인>`, `kiosk.<도메인>`): `Exposure` 에 호스트 칸이 없어 계약 변경이 필요하고, 입구 인증서의 이름 목록과 로그인(oauth2-proxy) 리다이렉트 주소가 호스트마다 늘어 복잡해진다.
- 입구에서 접두어를 지우는 prefix rewrite: 입구는 경로를 바꾸지 않기로 했다(헤드 결정). 영역 정적 서버가 접두어를 받는다.
- 한 화면을 `/` 에 두고 다른 하나만 접두어를 주기: 두 화면이 대칭이 아니고, `/` 를 연 영역이 이후 다른 경로를 열 때 겹친다.

## 결과
- 얻는 것: 두 화면이 한 출처에서 겹치지 않는다. 빌드 산출물과 라우터가 같은 값(Vite `base`)을 따른다.
- 서비스 워커 범위가 `/console/` 로 좁아진다. 이전 `/` 범위로 등록된 워커가 있는 브라우저는 따로 정리하지 않았다(새 배포 전에 `/` 로 서비스한 적이 없어 해당 없음, 확인한 것은 아니다).
- 감수하는 것: 사용자가 `/` 로 들어오면 화면이 없다(입구가 `/console/` 안내를 따로 하지 않으면 404). 입구의 `/` 안내는 헤드(deploy)의 몫이다. 이미지의 `THIRD_PARTY_NOTICES.txt` 는 점검(`openit-check notices`)이 보는 `/usr/share/nginx/html/` 자리에 두고 `/console/THIRD_PARTY_NOTICES.txt` 주소로 내보낸다.
- 접두어를 바꾸려면 `exposure.json`, Vite `base`, nginx, Dockerfile, 시험의 경로를 같이 고쳐야 하고 시험이 어긋남을 잡는다.

## 되돌리는 조건
`Exposure` 에 호스트 칸이 생기고 입구가 호스트별로 나누게 되면 호스트 분리를 다시 검토한다. 두 화면 중 하나가 퇴역하면 남은 화면을 `/` 로 되돌릴 수 있다.
