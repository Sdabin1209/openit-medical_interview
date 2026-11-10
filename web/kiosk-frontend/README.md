# kiosk-frontend

## 1. 하는 일
병원 키오스크에서 환자가 쓰는 문진 화면이다. 직원에게 받은 6자리 시작 코드를 숫자 키패드로 입력하고(QR 없음), 문진표를 고르고, 질문·응답 문장을 크게 보며 말하거나 글자로 답한다. 직원 호출, 문진 끝내기, 입력이 60초 없으면 처음 화면으로 돌아가는 초기화가 있다. 음성 인식·합성은 기기 안에서만 하고 외부로 보내지 않는다([ADR 0002](docs/adr/0002-음성은-기기-안에서만.md)). 기기 인증은 브라우저·OS 가 내는 기기 인증서이고 화면 코드는 신원을 다루지 않는다.

## 2. 받는 계약·내는 계약
- 부르는 계약: [survey-service](../../contracts/openapi/survey-service.yaml) 의 `listActiveQuestionnaires`, `startSession`, `submitTurn`, `endSession`, `getSessionState`, `requestStaffCall`(흐름 N01, N02).
- 내는 계약: [kiosk-frontend](../../contracts/openapi/kiosk-frontend.yaml)(`/healthz`, `/readyz`, `/metrics`). nginx 가 `/healthz`, `/readyz` 를 답한다. `/metrics` 도 nginx 가 살아 있음 지표(`kiosk_frontend_up`) 하나를 낸다.
- 타입은 `npm run generate:contract` 로만 만든다(`src/contract/`, 손으로 고치지 않는다). 설정은 `redocly.yaml`, 점검은 `npm run check:contract` 와 `openit-check contract-drift`(ADR 0020).
- 계약이 부족하거나 틀렸다고 본 것: [kiosk-frontend-001](../../docs/change-requests/kiosk-frontend-001.md)(문진표 선택), [002](../../docs/change-requests/kiosk-frontend-002.md)(유휴 만료의 주체), [003](../../docs/change-requests/kiosk-frontend-003.md)(실패 신호의 turn_id).

## 3. 컴포넌트
| 컴포넌트 | 폴더 | 입력(props) | 하는 일 |
|---|---|---|---|
| StartView | `src/components/StartView` | `codeLength`, `questionnaires`, `onStart`, `onDirtyChange` | 시작 코드 키패드, 문진표 선택(start_view) |
| ConversationView | `src/components/ConversationView` | 문장, 발화 초안, `maxLength`, `voiceInput`, `voiceOutput`, 콜백 | 질문·응답 문장 표시, 발화 입력, 직원 부르기, 끝내기(conversation_view) |
| PausedView | `src/components/PausedView` | `reason`, `onCallAgain` | 직원 호출·위험 신호로 멈춘 동안의 안내 |
| EndView | `src/components/EndView` | `outcome`, `closingText`, `onDone` | 끝 화면 |
| IdleReset | `src/components/IdleReset` | `active`, `seconds`, `warnSeconds`, `onIdle` | 유휴 초기화와 경고(idle_reset, [ADR 0004](docs/adr/0004-고령자-접근성과-유휴-초기화.md)) |
| speech | `src/components/speech` | `useSpeechRecognition`, `useSpeechSynthesis` | 기기 안 음성 인식·합성(speech) |
| link_survey | `src/link/survey.ts` | 주소와 계약의 시간 상한 | survey-service 호출과 재시도([ADR 0003](docs/adr/0003-화면-구성과-재시도.md)) |

조립은 `src/App.tsx`, 계약 값은 `src/limits.ts`, 세션 모양은 `src/session.ts`. 컴포넌트는 `contract` 와 자기 폴더만 import 하고 서버 호출은 `src/link` 에서만 한다(경계 점검).

## 4. 실행·시험 명령
```
npm install
npm run dev                 # 개발 서버
npm run build               # 타입 검사 후 정적 파일 빌드
npm run generate:contract   # 계약에서 타입 다시 만들기
npm run check:contract      # 생성물이 계약과 같은지
npm run lint                # eslint(경계 점검 포함)
npx tsc --noEmit            # 타입 검사
npm test                    # Vitest(단위·계약·경계). 가짜 survey-service 는 MSW
tools/web-e2e kiosk-frontend          # Playwright(공식 이미지 안), 리포 루트에서
deploy/deploy build kiosk-frontend    # 이미지 빌드
tools/smoke web kiosk-frontend        # 이미지 스모크
```
가짜 survey-service 는 `tests/fakes/survey-service.ts` 하나이고 단위 시험(MSW)과 브라우저 시험(`page.route`)이 함께 쓴다.

## 5. 시험 상태
이 절은 이 영역의 시험 상태만 쓴다. 2026-11-10 기준.
- `npm test`, `npx tsc --noEmit`, `npm run lint`, `tools/web-e2e kiosk-frontend`, 이미지 빌드와 스모크의 결과는 작업 보고에 있다(아래 줄을 시험을 돌린 뒤 갱신한다).
- 확인하지 못한 것: 실제 키오스크 Chrome 의 Web Speech API(기기 안 인식 가능 여부, 한국어 목소리). Playwright 이미지의 headless Chromium 은 `SpeechRecognition.available()` 에서 죽어 대역으로 시험했다(ADR 0002). 고령자 사용 시험, 대비 측정 도구 확인, 기기 인증서(mTLS)가 걸린 게이트웨이 뒤의 실제 호출, nginx 이미지 위에서의 브라우저 시험(브라우저 시험은 같은 보안 헤더를 붙인 `vite preview` 에서 돈다).

## 6. ADR 목록
- [0001 템플릿에서 시작](docs/adr/0001-템플릿에서-시작.md)
- [0002 음성은 기기 안에서만 처리한다](docs/adr/0002-음성은-기기-안에서만.md)
- [0003 화면 구성, 서버 호출과 재시도](docs/adr/0003-화면-구성과-재시도.md)
- [0004 고령자 접근성과 유휴 초기화](docs/adr/0004-고령자-접근성과-유휴-초기화.md)
