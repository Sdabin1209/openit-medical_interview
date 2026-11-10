"""이미지 스모크(ADR 0004). `tools/smoke service survey-service` 가 부른다.

이미지를 읽기 전용 루트·비 root·모든 권한 제거로 띄우고, 영역 전용 PostgreSQL 16 컨테이너와 같은 사설 네트워크에 둔다.
비밀은 파일로 마운트한다(D84). 컨테이너·네트워크 이름에 openit-ss 를 넣고, 끝나면 자기가 만든 것만 ID 로 지운다.
호스트 포트는 Docker 가 배정한다(고정 포트 없음). docker 호출은 호출자가 준비한 격리 환경(DOCKER_CONFIG, DOCKER_HOST)만 쓴다.
"""

import datetime
import json
import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from tests.support.postgres import IMAGE as POSTGRES_IMAGE

pytestmark = pytest.mark.smoke
ROOT = Path(__file__).resolve().parents[2]


def _docker_env() -> dict[str, str]:
    if not os.environ.get("DOCKER_CONFIG"):
        pytest.fail("DOCKER_CONFIG 가 없다. tools/smoke 로 실행해 격리 설정을 받는다(사용자 ~/.docker 를 쓰지 않는다)")
    keep = ("PATH", "DOCKER_CONFIG", "DOCKER_HOST")
    return {key: os.environ[key] for key in keep if key in os.environ}


