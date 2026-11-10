# __AREA__

## 1. 하는 일
(화면 영역이 하는 일을 한 문단으로 쓴다.)

## 2. 받는 계약·내는 계약
(`contracts/`의 어느 OpenAPI 계약을 받는지 링크한다. 이웃 영역의 사실은 복사하지 않는다.)
타입은 `npm run generate:contract -- <openapi 파일> -o src/contract/<이름>.d.ts`로만 만든다. 손으로 고치지 않는다.

## 3. 컴포넌트
| 컴포넌트 | 폴더 | 입력(props) | 하는 일 |
|---|---|---|---|
| HealthBadge | `src/components/HealthBadge` | `readyz`, `isLoading`, `isError` | 서버 준비 상태 표시(템플릿 예시) |
| NameForm | `src/components/NameForm` | `onSubmit` | 이름 입력 폼, react-hook-form(템플릿 예시) |
| GreetingTable | `src/components/GreetingTable` | `rows` | 표, @tanstack/react-table(템플릿 예시) |
| ConfirmDialog | `src/components/ConfirmDialog` | `open`, `title`, `description`, `onConfirm`, `onCancel` | 확인 대화상자, Radix UI(템플릿 예시) |

예시를 지우고 자기 컴포넌트로 바꾼다. 컴포넌트는 contract 와 자기 폴더만 import 하고, 서버 호출은 `src/link`에서만 한다(경계 점검).

## 4. 실행·시험 명령
```
npm install
npm run dev            # 개발 서버
npm run build          # 타입 검사 후 정적 파일 빌드
npm run lint           # eslint(경계 점검 포함)
npx tsc --noEmit       # 타입 검사
npm test               # Vitest(단위·계약·경계)
npm run test:e2e       # Playwright(브라우저, 처음에는 `npx playwright install chromium`)
deploy/deploy build web-__PKG__   # 이미지 빌드
tools/smoke web __AREA__              # 이미지 스모크(/healthz, /readyz)
```

## 5. 시험 상태
(시험을 돌린 날짜와 결과를 쓴다. 돌리지 않았으면 돌리지 않았다고 쓴다.)

## 6. ADR 목록
- [0001 템플릿에서 시작](docs/adr/0001-템플릿에서-시작.md)
