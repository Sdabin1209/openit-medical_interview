"""샌드박스(D123): 제품을 그대로 복사한 두 번째 설치를 따로 띄운다. 제품 compose·설정에는 시험용 문이 없다.

- 리포의 deploy/·platform/·contracts/ 를 임시 폴더로 복사하고 그 복사본의 ./deploy bootstrap 으로 설치한다(신뢰의 뿌리 -> 레지스트리 -> 기동).
- 시험에 필요한 것은 설치 입력(노출 선언, 기기 허용 목록, 기계 호출자 표, 기기 CA)과 compose 에 더하는 시험 서비스뿐이다.
  시험 서비스: 평문 에코 상류(가짜 영역 서비스. 영역 서비스 컨테이너의 자리에서 영역 전용 네트워크에 서비스 이름의 별칭으로 선다), 클라이언트.
  영역 게이트웨이는 제품 compose 의 것(<영역>-gateway, platform ADR 0007)을 그대로 쓴다. 영역 서비스·영역 DB 는 이 시험의 대상이 아니라 사본에서 끈다(아래 DISABLED_AREA_SERVICES).
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

import yaml
from cryptography.hazmat.primitives import serialization

from openit_platform import area_gateway

from .devices import Issued, make_ca, make_device

REPO = Path(__file__).resolve().parents[3]

# 상태를 보는 빈도. 통과 조건이 아니다(wait 설명). 측정하지 않았다
STATE_POLL_SECONDS = 1.0
# 컨테이너 기동·인증서 발급이 끝나기를 기다리는 상한. 멈춘 기동을 끝내는 값이며 측정하지 않았다(기존 값 유지)
STARTUP_LIMIT_SECONDS = 240
# 허용 목록을 바꾼 `up` 이 입구에 반영되기를 기다리는 상한. 측정하지 않았다(기존 값 유지)
RELOAD_LIMIT_SECONDS = 60
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


# 왜 끄는가: platform 시험에는 영역 서비스 이미지가 없다(이미지 빌드는 영역의 일이다). 영역 서비스와 그 DB 는 시험용 프로필로 꺼 사본에서만 뺀다.
# 제품 compose 는 바꾸지 않는다(D123). ./deploy 는 자기 compose 파일만 읽어 별도 조각을 합칠 수 없어서 사본을 고친다
DISABLED_AREA_SERVICES = ("survey-db", "survey-service", "model-runtime", "admin-console", "kiosk-frontend")
OFF_PROFILE = "sandbox-off"
# 영역 서비스가 서 영역 전용 네트워크(제품 compose 의 이름)
AREA_NETWORKS = {name: f"{name}-area" for name in SERVICES}


def gateway_names() -> list[str]:
    return [f"{name}-gateway" for name in SERVICES]


def patched_compose(text: str) -> str:
    """제품 compose 사본에서 영역 서비스를 끄고(프로필) oauth2-proxy 제공자를 일반 oidc 로 한다(platform ADR 0004: 반영된 뒤에는 치환이 아무것도 바꾸지 않는다)."""
    document = yaml.safe_load(text.replace("--provider=keycloak-oidc", "--provider=oidc"))
    for name in DISABLED_AREA_SERVICES:
        document["services"][name]["profiles"] = [OFF_PROFILE]
    for name in gateway_names():
        # 왜 상류 이름을 바꾸나: 제품 compose 의 OPENIT_AREA_UPSTREAM(<서비스 이름>:8080)은 게이트웨이 자신의 backend 별칭(서비스 이름)과 같아서
        # 샌드박스에서 게이트웨이가 자기 자신으로 풀렸다(getent: 게이트웨이의 backend IP, 연결 거절). 시험 상류의 고유한 이름으로 부른다(보고: 제품 쪽 변경 필요)
        document["services"][name]["environment"]["OPENIT_AREA_UPSTREAM"] = f"sandbox-upstream:{UPSTREAM_PORT}"
    return yaml.dump(document, Dumper=NoAliasDumper, sort_keys=False, allow_unicode=True)


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:  # 왜: 같은 목록이 YAML 앵커로 나가면 사람이 읽기 어렵다
        return True


def compose_text() -> str:
    area_networks = "".join(f"      {AREA_NETWORKS[name]}:\n        aliases: [{name}]\n" for name in SERVICES)
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
    networks:
{area_networks}  sandbox-client:
    image: smallstep/step-ca:0.28.4@sha256:0f88382ac5af5c6b7bbba0c6e8fcefef52aee6f22ea364df8e02a09ffd0d22f3
    read_only: true
    user: "10001:10001"
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    entrypoint: ["sleep", "infinity"]
    volumes:
      - ${{OPENIT_TRUST_LIST_FILE}}:/etc/openit/trust-list.pem:ro
      - {CLIENT_CERT_AREA}-certs:{area_gateway.AREA_CERTS}:ro
    networks: [backend]
"""


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
        compose = self.deploy_dir / "compose.yaml"
        compose.write_text(patched_compose(compose.read_text(encoding="utf-8")), encoding="utf-8")
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
            "OPENIT_INFERENCE_ENGINE_LOCAL": "false",  # 추론 엔진은 이 시험의 대상이 아니다(서빙 GPU 서버 배치)
            # 리프 수명은 기본값을 쓴다: 갱신이 일어나는 시간은 재지 않는다(외부 제품의 동작, platform ADR 0008). 갱신 설정은 단위 시험이 생성물로 본다
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
            str(generated / "images.env"),
            "--env-file",
            str(generated / "areas.env"),
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

    def wait(self, what: str, check: object, limit_seconds: float) -> None:
        """상태가 될 때까지 본다. 시간은 판정 기준이 아니라 멈춘 기동을 끝내는 상한(limit_seconds)이다.

        왜 간격을 두고 본다: Prometheus·Envoy·step-ca 에는 상태 변화를 밀어 주는 표준 수단이 없다. 간격은 상태를 보는 빈도일 뿐 통과 조건이 아니다.
        """
        deadline = time.monotonic() + limit_seconds
        last = ""
        while True:
            try:
                if check():  # type: ignore[operator]
                    return
            except AssertionError as error:
                last = str(error)
            if time.monotonic() >= deadline:
                break
            time.sleep(STATE_POLL_SECONDS)
        raise AssertionError(f"상한({limit_seconds:g}초) 안에 {what} 되지 않았다 {last}")

    def start_test_services(self) -> None:
        # 영역 게이트웨이는 제품 compose 의 것이다(bootstrap 이 이미 띄웠다). 시험용 상류와 클라이언트를 더한다
        self.compose("up", "-d", "--no-deps", "sandbox-upstream", "sandbox-client", *gateway_names())

        def gateways_ready() -> bool:
            """영역 게이트웨이마다 인증서와 키가 생겼다(제품 compose 의 healthcheck 와 같은 명령)."""
            return all(self.exec(f"{name}-gateway", "sh", "-c", area_gateway.healthcheck_command(name, ACME_URL), check=False).returncode == 0 for name in SERVICES)

        self.wait("영역 게이트웨이가 사설 CA 에서 인증서를 받아 준비", gateways_ready, STARTUP_LIMIT_SECONDS)

    def recreate_gateways(self) -> None:
        """영역 게이트웨이와 그 인증서 볼륨(메모리)을 지우고 다시 만든다. 새 신뢰 목록으로 새 인증서를 받는다(서버를 다시 켠 것과 같다)."""
        self.compose("rm", "-sf", "sandbox-client", *gateway_names())
        for name in SERVICES:
            self.docker(["volume", "rm", "-f", f"{self.project}_{name}-certs"])
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
