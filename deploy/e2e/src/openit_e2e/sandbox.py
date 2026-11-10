"""샌드박스(D123): 제품을 그대로 복사한 두 번째 설치를 따로 띄워 그 안에서 시험한다. 제품 compose·설치 설정은 바꾸지 않는다.

- 리포의 deploy/·platform/·contracts/ 와 영역 폴더의 Dockerfile 을 `.e2e/work/<프로젝트>/` 로 복사하고 그 복사본의 `./deploy bootstrap` 으로 설치한다
  (신뢰의 뿌리 -> 레지스트리 -> 이미지 올리기 -> 기동). 영역 이미지는 이 엔진에 이미 빌드되어 있어야 한다(`./deploy build`).
- 샌드박스에서만 더하는 것: 설치 입력(기기 CA·허용 목록, 기계 호출자 표, 프로파일), compose 조각 `compose.e2e.yaml`(추론 엔진의 크기·모델 캐시·어댑터 마운트와
  게시 도구 서비스), Keycloak 시험 계정. compose 프로젝트 이름은 `openit-e2e-<무작위>` 다. 끝나면 이 프로젝트만 `down -v` 하고 남은 것이 0개인지 본다.
- docker 호출은 전부 dockerenv.run_docker 를 지난다(사용자 ~/.docker 를 읽지 않는다).
"""

from __future__ import annotations

import importlib.util
import json
import os
import secrets
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from . import devices
from .contract import StepFailure

