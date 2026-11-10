"""샌드박스(D123): 제품을 그대로 복사한 두 번째 설치를 따로 띄운다. 제품 compose·설정에는 시험용 문이 없다.

- 리포의 deploy/·platform/·contracts/ 를 임시 폴더로 복사하고 그 복사본의 ./deploy bootstrap 으로 설치한다(신뢰의 뿌리 -> 레지스트리 -> 기동).
- 시험에 필요한 것은 설치 입력(노출 선언, 기기 허용 목록, 기계 호출자 표, 기기 CA)과 compose 에 더하는 시험 서비스뿐이다.
  시험 서비스: 평문 에코 상류(가짜 영역 서비스), 영역마다 실제 영역 게이트웨이(platform/caddy/area-gateway.Caddyfile, platform ADR 0007), 클라이언트.
- 끝나면 이 프로젝트(openit-int-pf-sbx-…)의 컨테이너·볼륨·네트워크를 내리고 남은 것이 0개인지 확인한다. 실패하면 로그를 먼저 남긴다.
"""

from __future__ import annotations

import importlib.util
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from types import ModuleType

from cryptography.hazmat.primitives import serialization

from openit_platform import area_gateway

from .devices import Issued, make_ca, make_device

REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TRUST_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "UV_CACHE_DIR", "XDG_CACHE_HOME")  # 상속 환경을 통째로 넘기지 않는다(RUNTIME R9.1)
SERVICES = ("survey-service", "model-runtime", "admin-console", "kiosk-frontend")
KC_PASSWORD = "Sandbox-Pass-1"  # 시험 계정의 임시 값(비밀이 아니다)

EXPOSURES = {
    "survey-service": {
        "routes": [
            {"path_prefix": "/v1/questionnaires", "methods": ["GET"], "audience": "DEVICE_MTLS"},
            {"path_prefix": "/v1/questionnaires", "methods": ["GET"], "audience": "HUMAN_OIDC"},
            {"path_prefix": "/v1/sessions", "methods": ["GET", "POST"], "audience": "DEVICE_MTLS"},
            {"path_prefix": "/v1/start-codes", "methods": ["POST"], "audience": "HUMAN_OIDC"},
            {"path_prefix": "/v1/results", "methods": ["GET"], "audience": "HUMAN_OIDC"},
            {"path_prefix": "/v1/results", "methods": ["GET"], "audience": "EXTERNAL_MACHINE_TOKEN"},
            {"path_prefix": "/v1/risk-signals", "methods": ["POST"], "audience": "EXTERNAL_MACHINE_TOKEN"},
            {"path_prefix": "/v1/case-exports", "methods": ["GET"], "audience": "MACHINE_TOKEN"},
        ],
        "egress": ["model-runtime", "platform"],
    },
    "model-runtime": {"routes": [{"path_prefix": "/v1/model-status", "methods": ["GET"], "audience": "HUMAN_OIDC"}], "egress": []},
    "admin-console": {"routes": [{"path_prefix": "/console/", "methods": ["GET"], "audience": "HUMAN_OIDC"}], "egress": []},
    "kiosk-frontend": {"routes": [{"path_prefix": "/kiosk/", "methods": ["GET"], "audience": "DEVICE_MTLS"}], "egress": []},
}
MACHINE_CALLERS = {
    "tokens": [
        {"client": "hospital", "roles": ["result-reader"], "client_secret_file": "/run/secrets/unused-hospital"},
        {"client": "detector", "roles": ["risk-detector"], "client_secret_file": "/run/secrets/unused-detector"},
        {"client": "lab", "roles": ["case-reader"], "client_secret_file": "/run/secrets/unused-lab"},
    ]
}

ACME_URL = "https://step-ca:9000/acme/acme/directory"  # deploy/env.example 의 OPENIT_INTERNAL_ACME_DIRECTORY_URL 기본값
UPSTREAM_PORT = 8080
CADDY_IMAGE = "caddy:2.11.9@sha256:0c2243efcf437ab7f7a978f1027fcf0d4f9be8a75df27b1b3fbc5dbe0ffa8cf0"  # 제품 compose 와 같은 digest
CLIENT_CERT_AREA = "survey-service"  # 시험 클라이언트가 이웃 영역으로서 보일 클라이언트 인증서의 주인(그 영역 게이트웨이가 받은 인증서를 읽기 전용으로 본다)

# 가짜 영역 서비스: 평문 HTTP 로 받은 요청의 머리글을 본문에 되돌려 준다(영역 게이트웨이 뒤의 서비스 컨테이너 자리).
UPSTREAM_CADDYFILE = """# 시험용 평문 상류(영역 서비스의 자리). 영역 게이트웨이만 닿는다.
{
	admin off
	auto_https off
}

http://:8080 {
	handle /metrics {
		respond <<METRICS
			# TYPE sandbox_up gauge
			sandbox_up 1
			METRICS 200
	}
	handle {
		respond <<BODY
			service={http.request.host}
			method={http.request.method}
			path={http.request.uri.path}
			xfcc={http.request.header.X-Forwarded-Client-Cert}
			authorization={http.request.header.Authorization}
			BODY 200
	}
}
"""


