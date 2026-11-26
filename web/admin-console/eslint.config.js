// 경계 점검(ADR 0003, 화면 영역): eslint-plugin-boundaries 로 컴포넌트·link·contract 의 의존 방향을 강제한다.
//  - contract: 계약에서 생성한 타입. 아무것도 import 하지 않는다.
//  - components: contract 와 자기 자신만 import 한다(다른 컴포넌트 import 금지). 서버 호출 금지.
//  - link: 영역 밖(서버) 통신. contract 만 import 한다. fetch 는 여기서만 쓴다.
//  - app(main.tsx, App.tsx): 조립. 모두 import 할 수 있다.
import js from "@eslint/js";
import boundaries from "eslint-plugin-boundaries";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "playwright-report", "test-results", "src/contract/**", "tests/boundaries/fixtures/**", "dev/public/**"] },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  reactHooks.configs.flat.recommended,
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    files: ["**/*.mjs", "eslint.config.js", "public/sw.js"],
    ...tseslint.configs.disableTypeChecked,
  },
  {
    // 서비스 워커는 window 가 아니라 ServiceWorkerGlobalScope 에서 돈다
    files: ["public/sw.js"],
    languageOptions: { globals: { ...globals.serviceworker } },
  },
  {
    files: ["**/src/**/*.{ts,tsx}"], // 왜 **/: 경계 시험의 fixtures(tests/boundaries/fixtures/src)에도 같은 규칙이 걸려야 한다
    plugins: { boundaries },
    settings: {
      // 왜: 확장자 없는 상대 import(./App)를 실제 파일로 풀어야 경계를 판정할 수 있다(TypeScript 해석 규칙을 그대로 쓴다)
      "import/resolver": { typescript: { project: "./tsconfig.json" } },
      "boundaries/elements": [
        { type: "contract", pattern: "src/contract" },
        { type: "link", pattern: "src/link" },
        { type: "component", pattern: "src/components/*", capture: ["name"] },
        { type: "app", pattern: "src/*.{ts,tsx}", partialMatch: false },
      ],
    },
    rules: {
      "boundaries/dependencies": [
        2,
        {
          default: "disallow",
          policies: [
            { from: { element: { type: "app" } }, allow: { to: { element: { types: ["app", "link", "component", "contract"] } } } },
            { from: { element: { type: "link" } }, allow: { to: { element: { types: ["link", "contract"] } } } },
            {
              from: { element: { type: "component" } },
              allow: [
                { to: { element: { type: "contract" } } },
                { to: { element: { type: "component", captured: { name: "{{ from.element.captured.name }}" } } } },
              ],
            },
            { from: { element: { type: "contract" } }, allow: { to: { element: { type: "contract" } } } },
          ],
        },
      ],
      "boundaries/no-unknown-dependencies": 2,
    },
  },
  {
    // 왜: 서버 호출은 link 에서만 한다(ADR 0003). 다른 곳의 fetch 는 영역 밖 통신이 새는 것이다.
    files: ["**/src/**/*.{ts,tsx}"],
    ignores: ["**/src/link/**"],
    rules: {
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "영역 밖 통신은 src/link 에서만 한다." },
        { name: "XMLHttpRequest", message: "영역 밖 통신은 src/link 에서만 한다." },
        { name: "WebSocket", message: "영역 밖 통신은 src/link 에서만 한다." },
        { name: "EventSource", message: "영역 밖 통신은 src/link 에서만 한다(알림 스트림)." },
      ],
    },
  },
);