REPO = Path(__file__).resolve().parents[4]
DEPLOY = REPO / "deploy"
WORK_ROOT = REPO / ".e2e" / "work"
LOG_ROOT = REPO / ".e2e" / "logs"
HF_HOME = REPO / ".e2e" / "hf"  # 호스트 도구(중립 어댑터)가 모델 구성 파일을 받는 캐시. 작업 트리 안 git 제외 폴더다
# 왜 이름 있는 볼륨: 기반 모델 가중치(수 GB~16GB)는 실행마다 받지 않고 다음 실행이 다시 쓴다. 프로젝트(openit-e2e-<무작위>) 밖이라 down -v 가 지우지 않는다
HF_VOLUME = "openit-e2e-hf-cache"
# 왜 이 목록: 상속받은 환경 변수를 통째로 넘기지 않는다(RUNTIME R9.1). 도구가 필요로 하는 것만 넘긴다
ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "UV_CACHE_DIR", "XDG_CACHE_HOME")
USERS = {"staff-e2e": "staff", "clinician-e2e": "clinician", "author-e2e": "author", "approver-e2e": "release-approver"}  # 계약 UserRole
HOSPITAL = "hospital"  # 기계 호출자 이름(클라이언트 ID machine-hospital), 역할 result-reader(MachineRole)
DEVICE_ID = "kiosk-e2e-01"
ADAPTERS_IN_CONTAINER = (
    "/e2e/adapters"  # 엔진과 게시 도구가 같은 경로로 읽는다(계약 ModelRuntimeEnv 의 어댑터 배치 규칙: 엔진이 같은 경로로 읽는다)
)
INPUTS_IN_CONTAINER = "/e2e/inputs"
OUT_IN_CONTAINER = "/e2e/out"
# 왜 780초: 제품 compose 가 엔진에 준 건강 확인 창(start_period 120초 + 15초 간격 40회 = 720초)에 여유 1분. 계약에 엔진 기동 상한은 없다(측정하지 않았다)
ENGINE_START_LIMIT = 780
READY_LIMIT = 120  # 왜 120초: 엔진이 건강해진 뒤 model-runtime 의 /readyz 가 엔진 모델 목록을 확인하는 데 필요한 시간. 측정하지 않았다(계약에 상한 없음)


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise StepFailure(f"모듈을 읽지 못했다: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def restricted_env() -> dict[str, str]:
    return {key: os.environ[key] for key in ENV_KEYS if key in os.environ}


def deployable_folders(root: Path) -> list[Path]:
    """./deploy 가 이미지 대상으로 보는 영역 폴더(services/·jobs/·web/ 아래 Dockerfile 이 있고 밑줄로 시작하지 않는 것). 틀 시험용 `_example*` 는 뺀다."""
    folders: list[Path] = []
    for base in ("services", "jobs", "web"):
        if (root / base).is_dir():
            folders += [
                child
                for child in sorted((root / base).iterdir())
                if child.is_dir() and (child / "Dockerfile").is_file() and not child.name.startswith("_")
            ]
    return folders


def image_name(folder: Path) -> str:
    """./deploy 의 대상 이름 규칙(web 은 web- 접두어)과 로컬 이미지 이름 openit/<대상>."""
    return f"openit/{'web-' if folder.parent.name == 'web' else ''}{folder.name}"


class Sandbox:
    def __init__(self, profile: str, base_model: str, engine_args: list[str]) -> None:
        self.profile = profile
        self.base_model = base_model
        self.engine_args = engine_args
        self.project = f"openit-e2e-{secrets.token_hex(3)}"
        self.root = WORK_ROOT / self.project
        self.deploy_dir = self.root / "deploy"
        self.state = self.root / "state"
        self.log_dir = LOG_ROOT / self.project
        self.dockerenv = load_module("e2e_dockerenv", DEPLOY / "dockerenv.py")
        self.org_ca: devices.Issued | None = None
        self.device: devices.Issued | None = None
        self.device_files: tuple[Path, Path] | None = None
        self.password = secrets.token_urlsafe(18)  # 시험 계정의 비밀번호. 이 샌드박스 안에서만 유효하고 출력하지 않는다

    # ------------------------------------------------------------ docker
    def docker(self, args: list[str], *, check: bool = True, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        result = self.dockerenv.run_docker(args, environ=restricted_env(), capture_output=True, check=False, **kwargs)
        if check and result.returncode != 0:
            raise StepFailure(f"docker {' '.join(args[:6])} rc={result.returncode}\n{(result.stdout + result.stderr)[-1500:]}")
        return result  # type: ignore[no-any-return]

    def compose_args(self) -> list[str]:
        generated = self.deploy_dir / "generated"
        return [
            "compose", "--project-name", self.project, "--project-directory", str(self.deploy_dir),
            "-f", str(self.deploy_dir / "compose.yaml"), "--env-file", str(self.deploy_dir / "env.example"),
            "--profile", "local-registry",
            "-f", str(generated / "compose.platform.yaml"),
            "--env-file", str(generated / "platform.env"), "--env-file", str(generated / "images.env"), "--env-file", str(generated / "areas.env"),
            "-f", str(self.deploy_dir / "compose.e2e.yaml"),
            "--profile", "inference-engine", "--profile", "e2e", "--profile", "tools",
            "--env-file", str(self.deploy_dir / ".env"),
        ]  # fmt: skip

    def compose(self, *args: str, check: bool = True, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return self.docker([*self.compose_args(), *args], check=check, **kwargs)

    def exec(self, service: str, *command: str, check: bool = True, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return self.compose("exec", "-T", service, *command, check=check, input=stdin)

    def published_port(self, service: str, port: int) -> int:
        out = self.compose("port", service, str(port)).stdout.strip()
        return int(out.rpartition(":")[2])

    # ------------------------------------------------------------ 점검
    def preflight(self) -> list[str]:
        """시작 전에 막는 조건. 문제 목록(비어 있으면 통과)."""
        problems: list[str] = []
        for folder in deployable_folders(REPO):
            name = image_name(folder)
            if self.docker(["image", "inspect", f"{name}:local"], check=False).returncode != 0:
                problems.append(f"이 엔진에 이미지 {name}:local 이 없다(./deploy build {name.removeprefix('openit/')})")
        if shutil.which("nvidia-smi") is None:
            problems.append("nvidia-smi 가 없다(추론 엔진에 GPU 가 필요하다)")
        return problems

    # ------------------------------------------------------------ 준비
    def prepare(self, hospital_secret_name: str = HOSPITAL) -> None:
        """리포의 사본을 만들고 설치 입력을 쓴다."""
        self.root.mkdir(parents=True)
        # 왜 폴더째: compose 가 deploy/ 아래 파일(postgres/init 등)을 마운트한다. 이 설치의 상태(비밀, pki, 생성 파일, .env)와 이 도구 자신(e2e/)은 복사하지 않는다
        skip = ("secrets", "pki", "generated", ".env", "backups", ".build-meta", "images.lock", "__pycache__", "e2e", ".venv")
        shutil.copytree(DEPLOY, self.deploy_dir, ignore=shutil.ignore_patterns(*skip))
        for name in ("src", "caddy", "monitoring"):
            shutil.copytree(REPO / "platform" / name, self.root / "platform" / name, ignore=shutil.ignore_patterns("__pycache__", ".venv"))
        contracts = self.root / "contracts"
        contracts.mkdir()
        shutil.copy2(REPO / "contracts" / "components.yaml", contracts / "components.yaml")
        shutil.copytree(REPO / "contracts" / "openapi", contracts / "openapi")
        # 왜 Dockerfile 만: ./deploy 는 폴더 목록으로 이미지 대상을 알고(area_targets) 이미지는 이 엔진의 openit/<대상>:local 을 올린다. 빌드는 하지 않는다
        for folder in deployable_folders(REPO):
            target = self.root / folder.relative_to(REPO)
            target.mkdir(parents=True)
            shutil.copy2(folder / "Dockerfile", target / "Dockerfile")
        self.state.mkdir()
        self._write_machine_callers()
        self._write_devices()
        for folder in ("adapters", "inputs", "out"):
            (self.state / folder).mkdir()
        (self.state / "out").chmod(0o777)  # 왜: 게시 도구(uid 10001)가 평가 보고서를 쓴다. 이 샌드박스 폴더는 끝나면 지워진다
        self._write_env()
        self._write_overlay()

    def _write_machine_callers(self) -> None:
        # 기본 표(survey-service 가 model-runtime 을 부름)에 병원 시스템(결과 당겨 가기)을 더한다(계약 MachineTokenTable)
        table = json.loads((DEPLOY / "machine-callers.json").read_text(encoding="utf-8"))
        table["tokens"].append({"client": HOSPITAL, "roles": ["result-reader"], "client_secret_file": f"/run/machine-clients/{HOSPITAL}"})
        (self.deploy_dir / "machine-callers.json").write_text(json.dumps(table, indent=2), encoding="utf-8")

    def _write_devices(self) -> None:
        self.org_ca = devices.make_ca("E2E Sandbox Device CA")
        from cryptography.hazmat.primitives import serialization

        (self.state / "device-ca.pem").write_bytes(self.org_ca.cert.public_bytes(serialization.Encoding.PEM))
        self.device = devices.make_device(self.org_ca, DEVICE_ID)
        devices.write_allowlist(self.state / "device-allowlist.json", {DEVICE_ID: self.device})
        (self.state / "devices").mkdir()
        self.device_files = self.device.write(self.state / "devices", DEVICE_ID)

    def _write_env(self) -> None:
        env = {
            "OPENIT_PROJECT_NAME": self.project,
            # 왜 false: ./deploy up 은 제품 compose 의 엔진 정의(기본 크기, 모델 캐시 없음, 인터넷 없음)로는 이 서버에서 엔진을 띄우지 못한다.
            # 엔진은 아래 compose.e2e.yaml 조각이 같은 정의에 크기·캐시·어댑터 마운트를 얹어 따로 띄운다(제품 설정을 바꾸지 않는다)
            "OPENIT_INFERENCE_ENGINE_LOCAL": "false",
            "OPENIT_MODEL_PROFILE": self.profile,
            "OPENIT_BASE_MODEL": self.base_model,
            "OPENIT_DEVICE_CA_CERTIFICATE_FILE": str(self.state / "device-ca.pem"),
            "OPENIT_DEVICE_ALLOWLIST_FILE": str(self.state / "device-allowlist.json"),
        }
        (self.deploy_dir / ".env").write_text("".join(f"{key}={value}\n" for key, value in env.items()), encoding="utf-8")

    def _write_overlay(self) -> None:
        product = yaml.safe_load((self.deploy_dir / "compose.yaml").read_text(encoding="utf-8"))
        engine = product["services"]["inference-engine"]
        overlay = {
            "services": {
                "inference-engine": {
                    # 제품 정의의 인자에 이 GPU 에 맞는 크기 인자를 더한다(replace 가 아니라 같은 목록의 뒤에 붙인다)
                    "command": [*engine["command"], *self.engine_args],
                    "environment": {
                        "HF_HUB_OFFLINE": "1"
                    },  # 모델은 아래 볼륨에서만 읽는다(엔진 컨테이너는 내부 네트워크라 허브에 닿지 않는다)
                    "volumes": [f"{HF_VOLUME}:/root/.cache/huggingface", f"{self.state / 'adapters'}:{ADAPTERS_IN_CONTAINER}:ro"],
                },
                "e2e-publisher": {
                    "profiles": ["e2e"],
                    "image": "${OPENIT_IMAGE_MODEL_RUNTIME}",
                    "pull_policy": "never",
                    "entrypoint": [
                        "/app/.venv/bin/package-publish"
                    ],  # 영역 이미지에 들어 있는 게시 도구(model-runtime pyproject 의 project.scripts)
                    "read_only": True,
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                    "tmpfs": ["/tmp", "/work:uid=10001,gid=10001,mode=0700"],  # noqa: S108 (컨테이너 안 tmpfs)
                    "secrets": ["registry_credentials"],
                    "volumes": [
                        "${OPENIT_TRUST_LIST_FILE}:/etc/openit/trust-list.pem:ro",
                        f"{self.state / 'adapters'}:{ADAPTERS_IN_CONTAINER}:ro",
                        f"{self.state / 'inputs'}:{INPUTS_IN_CONTAINER}:ro",
                        f"{self.state / 'out'}:{OUT_IN_CONTAINER}",
                    ],
                    "networks": ["backend", "model-runtime-area"],  # 레지스트리(backend)와 추론 엔진(영역 네트워크)에 닿는다
                },
            },
            "volumes": {HF_VOLUME: {"external": True}},
        }
        (self.deploy_dir / "compose.e2e.yaml").write_text(yaml.safe_dump(overlay, sort_keys=False, allow_unicode=True), encoding="utf-8")

    # ------------------------------------------------------------ 설치와 기동
    def run_deploy(self, *args: str, log: str, timeout: int = 1800) -> None:
        """샌드박스 사본의 ./deploy 를 실행한다. 출력은 로그 파일에 남기고 실패하면 끝부분을 보인다."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with (self.log_dir / log).open("w", encoding="utf-8") as handle:
            result = subprocess.run(
                [str(self.deploy_dir / "deploy"), *args],
                cwd=self.root,
                env=restricted_env(),
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout,
            )
        if result.returncode != 0:
            tail = (self.log_dir / log).read_text(encoding="utf-8", errors="replace")[-2500:]
            raise StepFailure(f"./deploy {' '.join(args)} rc={result.returncode}\n{tail}")

    def vllm_image(self) -> str:
        product = yaml.safe_load((self.deploy_dir / "compose.yaml").read_text(encoding="utf-8"))
        return str(product["services"]["inference-engine"]["image"])

    def ensure_model_cache(self) -> str:
        """기반 모델의 가중치를 이름 있는 볼륨에 둔다(있으면 받지 않는다). 받은 것과 재사용한 것을 알린다."""
        image = self.vllm_image()
        code = "import sys; from huggingface_hub import snapshot_download; snapshot_download(sys.argv[1], local_files_only=True)"
        base = [
            "run",
            "--rm",
            "--entrypoint",
            "python3",
            "-v",
            f"{HF_VOLUME}:/root/.cache/huggingface",
            "-e",
            "HF_HOME=/root/.cache/huggingface",
            image,
        ]
        if self.docker([*base, "-c", code, self.base_model], check=False).returncode == 0:
            return "재사용"
        self.docker([*base, "-c", code.replace(", local_files_only=True", ""), self.base_model], timeout=7200)
        return "받음"

    def create_users(self) -> None:
        """Keycloak 시험 계정(직원·의사·문항 작성자·승인자)을 이 샌드박스 안에 만든다. 비밀번호는 표준 입력으로 넘긴다."""
        script = (
            "set -e; read -r PW; K='/opt/keycloak/bin/kcadm.sh'; C='--config /tmp/kcadm.config'; "
            '$K config credentials $C --server http://localhost:8080 --realm master --user admin --password "$(cat /run/secrets/keycloak_admin_password)"; '
        )
        for user, role in USERS.items():
            script += (
                f"$K create users $C -r openit -s username={user} -s enabled=true -s emailVerified=true -s email={user}@example.org -s firstName=E2E -s lastName=User; "
                f'$K set-password $C -r openit --username {user} --new-password "$PW"; '
                f"$K add-roles $C -r openit --uusername {user} --rolename {role}; "
            )
        self.exec("keycloak", "bash", "-c", script, stdin=self.password + "\n")

    def install_value(self, key: str) -> str:
        """설치 설정 값: deploy/env.example 의 기본값을 deploy/.env 가 덮는다(compose 와 ./deploy 가 읽는 방식과 같다)."""
        value = ""
        for name in ("env.example", ".env"):
            for line in (self.deploy_dir / name).read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{key}="):
                    value = line.partition("=")[2].strip()
        return value

    def machine_secret(self, caller: str) -> str:
        return (self.deploy_dir / "secrets" / "machine-clients" / caller).read_text(encoding="utf-8").strip()

    def start_engine(self) -> None:
        self.compose("up", "-d", "--no-deps", "--wait", "--wait-timeout", str(ENGINE_START_LIMIT), "inference-engine")

    def wait_until(self, what: str, check: Callable[[], bool], seconds: float, interval: float = 3) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if check():
                return
            time.sleep(interval)
        raise StepFailure(f"{seconds:.0f}초 안에 {what} 되지 않았다")

    def wait_model_runtime_ready(self) -> None:
        """model-runtime 의 /readyz 가 200(엔진이 프로파일의 기반 모델을 서빙한다)이 될 때까지. 컨테이너 안에서 본다(D123: 제품 안의 일은 exec)."""
        probe = "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=3).status == 200 else 1)"

        def ready() -> bool:
            return self.exec("model-runtime", "python", "-c", probe, check=False).returncode == 0

        self.wait_until("model-runtime 의 /readyz 가 200 이", ready, READY_LIMIT)

    def publish(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return self.compose("run", "--rm", "--no-deps", "-T", "e2e-publisher", *args, check=False, timeout=1800)

    # ------------------------------------------------------------ 진단과 정리
    def save_diagnostics(self) -> Path:
        """정리하기 전에 상태와 로그를 남긴다(실패한 단계를 다시 볼 수 있게)."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        (self.log_dir / "ps.txt").write_text(self.compose("ps", "--all", check=False).stdout, encoding="utf-8")
        (self.log_dir / "compose.log").write_text(self.compose("logs", "--no-color", "--tail", "300", check=False).stdout, encoding="utf-8")
        return self.log_dir

    def teardown(self) -> list[str]:
        """이 프로젝트만 내린다(프로필 포함). 남은 컨테이너·볼륨·네트워크를 돌려준다(비어 있어야 한다)."""
        if (self.deploy_dir / "generated" / "areas.env").is_file():
            self.compose("down", "-v", "--remove-orphans", check=False)
        left: list[str] = []
        label = f"label=com.docker.compose.project={self.project}"
        # 왜 상표로 한 번 더: 설치가 중간에 실패해 compose 파일 묶음이 완성되지 않았으면 위의 down 을 못 한다. 이 프로젝트의 상표가 붙은 것만 ID 로 지운다(다른 프로젝트는 건드리지 않는다)
        for kind, listing, removal in (
            ("container", ["ps", "-aq"], ["rm", "-fv"]),
            ("network", ["network", "ls", "-q"], ["network", "rm"]),
            ("volume", ["volume", "ls", "-q"], ["volume", "rm", "-f"]),
        ):
            ids = self.docker([*listing, "--filter", label], check=False).stdout.split()
            if ids:
                self.docker([*removal, *ids], check=False)
            left += [f"{kind}:{item}" for item in self.docker([*listing, "--filter", label], check=False).stdout.split()]
        shutil.rmtree(self.root, ignore_errors=True)
        return left
