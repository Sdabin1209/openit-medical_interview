"""웹 푸시: RFC 8291 부록 A 의 시험 벡터, VAPID 헤더(RFC 8292), 전달과 구독 소멸 처리."""

import base64
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from survey_service.contract.models import AlertKind, PushSubscription
from survey_service.link import push
from survey_service.types import AlertRecord

pytestmark = pytest.mark.anyio


def test_rfc8291_appendix_a_vector() -> None:
    """RFC 8291 부록 A 의 값으로 만든 본문이 글자 그대로 같다."""
    server_private = ec.derive_private_key(
        int.from_bytes(push.b64u_decode("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"), ec.SECP256R1()
    )
    body = push.encrypt(
        b"When I grow up, I want to be a watermelon",
        push.b64u_decode("BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"),
        push.b64u_decode("BTBZMqHH6r4Tts7J_aSIgg"),
        server_private=server_private,
        salt=push.b64u_decode("DGv6ra1nlYgDCS1FRnbzlw"),
    )  # fmt: skip
    expected = (
        "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A"
        "_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
    )
    assert push.b64u(body) == expected


def test_encrypt_rejects_oversized_payload() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    with pytest.raises(ValueError, match="레코드"):
        push.encrypt(b"x" * 5000, public, b"a" * 16)


def _pem() -> bytes:
    return ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def test_vapid_header_is_a_verifiable_es256_jwt() -> None:
    pem = _pem()
    header = push.vapid_authorization(
        "https://push.example.org/send/abc", "mailto:ops@example.org", pem, now=1_800_000_000
    )
    scheme, rest = header.split(" ", 1)
    token = rest.split(",")[0].removeprefix("t=")
    key = rest.split("k=")[1]
    assert scheme == "vapid" and key == push.vapid_public_key(pem) and len(key) == 87
    public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), push.b64u_decode(key))
    claims = jwt.decode(
        token, public, algorithms=["ES256"], audience="https://push.example.org", options={"verify_exp": False}
    )
    assert claims["sub"] == "mailto:ops@example.org" and claims["exp"] - 1_800_000_000 == push.VAPID_LIFETIME_SECONDS
    assert push.VAPID_LIFETIME_SECONDS <= 24 * 3600  # RFC 8292 2


def test_vapid_key_must_be_p256() -> None:
    from cryptography.hazmat.primitives.asymmetric import rsa

    rsa_pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    with pytest.raises(ValueError, match="P-256"):
        push.vapid_public_key(rsa_pem)


async def test_notifier_sends_encrypted_payload_and_reports_gone(tmp_path: Path) -> None:
    key_file = tmp_path / "vapid.pem"
    key_file.write_bytes(_pem())
    received: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(410 if request.url.path.endswith("gone") else 201)

    notifier = push.WebPushNotifier(
        str(key_file), "mailto:ops@example.org", egress_proxy=None, transport=httpx.MockTransport(handler)
    )
    user = ec.generate_private_key(ec.SECP256R1())
    public = push.b64u(
        user.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )
    secret = push.b64u(b"s" * 16)
    subscriptions = tuple(
        PushSubscription.model_validate(
            {"endpoint": f"https://push.example.org/send/{name}", "keys": {"p256dh": public, "auth": secret}}
        )
        for name in ("ok", "gone")
    )
    record = AlertRecord(
        alert_id=uuid.uuid4(),
        kind=AlertKind.CALL_STAFF,
        session_id=uuid.uuid4(),
        device_id="kiosk-01",
        raised_at=datetime(2026, 11, 10, tzinfo=UTC),
    )
    gone = await notifier.push(record, subscriptions)
    await notifier.close()
    assert gone == ("https://push.example.org/send/gone",) and len(received) == 2
    request = received[0]
    assert request.headers["content-encoding"] == "aes128gcm" and request.headers["ttl"] == str(push.PUSH_TTL_SECONDS)
    assert request.headers["authorization"].startswith("vapid t=")
    # 받는 쪽(브라우저)이 풀면 알림 종류·식별자·시각만 있고 환자 정보는 없다
    payload = json.loads(_decrypt(request.content, user, base64.urlsafe_b64decode(secret + "==")))
    assert set(payload) == {"kind", "alert_id", "raised_at"} and payload["kind"] == "CALL_STAFF"
    assert payload["alert_id"] == str(record.alert_id)


def _decrypt(body: bytes, user_private: ec.EllipticCurvePrivateKey, auth: bytes) -> bytes:
    """RFC 8291 의 받는 쪽 절차로 풀어 본다(시험 도구)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    salt, key_len = body[:16], body[20]
    server_public = body[21 : 21 + key_len]
    ciphertext = body[21 + key_len :]
    user_public = user_private.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    shared = user_private.exchange(
        ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), server_public)
    )
    ikm = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=auth, info=b"WebPush: info\x00" + user_public + server_public
    ).derive(shared)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt, info=b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt, info=b"Content-Encoding: nonce\x00").derive(ikm)
    return AESGCM(cek).decrypt(nonce, ciphertext, None).rstrip(b"\x02")