def _docker(*args: str, check: bool = True) -> str:
    result = subprocess.run(  # noqa: S603
        ["docker", *args],  # noqa: S607
        env=_docker_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        pytest.fail(f"docker {args[0]} 실패 rc={result.returncode}: {result.stderr[-500:]}")
    return result.stdout.strip()


def _logs(cid: str) -> str:
    """컨테이너 로그(표준 출력과 표준 오류)의 끝부분. 실패 메시지에 싣는다."""
    done = subprocess.run(  # noqa: S603
        ["docker", "logs", "--tail", "40", cid],  # noqa: S607
        env=_docker_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout + done.stderr


def _root_certificate() -> bytes:
    """시험용 자체 서명 루트 인증서(PEM). 서비스는 이것을 나가는 호출(이웃, 발급자)의 신뢰 앵커로 읽는다."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "openit-smoke-root")])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return certificate.public_bytes(serialization.Encoding.PEM)


def _secret(folder: Path, name: str, content: str | bytes) -> str:
    path = folder / name
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    path.chmod(0o644)  # 왜 644: 컨테이너의 비 root 사용자(10001)가 읽는다. 폴더는 시험이 끝나면 지운다
    return f"/run/secrets/{name}"


@pytest.fixture(scope="module")
def container() -> Iterator[str]:
    image = os.environ.get("OPENIT_SMOKE_IMAGE")
    if not image:
        pytest.fail("OPENIT_SMOKE_IMAGE 가 없다. tools/smoke 로 실행한다")
    suffix = uuid.uuid4().hex[:8]
    network, database, name = (
        f"openit-ss-smoke-net-{suffix}",
        f"openit-ss-smoke-pg-{suffix}",
        f"openit-ss-smoke-{suffix}",
    )
    password = secrets.token_hex(12)
    folder = ROOT / ".smoke-tmp" / suffix
    folder.mkdir(parents=True)
    folder.chmod(0o755)
    key = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    machine_secret = _secret(folder, "machine_hospital_secret", secrets.token_hex(16))
    files = {
        "OPENIT_DATABASE_PASSWORD_FILE": _secret(folder, "database_password", password),
        "OPENIT_MODEL_RUNTIME_CLIENT_SECRET_FILE": _secret(
            folder, "model_runtime_client_secret", secrets.token_hex(16)
        ),
        "OPENIT_VAPID_PRIVATE_KEY_FILE": _secret(folder, "vapid_private_key", key),
        "OPENIT_TLS_PRIVATE_KEY_FILE": _secret(folder, "tls_private_key", "unused"),
        "OPENIT_TLS_CERTIFICATE_FILE": _secret(folder, "tls_certificate", "unused"),
        "OPENIT_ROOT_CERTIFICATE_FILE": _secret(folder, "root_certificate", _root_certificate()),
        "OPENIT_MACHINE_TOKENS_FILE": _secret(
            folder,
            "machine_tokens.json",
            json.dumps(
                {"tokens": [{"client": "hospital", "roles": ["result-reader"], "client_secret_file": machine_secret}]}
            ),
        ),
    }
    env = {
        "OPENIT_OIDC_ISSUER_URL": "https://platform/realms/openit",
        "OPENIT_OIDC_AUDIENCE": "survey-service",
        "OPENIT_LISTEN_PORT": "8080",
        "OPENIT_DATABASE_URL": f"postgresql://postgres@{database}:5432/postgres",
        "OPENIT_MODEL_RUNTIME_URL": "https://model-runtime",
        "OPENIT_VAPID_SUBJECT": "mailto:ops@example.org",
        "OPENIT_EGRESS_PROXY": "http://127.0.0.1:3128",
        **files,
    }
    created: list[str] = []
    try:
        _docker("network", "create", network)
        created.append(network)
        _docker(
            "run", "-d", "--name", database, "--network", network, "-e", f"POSTGRES_PASSWORD={password}", "--tmpfs", "/var/lib/postgresql/data",
            POSTGRES_IMAGE,
        )  # fmt: skip
        deadline = time.monotonic() + 60
        while "accepting" not in _docker(
            "exec", database, "pg_isready", "-U", "postgres", "-h", "127.0.0.1", check=False
        ):
            if time.monotonic() > deadline:
                pytest.fail("스모크용 PostgreSQL 이 준비되지 않았다")
            time.sleep(0.5)
        time.sleep(1.5)  # 초기화 중 임시 서버가 먼저 답하고 재시작한다
        args = ["run", "-d", "--name", name, "--network", network, "--read-only", "--cap-drop", "ALL"]
        args += ["--security-opt", "no-new-privileges", "-p", "127.0.0.1::8080", "-v", f"{folder}:/run/secrets:ro"]
        for key_name, value in env.items():
            args += ["-e", f"{key_name}={value}"]
        cid = _docker(*args, image)
        time.sleep(3)  # 왜: 시작 직후 설정 오류로 죽으면 로그를 실패 메시지에 싣는다(진단 수단을 남긴다)
        if _docker("inspect", "-f", "{{.State.Running}}", cid) != "true":
            pytest.fail(f"이미지가 시작하지 못했다. 로그:\n{_logs(cid)}")
        yield cid
    finally:
        # 진단 수단을 지우지 않는다: 로그를 먼저 남기고 자기가 만든 것만 지운다
        subprocess.run(["docker", "logs", "--tail", "50", name], env=_docker_env(), check=False)  # noqa: S603, S607
        for target in (name, database):
            subprocess.run(["docker", "rm", "-f", target], env=_docker_env(), check=False, capture_output=True)  # noqa: S603, S607
        for target in created:
            subprocess.run(["docker", "network", "rm", target], env=_docker_env(), check=False, capture_output=True)  # noqa: S603, S607
        for path in folder.iterdir():
            path.unlink()
        folder.rmdir()


def _url(cid: str, path: str) -> str:
    mapping = _docker("port", cid, "8080/tcp").splitlines()[0]
    return f"http://{mapping}{path}"


def _get(cid: str, path: str, headers: dict[str, str] | None = None) -> tuple[int, object]:
    deadline = time.monotonic() + 60
    while True:
        try:
            request = urllib.request.Request(_url(cid, path), headers=headers or {})  # noqa: S310
            with urllib.request.urlopen(request, timeout=3) as response:  # noqa: S310
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code == 503 and time.monotonic() < deadline:  # 시작 중(마이그레이션)이면 준비될 때까지 기다린다
                time.sleep(0.5)
                continue
            return error.code, json.loads(error.read())
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)


def test_healthz(container: str) -> None:
    status, body = _get(container, "/healthz")
    assert status == 200
    assert isinstance(body, dict) and body["status"] == "pass" and body["service"] == "survey-service"


def test_readyz_has_a_migrated_database(container: str) -> None:
    status, body = _get(container, "/readyz")
    assert status == 200
    assert isinstance(body, dict) and body["checks"] == [{"name": "database", "status": "pass"}]


def test_device_request_reaches_the_service(container: str) -> None:
    header = {"X-Forwarded-Client-Cert": 'Subject="CN=kiosk-01"'}
    status, body = _get(container, "/v1/questionnaires", header)
    assert (status, body) == (200, {"questionnaires": []})
    status, body = _get(container, "/v1/questionnaires")
    assert status == 401


def test_runs_as_non_root(container: str) -> None:
    assert _docker("exec", container, "id", "-u") != "0"


def test_root_filesystem_is_read_only(container: str) -> None:
    mode = _docker("inspect", "-f", "{{.HostConfig.ReadonlyRootfs}}", container)
    assert mode == "true"


def test_image_labels(container: str) -> None:
    labels = json.loads(_docker("inspect", "-f", "{{json .Config.Labels}}", container))
    assert labels["io.openit.service"] == "survey-service" and labels["io.openit.contracts"]
    # 라벨의 원본은 영역 폴더의 선언 파일이다(deploy build 가 인자로 넘긴다, ADR 0016)
    for label, filename in (("jobs", "jobs.json"), ("exposure", "exposure.json"), ("inputs", "inputs.json")):
        assert json.loads(labels[f"io.openit.{label}"]) == json.loads((ROOT / filename).read_text(encoding="utf-8"))
