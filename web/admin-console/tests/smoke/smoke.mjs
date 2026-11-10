// 이미지 스모크(ADR 0004): 이미지를 띄워 /healthz, /readyz 와 보안 설정을 확인한다. `tools/smoke <영역>` 이 부른다.
// docker 호출은 호출자가 준비한 격리 환경(DOCKER_CONFIG, DOCKER_HOST)만 쓴다. 호스트 포트는 Docker 가 배정한다.
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";

const image = process.env.OPENIT_SMOKE_IMAGE;
if (!image) fail("OPENIT_SMOKE_IMAGE 가 없다. tools/smoke 로 실행한다");
if (!process.env.DOCKER_CONFIG) fail("DOCKER_CONFIG 가 없다. tools/smoke 로 실행해 격리 설정을 받는다");

const env = Object.fromEntries(
  ["PATH", "DOCKER_CONFIG", "DOCKER_HOST"].filter((k) => process.env[k]).map((k) => [k, process.env[k]]),
);

function fail(message) {
  console.error(message);
  process.exit(1);
}

function docker(...args) {
  const result = spawnSync("docker", args, { env, encoding: "utf8" });
  if (result.status !== 0) fail(`docker ${args[0]} 실패 rc=${String(result.status)}: ${result.stderr.slice(-500)}`);
  return result.stdout.trim();
}

const name = `openit-web-smoke-${randomBytes(4).toString("hex")}`;
let failed = false;
const cid = docker(
  "run", "-d", "--name", name, "--read-only", "--tmpfs", "/tmp", "--cap-drop", "ALL",
  "--security-opt", "no-new-privileges", "-p", "127.0.0.1::8080", image,
);

async function get(path) {
  const hostPort = docker("port", cid, "8080/tcp").split("\n")[0];
  const deadline = Date.now() + 30_000;
  for (;;) {
    try {
      const response = await fetch(`http://${hostPort}${path}`, { signal: AbortSignal.timeout(3000) });
      return { status: response.status, body: await response.text() };
    } catch (error) {
      if (Date.now() > deadline) throw error;
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
}

function check(label, ok) {
  console.log(`${ok ? "OK  " : "FAIL"} ${label}`);
  if (!ok) failed = true;
}

try {
  const healthz = await get("/healthz");
  check("/healthz 200", healthz.status === 200 && JSON.parse(healthz.body).status === "pass");
  const readyz = await get("/readyz");
  check("/readyz 200 pass", readyz.status === 200 && JSON.parse(readyz.body).status === "pass");
  const index = await get("/console/");
  check("/console/ 에 화면(index.html)이 있다", index.status === 200 && index.body.includes('id="root"'));
  const spa = await get("/console/about");
  check("없는 경로는 index.html 로(SPA 라우팅)", spa.status === 200 && spa.body.includes('id="root"'));
  check("비root 로 실행", docker("exec", cid, "id", "-u") !== "0");
  check("루트 파일시스템 읽기 전용", docker("inspect", "-f", "{{.HostConfig.ReadonlyRootfs}}", cid) === "true");
  check("HEALTHCHECK 가 healthy", await waitHealthy());
} finally {
  // 진단 수단을 지우지 않는다: 실패했으면 로그를 먼저 남긴다
  if (failed) spawnSync("docker", ["logs", "--tail", "50", cid], { env, stdio: "inherit" });
  spawnSync("docker", ["rm", "-f", cid], { env, stdio: "ignore" });
}

async function waitHealthy() {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    if (docker("inspect", "-f", "{{.State.Health.Status}}", cid) === "healthy") return true;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return false;
}

process.exit(failed ? 1 : 0);
