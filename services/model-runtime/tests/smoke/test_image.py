"""이미지 스모크(ADR 0004). `tools/smoke service model-runtime` 이 부른다.

docker 호출은 호출자가 준비한 격리 환경(DOCKER_CONFIG, DOCKER_HOST)만 쓴다.
호스트 포트는 Docker 가 배정한다(고정 포트 없음).
컨테이너에는 시험용 PKI·토큰·자격 파일을 읽기 전용으로 마운트하고, 영역 사이 mTLS 로 실제 호출한다.
컨테이너 이름에는 openit-mr 를 넣고 끝나면 자기가 만든 것만 ID 로 지운다.
"""

import json
import os
import ssl
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Generator
from dataclasses import dataclass

import pytest

from fakes.pki import Pki, make_pki
from support import ISSUER, MACHINE_TOKEN

pytestmark = pytest.mark.smoke


def _docker_env() -> dict[str, str]:
    if not os.environ.get("DOCKER_CONFIG"):
        pytest.fail("DOCKER_CONFIG 가 없다. tools/smoke 로 실행해 격리 설정을 받는다(사용자 ~/.docker 를 쓰지 않는다)")
    keep = ("PATH", "DOCKER_CONFIG", "DOCKER_HOST")
    return {key: os.environ[key] for key in keep if key in os.environ}


def _docker(*args: str) -> str:
    result = subprocess.run(["docker", *args], env=_docker_env(), capture_output=True, text=True, check=False)  # noqa: S603, S607
    if result.returncode != 0:
        pytest.fail(f"docker {args[0]} 실패 rc={result.returncode}: {result.stderr[-500:]}")
    return result.stdout.strip()


@dataclass(frozen=True)
class Running:
    cid: str
    endpoint: str
    pki: Pki


@pytest.fixture(scope="module")
def container(tmp_path_factory: pytest.TempPathFactory) -> Generator[Running]:
    image = os.environ.get("OPENIT_SMOKE_IMAGE")
    if not image:
        pytest.fail("OPENIT_SMOKE_IMAGE 가 없다. tools/smoke 로 실행한다")
    tmp = tmp_path_factory.mktemp("smoke")
    pki = make_pki(tmp / "pki")
    token_file = tmp / "inference-caller.token"
    token_file.write_text(MACHINE_TOKEN + "\n", encoding="utf-8")
    table = tmp / "machine-tokens.json"
    table.write_text(
        json.dumps(
            {
                "tokens": [
                    {"client": "survey-service", "roles": ["inference-caller"], "token_file": "/run/secrets/token"}
                ]
            }
        ),
        encoding="utf-8",
    )
    credentials = tmp / "registry.credentials"
    credentials.write_text("reader:password\n", encoding="utf-8")
    cache = tmp / "cache"
    cache.mkdir()
    for path in (pki.root, pki.server_cert, pki.server_key, token_file, table, credentials):
        path.chmod(0o644)  # 시험용 값이다. 컨테이너의 비 root 사용자(10001)가 읽는다
    cache.chmod(0o777)
    env = {
        "OPENIT_ROOT_CERTIFICATE_FILE": "/run/pki/root.pem",
        "OPENIT_TLS_CERTIFICATE_FILE": "/run/pki/server.pem",
        "OPENIT_TLS_PRIVATE_KEY_FILE": "/run/pki/server.key",
        "OPENIT_LISTEN_PORT": "8443",
        "OPENIT_OIDC_ISSUER_URL": ISSUER,
        "OPENIT_OIDC_AUDIENCE": "model-runtime",
        "OPENIT_REGISTRY_URL": "https://registry.invalid",
        "OPENIT_REGISTRY_REPOSITORY": "openit/model-package",
        "OPENIT_REGISTRY_CREDENTIALS_FILE": "/run/secrets/registry",
        "OPENIT_MACHINE_TOKENS_FILE": "/run/config/machine-tokens.json",
        "OPENIT_MODEL_PROFILE": "smoke",
        "OPENIT_MODEL_CACHE_DIR": "/var/lib/openit/model-runtime",
    }
    name = f"openit-mr-smoke-{uuid.uuid4().hex[:8]}"
    args = [
        "run",
        "-d",
        "--name",
        name,
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "-p",
        "127.0.0.1::8443",
    ]
    for key, value in env.items():
        args += ["-e", f"{key}={value}"]
    mounts = [
        (pki.root.parent, "/run/pki"),
        (token_file, "/run/secrets/token"),
        (credentials, "/run/secrets/registry"),
        (table, "/run/config/machine-tokens.json"),
    ]
    for source, target in mounts:
        args += ["-v", f"{source}:{target}:ro"]
    args += ["-v", f"{cache}:/var/lib/openit/model-runtime", image]
    cid = _docker(*args)
    try:
        endpoint = _docker("port", cid, "8443/tcp").splitlines()[0]
        yield Running(cid, endpoint, pki)
    finally:
        # 진단 수단을 지우지 않는다: 실패했으면 로그를 먼저 남긴다. 자기가 만든 컨테이너만 ID 로 지운다
        subprocess.run(["docker", "logs", "--tail", "50", cid], env=_docker_env(), check=False)  # noqa: S603, S607
        subprocess.run(["docker", "rm", "-f", cid], env=_docker_env(), check=False, capture_output=True)  # noqa: S603, S607


