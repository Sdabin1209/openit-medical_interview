"""이웃·IdP 호출(link): model-runtime 클라이언트, JWKS, 기계 토큰 표."""

import asyncio
import base64
import contextlib
import datetime
import json
import os
import socket
import ssl
import threading
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID
from tests.support.harness import DIGEST
from tests.unit.test_settings_health import REQUIRED

from survey_service.contract.models import ExtractionRequest, ResponseGenerationRequest
from survey_service.link.auth import JwksKeys, load_machine_callers
from survey_service.link.machine_token import MachineTokenSource, TokenError
from survey_service.link.model_client import HttpModelClient
from survey_service.link.problem import ApiError
from survey_service.link.tls import ClientTls
from survey_service.settings import limits_of, load_env
from survey_service.types import ModelCallError, ModelCallFailure

pytestmark = pytest.mark.anyio
LIMITS = limits_of(load_env(REQUIRED))


def extraction_request() -> ExtractionRequest:
    return ExtractionRequest.model_validate(
        {
            "runtime_contract_version": 1,
            "question_id": "Q1",
            "current_question": "질문",
            "user_utterance": "네",
            "slots": [],
            "flow": {"start_item": "Q1", "rules": [{"item_id": "Q1", "branches": [{"next_item": "END"}]}]},
            "fields": [{"item_id": "Q1", "field_name": "answer", "data_type": "boolean"}],
        }
    )


class StaticTokens(MachineTokenSource):
    """발급자를 부르지 않고 정해진 토큰을 주는 시험용 토큰 받개."""

    def __init__(self, value: str = "jwt-for-tests") -> None:
        self.value, self.invalidated = value, 0

    async def token(self) -> str:
        return self.value

    def invalidate(self) -> None:
        self.invalidated += 1


def client(handler: httpx.MockTransport, tokens: MachineTokenSource | None = None) -> HttpModelClient:
    return HttpModelClient(
        "https://model-runtime", tokens or StaticTokens(), LIMITS, egress_proxy=None, tls=None, transport=handler
    )


async def test_model_client_posts_contract_bodies_with_bearer_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/extractions":
            return httpx.Response(
                200, json={"package_digest": DIGEST, "output": {"values": [], "action": "NEXT", "next_item": "END"}}
            )
        return httpx.Response(200, json={"package_digest": DIGEST, "text": "문장"})

    model = client(httpx.MockTransport(handler))
    extracted = await model.extract(extraction_request())
    responded = await model.respond(
        ResponseGenerationRequest.model_validate(
            {
                "runtime_contract_version": 1,
                "action": "START",
                "next": {"type": "NEXT", "question_id": "Q1", "text": "질문"},
            }
        )
    )
    assert extracted.output.action.value == "NEXT" and responded.text.root == "문장"
    assert [r.url.path for r in seen] == ["/v1/extractions", "/v1/responses"]
    assert all(r.headers["authorization"] == "Bearer jwt-for-tests" for r in seen)
    assert "null" not in seen[0].content.decode()  # 값이 없는 칸은 싣지 않는다
    await model.close()


@pytest.mark.parametrize("status", [400, 409, 503, 500])
async def test_model_errors_become_unavailable(status: int) -> None:
    model = client(httpx.MockTransport(lambda _r: httpx.Response(status, json={"status": status})))
    with pytest.raises(ModelCallError) as error:
        await model.extract(extraction_request())
    assert error.value.failure is ModelCallFailure.UNAVAILABLE