def gateway_service(name: str) -> str:
    """영역 게이트웨이 하나(제품의 deploy 가 영역마다 compose 에 두는 것과 같은 모양: platform/caddy/area-gateway.md)."""
    healthcheck = area_gateway.healthcheck_command(name, ACME_URL)
    return f"""  sandbox-gw-{name}:
    image: {CADDY_IMAGE}
    read_only: true
    user: "10001:10001"
    cap_drop: [ALL]
    cap_add: [NET_BIND_SERVICE]
    security_opt: ["no-new-privileges:true"]
    tmpfs:
      - /data:uid=10001,gid=10001,mode=0700
      - /config:uid=10001,gid=10001,mode=0700
    environment:
      OPENIT_AREA_NAME: {name}
      OPENIT_AREA_UPSTREAM: sandbox-upstream:{UPSTREAM_PORT}
      OPENIT_SERVICE_PORT: "8443"
      OPENIT_INTERNAL_ACME_DIRECTORY_URL: {ACME_URL}
    volumes:
      - ../platform/caddy/{area_gateway.CADDYFILE}:/etc/caddy/Caddyfile:ro
      - ${{OPENIT_TRUST_LIST_FILE}}:/etc/openit/trust-list.pem:ro
      - sandbox-certs-{name}:{area_gateway.AREA_CERTS}
    networks:
      backend:
        aliases: [{name}]
    healthcheck:
      test: ["CMD-SHELL", "{healthcheck}"]
      interval: 3s
      timeout: 3s
      retries: 100
"""