def _context(pki: Pki, with_client_certificate: bool) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=str(pki.root))
    context.check_hostname = (
        False  # 시험용 서버 인증서는 localhost·127.0.0.1 이름이고 컨테이너 포트는 호스트가 배정했다
    )
    if with_client_certificate:
        context.load_cert_chain(str(pki.client_cert), str(pki.client_key))
    return context


def _get(
    box: Running, path: str, token: str | None = MACHINE_TOKEN, certificate: bool = True
) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        f"https://{box.endpoint}{path}", headers={"Authorization": f"Bearer {token}"} if token else {}
    )
    deadline = time.monotonic() + 40
    while True:
        try:
            with urllib.request.urlopen(request, context=_context(box.pki, certificate), timeout=3) as response:  # noqa: S310
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())
        except (urllib.error.URLError, ConnectionError, TimeoutError, ssl.SSLError):
            if not certificate:
                raise
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)


def test_container_becomes_healthy_by_its_own_healthcheck(container: Running) -> None:
    deadline = time.monotonic() + 60
    state = ""
    while time.monotonic() < deadline:
        state = _docker("inspect", "--format", "{{.State.Health.Status}}", container.cid)
        if state == "healthy":
            break
        time.sleep(1)
    assert state == "healthy"


def test_runs_as_non_root_with_labels(container: Running) -> None:
    assert _docker("exec", container.cid, "id", "-u") == "10001"
    labels = json.loads(_docker("inspect", "--format", "{{json .Config.Labels}}", container.cid))
    assert (
        labels["io.openit.service"] == "model-runtime" and json.loads(labels["io.openit.inputs"])["run_as_uid"] == 10001
    )


def test_healthz_over_mtls(container: Running) -> None:
    status, body = _get(container, "/healthz", token=None)
    assert status == 200 and body == {"status": "pass", "service": "model-runtime"}


def test_connection_without_client_certificate_is_refused(container: Running) -> None:
    _get(container, "/healthz", token=None)  # 서버가 뜬 것을 먼저 확인한다
    with pytest.raises((urllib.error.URLError, ssl.SSLError, ConnectionError)):
        _get(container, "/healthz", token=None, certificate=False)


def test_readyz_names_only_the_failed_check(container: Running) -> None:
    status, body = _get(container, "/readyz", token=None)
    # 추론 엔진 컨테이너는 이 스모크에 없다. 저장 폴더는 쓸 수 있다
    assert status == 503 and body["detail"] == "준비되지 않은 점검: engine"


def test_model_status_with_machine_token_reads_the_state_folder(container: Running) -> None:
    assert _get(container, "/v1/model-status") == (200, {"state": "NOT_LOADED"})
    assert _get(container, "/v1/model-status", token="wrong")[0] == 401  # noqa: S106
    assert _get(container, "/v1/model-status", token=None)[0] == 401