async def test_model_timeout_connection_and_garbage() -> None:
    def timeout(_r: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    def refused(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with pytest.raises(ModelCallError) as late:
        await client(httpx.MockTransport(timeout)).extract(extraction_request())
    assert late.value.failure is ModelCallFailure.DEADLINE
    with pytest.raises(ModelCallError) as down:
        await client(httpx.MockTransport(refused)).extract(extraction_request())
    assert down.value.failure is ModelCallFailure.UNAVAILABLE
    with pytest.raises(ModelCallError):
        await client(httpx.MockTransport(lambda _r: httpx.Response(200, json={"nonsense": 1}))).extract(
            extraction_request()
        )


async def test_model_io_version_is_cached_and_failure_is_unknown() -> None:
    calls = {"n": 0}

    def handler(_r: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"state": "READY", "model_io_version": "model-io-v2"})

    model = client(httpx.MockTransport(handler))
    assert await model.model_io_version() == "model-io-v2" and await model.model_io_version() == "model-io-v2"
    assert calls["n"] == 1
    broken = client(httpx.MockTransport(lambda _r: httpx.Response(503)))
    assert await broken.model_io_version() is None


async def test_jwks_discovery_refetch_limit_and_unknown_kid() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = key.public_key().public_numbers()

    def b64(value: int) -> str:
        return base64.urlsafe_b64encode(value.to_bytes((value.bit_length() + 7) // 8, "big")).decode().rstrip("=")

    jwk = {"kty": "RSA", "n": b64(numbers.n), "e": b64(numbers.e), "kid": "k1", "use": "sig"}
    fetched: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(request.url.path)
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json={"jwks_uri": "https://platform/certs"})
        return httpx.Response(200, json={"keys": [jwk]})

    now = {"t": 1000.0}
    keys = JwksKeys(
        "https://platform/realms/openit/",
        None,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        clock=lambda: now["t"],
    )
    assert await keys("k1") is not None and fetched == ["/realms/openit/.well-known/openid-configuration", "/certs"]
    assert await keys("k1") is not None and len(fetched) == 2  # 캐시
    with pytest.raises(ApiError):
        await keys("unknown")
    assert len(fetched) == 2  # 60초 안에는 모르는 kid 로 IdP 를 다시 두드리지 않는다
    now["t"] += 61
    with pytest.raises(ApiError):
        await keys("unknown")
    assert len(fetched) == 4
    only = JwksKeys(
        "https://platform/realms/openit",
        "https://platform/certs",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    assert await only(None) is not None  # 키가 하나뿐이면 kid 없는 토큰도 그 키로


async def test_jwks_fetch_failure_is_401() -> None:
    keys = JwksKeys(
        "https://platform/realms/openit",
        "https://platform/certs",
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(500))),
    )
    with pytest.raises(ApiError) as error:
        await keys("k1")
    assert error.value.status == 401


def test_machine_caller_table_is_read_without_secret_files(tmp_path: Path) -> None:
    """받는 쪽은 호출자 이름과 역할만 쓴다. 클라이언트 비밀 파일은 열지 않는다(없어도 읽힌다)."""
    table = tmp_path / "machines.json"
    entry = {"client": "hospital", "roles": ["result-reader"], "client_secret_file": "/run/secrets/does-not-exist"}
    table.write_text(json.dumps({"tokens": [entry]}), encoding="utf-8")
    assert load_machine_callers(str(table)) == {"hospital": frozenset({"result-reader"})}
    table.write_text(json.dumps({"tokens": [{**entry, "client": "Bad Name"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="client"):
        load_machine_callers(str(table))
    table.write_text(json.dumps({"tokens": [{**entry, "token_file": "/x"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="token_file"):  # 8.0.0 의 고정 토큰 칸은 이제 계약에 없다
        load_machine_callers(str(table))


async def test_model_client_invalidates_the_token_on_401() -> None:
    tokens = StaticTokens()
    model = client(httpx.MockTransport(lambda _r: httpx.Response(401, json={"status": 401})), tokens)
    with pytest.raises(ModelCallError):
        await model.extract(extraction_request())
    assert tokens.invalidated == 1


async def test_model_client_without_a_token_is_unavailable() -> None:
    class Broken(StaticTokens):
        async def token(self) -> str:
            raise TokenError("no token")

    model = client(httpx.MockTransport(lambda _r: httpx.Response(200)), Broken())
    with pytest.raises(ModelCallError) as error:
        await model.extract(extraction_request())
    assert error.value.failure is ModelCallFailure.UNAVAILABLE


def issuer_handler(seen: list[httpx.Request], *, lifetime: int = 300, prefix: str = "jwt") -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json={"token_endpoint": "https://platform/realms/openit/token"})
        return httpx.Response(
            200, json={"access_token": f"{prefix}-{len(seen)}", "token_type": "Bearer", "expires_in": lifetime}
        )

    return httpx.MockTransport(handler)


async def test_machine_token_is_requested_with_client_credentials_cached_and_renewed(tmp_path: Path) -> None:
    secret = tmp_path / "secret"
    secret.write_text("s e&cret\n", encoding="utf-8")
    seen: list[httpx.Request] = []
    now = {"t": 1000.0}
    source = MachineTokenSource(
        "https://platform/realms/openit/",
        "machine-survey-service",
        str(secret),
        client=httpx.AsyncClient(transport=issuer_handler(seen)),
        clock=lambda: now["t"],
    )
    first = await source.token()
    assert [r.url.path for r in seen] == ["/realms/openit/.well-known/openid-configuration", "/realms/openit/token"]
    post = seen[1]
    assert post.content == b"grant_type=client_credentials"
    # RFC 6749 2.3.1: 클라이언트 ID·비밀을 폼 인코딩한 뒤 기본 인증으로 보낸다. 비밀은 파일에서 읽는다
    basic = base64.b64decode(post.headers["authorization"].removeprefix("Basic ")).decode()
    assert basic == "machine-survey-service:s+e%26cret"
    now["t"] += 200  # 만료(300초) 30초 전까지는 같은 토큰
    assert await source.token() == first and len(seen) == 2
    now["t"] += 71  # 만료까지 29초: 갱신한다(디스커버리는 다시 읽지 않는다)
    renewed = await source.token()
    assert renewed != first and [r.url.path for r in seen[2:]] == ["/realms/openit/token"]
    source.invalidate()
    assert await source.token() != renewed and len(seen) == 4


async def test_machine_token_failures_are_token_errors(tmp_path: Path) -> None:
    secret = tmp_path / "secret"
    secret.write_text("x", encoding="utf-8")

    def source(handler: httpx.MockTransport, file: Path = secret) -> MachineTokenSource:
        return MachineTokenSource(
            "https://platform/r", "machine-x", str(file), client=httpx.AsyncClient(transport=handler)
        )

    with pytest.raises(TokenError):
        await source(httpx.MockTransport(lambda _r: httpx.Response(500))).token()
    with pytest.raises(TokenError):
        await source(issuer_handler([]), tmp_path / "missing").token()

    def garbage(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json={"token_endpoint": "https://platform/t"})
        return httpx.Response(200, json={"nonsense": 1})

    with pytest.raises(TokenError):
        await source(httpx.MockTransport(garbage)).token()


def _certificate(
    name: str, key: ec.EllipticCurvePrivateKey, issuer: tuple[str, ec.EllipticCurvePrivateKey] | None
) -> x509.Certificate:
    # 왜 고정한 넓은 기간: TLS 라이브러리는 실제 시각으로 유효 기간을 본다. 시험이 지금 시각에 기대지 않게 한다
    builder = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer[0] if issuer else name)]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC))
        .not_valid_after(datetime.datetime(2100, 1, 1, tzinfo=datetime.UTC))
        .add_extension(x509.BasicConstraints(ca=issuer is None, path_length=None), critical=True)
    )
    return builder.sign(issuer[1] if issuer else key, hashes.SHA256())


def _write_pair(folder: Path, name: str, ca: tuple[str, ec.EllipticCurvePrivateKey]) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    (folder / "client.key").write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    (folder / "client.crt").write_bytes(_certificate(name, key, ca).public_bytes(serialization.Encoding.PEM))


def _peer_name(context: ssl.SSLContext, server: ssl.SSLContext) -> str:
    """서버(클라이언트 인증서 필수)에 새 연결을 맺고 서버가 본 클라이언트 인증서의 CN 을 돌려준다."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    seen: list[str] = []

    def serve() -> None:
        conn, _ = listener.accept()
        try:
            with server.wrap_socket(conn, server_side=True) as tls:
                tls.recv(1)  # TLS 1.3 은 클라이언트 인증서 검사가 첫 읽기에서 끝난다
                der = tls.getpeercert(binary_form=True)
                names = (
                    x509.load_der_x509_certificate(der).subject.get_attributes_for_oid(NameOID.COMMON_NAME)
                    if der
                    else []
                )
                seen.append(str(names[0].value) if names else "")
        except ssl.SSLError:
            seen.append("")
        finally:
            conn.close()

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        with (
            socket.create_connection(listener.getsockname()) as raw,
            context.wrap_socket(raw, server_hostname="localhost") as tls,
        ):
            tls.sendall(b"x")
            tls.settimeout(2)
            with contextlib.suppress(ssl.SSLError, OSError, TimeoutError):
                tls.recv(1)
    finally:
        thread.join(5)
        listener.close()
    return seen[0]


def test_client_certificate_is_reloaded_when_the_files_change(tmp_path: Path) -> None:
    """인증서 에이전트가 파일을 갱신하면 다음 요청부터 새 인증서로 mTLS 를 한다(수정 시각으로 본다)."""
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca = _certificate("test-root", ca_key, None)
    root = tmp_path / "root.pem"
    root.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    server_key = ec.generate_private_key(ec.SECP256R1())
    server_cert = _certificate("localhost", server_key, ("test-root", ca_key))
    (tmp_path / "server.key").write_bytes(
        server_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    (tmp_path / "server.crt").write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
    server = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=str(root))
    server.load_cert_chain(str(tmp_path / "server.crt"), str(tmp_path / "server.key"))
    server.verify_mode = ssl.CERT_REQUIRED
    # 서버 인증서의 SAN 이 없어 호스트 이름 검사는 끄고 체인 검증만 본다(이 시험은 클라이언트 인증서를 본다)
    tls = ClientTls(str(root), str(tmp_path / "client.crt"), str(tmp_path / "client.key"))
    tls.context.check_hostname = False
    _write_pair(tmp_path, "client-1", ("test-root", ca_key))
    tls.refresh()
    assert _peer_name(tls.context, server) == "client-1"
    _write_pair(tmp_path, "client-2", ("test-root", ca_key))
    for name in ("client.crt", "client.key"):  # 같은 초에 쓰여도 수정 시각이 다르게 한다
        stat = (tmp_path / name).stat()
        os.utime(tmp_path / name, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
    tls.refresh()
    assert _peer_name(tls.context, server) == "client-2"


def test_client_certificate_that_cannot_be_read_does_not_stop_requests(tmp_path: Path) -> None:
    """에이전트가 아직 인증서를 두지 않았거나 짝이 맞지 않으면 앞의 상태를 두고 다음 요청에서 다시 본다."""
    key = ec.generate_private_key(ec.SECP256R1())
    root = tmp_path / "root.pem"
    root.write_bytes(_certificate("test-root", key, None).public_bytes(serialization.Encoding.PEM))
    tls = ClientTls(str(root), str(tmp_path / "client.crt"), str(tmp_path / "client.key"))
    tls.refresh()  # 파일 없음: 예외 없이 지나간다
    (tmp_path / "client.crt").write_text("not a certificate", encoding="utf-8")
    (tmp_path / "client.key").write_text("not a key", encoding="utf-8")
    tls.refresh()  # 읽을 수 없음: 예외 없이 지나가고 다음 요청에서 다시 읽는다
    _write_pair(tmp_path, "client-1", ("test-root", key))
    tls.refresh()
    assert tls.context.get_ca_certs()  # 루트 인증서는 그대로다


# ------------------------------------------------------------ 응답 문장 스트림(generateResponseStream)


def start_request() -> ResponseGenerationRequest:
    return ResponseGenerationRequest.model_validate(
        {
            "runtime_contract_version": 1,
            "action": "START",
            "next": {"type": "NEXT", "question_id": "Q1", "text": "질문"},
        }
    )


def sse(*frames: tuple[str, dict[str, object]]) -> httpx.Response:
    body = "".join(f"event: {e}\ndata: {json.dumps({'event': e, **d}, ensure_ascii=False)}\n\n" for e, d in frames)
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())


async def collect(model: HttpModelClient) -> tuple[list[str], str]:
    got: list[str] = []

    async def on_delta(text: str) -> None:
        got.append(text)

    result = await model.respond_stream(start_request(), on_delta)
    return got, result.text.root


async def test_stream_client_parses_sse_and_passes_deltas_in_order() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return sse(
            ("delta", {"text": "안녕"}),
            ("delta", {"text": "하세요"}),
            ("result", {"result": {"package_digest": DIGEST, "text": "안녕하세요"}}),
        )

    model = client(httpx.MockTransport(handler))
    assert await collect(model) == (["안녕", "하세요"], "안녕하세요")
    assert seen[0].url.path == "/v1/responses/stream" and seen[0].headers["authorization"] == "Bearer jwt-for-tests"
    assert seen[0].headers["accept"] == "text/event-stream"
    await model.close()


async def test_stream_client_ignores_comments_and_unknown_events() -> None:
    body = (
        ": 주석\n\nevent: ping\ndata: {}\n\n"
        'event: delta\r\ndata: {"event":"delta","text":"가"}\r\n\r\n'
        f'event: result\ndata: {{"event":"result","result":{{"package_digest":"{DIGEST}","text":"가"}}}}\n\n'
    )
    handler = httpx.MockTransport(
        lambda _r: httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())
    )
    assert await collect(client(handler)) == (["가"], "가")


async def test_stream_client_error_event_and_missing_result_are_unavailable() -> None:
    problem: dict[str, object] = {"problem": {"type": "about:blank", "title": "x", "status": 503}}
    cases = [
        sse(("delta", {"text": "가"}), ("error", problem)),
        sse(("delta", {"text": "가"})),  # result 도 error 도 없이 끊겼다
        sse(("delta", {"text": ""})),  # 계약 밖의 조각은 읽지 못한다(받는 쪽은 다시 검사하지 않고 읽기만 한다)
        httpx.Response(200, json={"text": "x"}),  # 스트림이 아니다
        httpx.Response(503, json={"status": 503}),
        httpx.Response(409, json={"status": 409}),
    ]
    for reply in cases:
        model = client(httpx.MockTransport(lambda _r, reply=reply: reply))
        with pytest.raises(ModelCallError) as error:
            await collect(model)
        assert error.value.failure is ModelCallFailure.UNAVAILABLE


async def test_stream_client_timeouts_and_token_failures() -> None:
    def late(_r: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("느리다")

    with pytest.raises(ModelCallError) as error:
        await collect(client(httpx.MockTransport(late)))
    assert error.value.failure is ModelCallFailure.DEADLINE
    # 전체 상한은 마지막 이벤트까지에 건다: 끝나지 않는 스트림에 상한 0 을 주면 첫 기다림에서 바로 시간 초과다(실제 대기 없음)
    from dataclasses import replace

    async def never(_r: httpx.Request) -> httpx.Response:
        await asyncio.Event().wait()
        raise AssertionError

    zero = HttpModelClient(
        "https://model-runtime",
        StaticTokens(),
        replace(LIMITS, respond_seconds=0),
        egress_proxy=None,
        tls=None,
        transport=httpx.MockTransport(never),
    )
    with pytest.raises(ModelCallError) as expired:
        await collect(zero)
    assert expired.value.failure is ModelCallFailure.DEADLINE
    tokens = StaticTokens()
    unauthorized = client(httpx.MockTransport(lambda _r: httpx.Response(401, json={"status": 401})), tokens)
    with pytest.raises(ModelCallError):
        await collect(unauthorized)
    assert tokens.invalidated == 1