def compose_text() -> str:
    gateways = "".join(gateway_service(name) for name in SERVICES)
    volumes = "".join(f'  sandbox-certs-{name}:\n    driver: local\n    driver_opts: {{ type: tmpfs, device: tmpfs, o: "uid=10001,gid=10001,mode=0700" }}\n' for name in SERVICES)
    return f"""# 시험용 서비스(제품 compose 에는 없다). 제품 compose 와 합쳐 같은 프로젝트로 띄운다.
services:
  sandbox-upstream:
    image: {CADDY_IMAGE}
    read_only: true
    user: "10001:10001"
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    tmpfs:
      - /data:uid=10001,gid=10001,mode=0700
      - /config:uid=10001,gid=10001,mode=0700
    volumes:
      - ./sandbox/Caddyfile:/etc/caddy/Caddyfile:ro
    networks: [backend]
{gateways}  sandbox-client:
    image: smallstep/step-ca:0.28.4@sha256:0f88382ac5af5c6b7bbba0c6e8fcefef52aee6f22ea364df8e02a09ffd0d22f3
    read_only: true
    user: "10001:10001"
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    entrypoint: ["sleep", "infinity"]
    volumes:
      - ${{OPENIT_TRUST_LIST_FILE}}:/etc/openit/trust-list.pem:ro
      - sandbox-certs-{CLIENT_CERT_AREA}:{area_gateway.AREA_CERTS}:ro
    networks: [backend]
volumes:
{volumes}"""


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Sandbox:
    def __init__(self) -> None:
        self.project = f"openit-int-pf-sbx-{secrets.token_hex(3)}"
        self.root = Path(tempfile.mkdtemp(prefix=f"{self.project}-"))
        self.deploy_dir = self.root / "deploy"
        self.state = self.root / "state"
        self.dockerenv = load_module("sandbox_dockerenv", REPO / "deploy" / "dockerenv.py")
        self.org_ca: Issued | None = None
        self.devices: dict[str, Issued] = {}

    # ------------------------------------------------------------ 준비
    def prepare(self) -> None:
        # 왜 폴더째: compose 가 deploy/ 아래 파일(postgres/init 등)을 마운트한다. 이 설치의 상태(비밀, pki, 생성 파일, .env)는 복사하지 않는다
        state = ("secrets", "pki", "generated", ".env", "backups", ".build-meta", "images.lock", "__pycache__")
        shutil.copytree(REPO / "deploy", self.deploy_dir, ignore=shutil.ignore_patterns(*state))
        for name in ("src", "caddy", "monitoring"):
            shutil.copytree(REPO / "platform" / name, self.root / "platform" / name, ignore=shutil.ignore_patterns("__pycache__"))
        contracts = self.root / "contracts"
        contracts.mkdir()
        shutil.copy2(REPO / "contracts" / "components.yaml", contracts / "components.yaml")
        shutil.copytree(REPO / "contracts" / "openapi", contracts / "openapi")
        # 왜 사본에서만 바꾸나: oauth2-proxy 의 제공자는 `--provider=oidc` 여야 groups 가 UserRole 뿐이다(platform ADR 0004). 제품 compose 의 반영은 헤드가 한다.
        # 반영된 뒤에는 아래 치환이 아무것도 바꾸지 않는다
        compose = self.deploy_dir / "compose.yaml"
        compose.write_text(compose.read_text(encoding="utf-8").replace("--provider=keycloak-oidc", "--provider=oidc"), encoding="utf-8")
        self.state.mkdir()
        (self.state / "exposures").mkdir()
        for service, exposure in EXPOSURES.items():
            (self.state / "exposures" / f"{service}.json").write_text(json.dumps(exposure), encoding="utf-8")
        (self.state / "machine-callers.json").write_text(json.dumps(MACHINE_CALLERS), encoding="utf-8")
        self.write_devices()
        (self.deploy_dir / "sandbox").mkdir()
        (self.deploy_dir / "sandbox" / "Caddyfile").write_text(UPSTREAM_CADDYFILE, encoding="utf-8")
        (self.deploy_dir / "compose.sandbox.yaml").write_text(compose_text(), encoding="utf-8")
        env = {
            "OPENIT_PROJECT_NAME": self.project,
            # 왜 5m: 리프의 자동 갱신(Caddy)과 입구의 인증서 재적재, 루트 교체 뒤 새 중간 CA 로의 갱신을 몇 분 안에 본다(ADR 0014 의 시험 방법)
            "OPENIT_LEAF_LIFETIME": "5m",
            "OPENIT_CA_WARN_LEAF": "1m",
            "OPENIT_CA_ALLOWED_DNS": "registry,step-ca,gateway,openit.internal,*.openit.internal," + ",".join(SERVICES),
            "OPENIT_DEVICE_CA_CERTIFICATE_FILE": str(self.state / "device-ca.pem"),
            "OPENIT_DEVICE_ALLOWLIST_FILE": str(self.state / "device-allowlist.json"),
            "OPENIT_EXPOSURES_DIR": str(self.state / "exposures"),
            "OPENIT_MACHINE_TOKENS_FILE": str(self.state / "machine-callers.json"),
        }
        (self.deploy_dir / ".env").write_text("".join(f"{k}={v}\n" for k, v in env.items()), encoding="utf-8")

    def write_devices(self) -> None:
        self.org_ca = make_ca("Sandbox Organization Device CA")
        (self.state / "device-ca.pem").write_bytes(self.org_ca.cert.public_bytes(serialization.Encoding.PEM))
        self.devices = {
            "kiosk-01": make_device(self.org_ca, "kiosk-01"),
            "kiosk-02": make_device(self.org_ca, "kiosk-02"),  # 조직 CA 가 발급했으나 허용 목록에 없다
            "kiosk-01-other-serial": make_device(self.org_ca, "kiosk-01"),  # 같은 기기 ID, 허용한 일련번호가 아니다
            "rogue": make_device(make_ca("Unknown CA"), "kiosk-01"),  # 모르는 CA 가 낸 인증서
        }
        self.write_allowlist(["kiosk-01"])
        folder = self.state / "devices"
        folder.mkdir()
        for name, issued in self.devices.items():
            issued.write(folder, name)

    def write_allowlist(self, names: list[str]) -> None:
        devices = [{"device_id": name, "serial_number": self.devices[name].serial_hex} for name in names]
        (self.state / "device-allowlist.json").write_text(json.dumps({"devices": devices}), encoding="utf-8")

    def device_files(self, name: str) -> tuple[Path, Path]:
        return self.state / "devices" / f"{name}.crt", self.state / "devices" / f"{name}.key"

    # ------------------------------------------------------------ 실행
    def environment(self) -> dict[str, str]:
        return {key: os.environ[key] for key in TRUST_ENV if key in os.environ}

    def deploy(self, *args: str, check: bool = True, timeout: int = 1500) -> subprocess.CompletedProcess[str]:
        result = subprocess.run([str(self.deploy_dir / "deploy"), *args], cwd=self.root, env=self.environment(), capture_output=True, text=True, check=False, timeout=timeout)
        if check and result.returncode != 0:
            raise AssertionError(f"./deploy {' '.join(args)} rc={result.returncode}\n{(result.stdout + result.stderr)[-3000:]}")
        return result

    def compose_args(self) -> list[str]:
        generated = self.deploy_dir / "generated"
        return [
            "compose",
            "--project-name",
            self.project,
            "--project-directory",
            str(self.deploy_dir),
            "-f",
            str(self.deploy_dir / "compose.yaml"),
            "-f",
            str(generated / "compose.platform.yaml"),
            "-f",
            str(self.deploy_dir / "compose.sandbox.yaml"),
            "--profile",
            "local-registry",
            "--profile",
            "tools",
            "--env-file",
            str(self.deploy_dir / "env.example"),
            "--env-file",
            str(generated / "platform.env"),
            "--env-file",
            str(self.deploy_dir / ".env"),
        ]

    def docker(self, args: list[str], check: bool = True, **kwargs: object) -> subprocess.CompletedProcess[str]:
        result = self.dockerenv.run_docker(args, environ=self.environment(), capture_output=True, check=False, **kwargs)
        if check and result.returncode != 0:
            raise AssertionError(f"docker {' '.join(args[:6])} rc={result.returncode}\n{(result.stdout + result.stderr)[-2000:]}")
        return result

    def compose(self, *args: str, check: bool = True, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return self.docker([*self.compose_args(), *args], check=check, **kwargs)

    def exec(self, service: str, *command: str, check: bool = True, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return self.compose("exec", "-T", service, *command, check=check, input=stdin)

    def published_port(self, service: str, port: int) -> int:
        out = self.compose("port", service, str(port)).stdout.strip()
        return int(out.rpartition(":")[2])

    def wait(self, what: str, check: object, seconds: float = 240, interval: float = 3) -> None:
        deadline = time.monotonic() + seconds
        last = ""
        while time.monotonic() < deadline:
            try:
                if check():  # type: ignore[operator]
                    return
            except AssertionError as error:
                last = str(error)
            time.sleep(interval)
        raise AssertionError(f"시간 안에 {what} 되지 않았다 {last}")

    def gateway_services(self) -> list[str]:
        return [f"sandbox-gw-{name}" for name in SERVICES]

    def start_test_services(self) -> None:
        self.compose("up", "-d", "--no-deps", "sandbox-upstream", *self.gateway_services(), "sandbox-client")

        def gateways_ready() -> bool:
            """영역 게이트웨이마다 인증서와 키가 생겼다(제품 compose 의 healthcheck 와 같은 명령)."""
            return all(self.exec(f"sandbox-gw-{name}", "sh", "-c", area_gateway.healthcheck_command(name, ACME_URL), check=False).returncode == 0 for name in SERVICES)

        self.wait("영역 게이트웨이가 사설 CA 에서 인증서를 받아 준비", gateways_ready)

    def recreate_gateways(self) -> None:
        """영역 게이트웨이와 그 인증서 볼륨(메모리)을 지우고 다시 만든다. 새 신뢰 목록으로 새 인증서를 받는다(서버를 다시 켠 것과 같다)."""
        self.compose("rm", "-sf", "sandbox-client", *self.gateway_services())
        for name in SERVICES:
            self.docker(["volume", "rm", "-f", f"{self.project}_sandbox-certs-{name}"])
        self.start_test_services()

    def create_users(self) -> None:
        script = (
            "set -e; K='/opt/keycloak/bin/kcadm.sh'; C='--config /tmp/kcadm.config'; "
            '$K config credentials $C --server http://localhost:8080 --realm master --user admin --password "$(cat /run/secrets/keycloak_admin_password)"; '
        )
        for user, role in (("staff-1", "staff"), ("clinician-1", "clinician")):
            script += (
                f"$K create users $C -r openit -s username={user} -s enabled=true -s emailVerified=true -s email={user}@example.org -s firstName=Test -s lastName=User; "
                f"$K set-password $C -r openit --username {user} --new-password {KC_PASSWORD}; "
                f"$K add-roles $C -r openit --uusername {user} --rolename {role}; "
            )
        self.exec("keycloak", "bash", "-c", script)

    def machine_secret(self, client: str) -> str:
        return (self.deploy_dir / "secrets" / "machine-clients" / client).read_text(encoding="utf-8").strip()

    # ------------------------------------------------------------ 정리
    def save_logs(self) -> Path:
        target = REPO / "platform" / ".pytest_cache" / f"sandbox-logs-{self.project}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        logs = self.compose("logs", "--no-color", "--tail", "200", check=False).stdout
        target.write_text(logs, encoding="utf-8")
        return target

    def teardown(self) -> list[str]:
        """이 프로젝트만 내린다(프로필 포함). 남은 컨테이너·볼륨·네트워크를 돌려준다(비어 있어야 한다)."""
        self.compose("down", "-v", "--remove-orphans", check=False)
        left: list[str] = []
        label = f"label=com.docker.compose.project={self.project}"
        for kind, command in (("container", ["ps", "-aq"]), ("volume", ["volume", "ls", "-q"]), ("network", ["network", "ls", "-q"])):
            out = self.docker([*command, "--filter", label], check=False).stdout.split()
            left += [f"{kind}:{item}" for item in out]
        shutil.rmtree(self.root, ignore_errors=True)
        return left
