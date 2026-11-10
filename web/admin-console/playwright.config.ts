import { createServer } from "node:net";

import { defineConfig, devices } from "@playwright/test";

// 왜 빈 포트를 고른다: 고정 포트는 여러 영역이 같은 서버에서 동시에 시험할 때 충돌한다(워크스페이스 스모크 규칙).
async function freePort(): Promise<number> {
  return await new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => {
        if (address !== null && typeof address === "object") resolve(address.port);
        else reject(new Error("빈 포트를 얻지 못했다"));
      });
    });
  });
}

// 왜 환경 변수에 담는다: 설정 파일은 워커마다 다시 실행된다. 처음 실행한 프로세스가 고른 포트를 워커가 그대로 물려받아야 한다.
process.env["OPENIT_E2E_PORT"] ??= String(await freePort());
const port = Number(process.env["OPENIT_E2E_PORT"]);

export default defineConfig({
  testDir: "tests/e2e",
  use: { baseURL: `http://127.0.0.1:${String(port)}` },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npx vite build && npx vite preview --host 127.0.0.1 --port ${String(port)} --strictPort`,
    url: `http://127.0.0.1:${String(port)}/console/`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
