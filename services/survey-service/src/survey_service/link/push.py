"""link_push: 직원 알림을 웹 푸시로 보낸다(Web Push, RFC 8030). 메시지 암호화는 RFC 8291(aes128gcm, RFC 8188),
서버 신원은 VAPID(RFC 8292, ES256 JWT)다.

왜 직접 구현하나: 이 표준의 흔한 라이브러리(pywebpush, py-vapid, http-ece)는 MPL-2.0 이라 배포물 의존의
허용형 원칙(ADR 0001·0017)에
맞지 않는다. 암호 연산은 cryptography(Apache-2.0 또는 BSD)가, JWT 서명은 PyJWT(MIT)가 하고 이 모듈은 표준의 조립만 한다.
RFC 8291 부록 A 의 시험 벡터로 암호화를 시험한다.
"""

import base64
import os
import struct
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from survey_service.components import alert
from survey_service.contract.models import PushSubscription
from survey_service.types import AlertRecord

# 왜 4096: RFC 8291 4 가 푸시 서비스가 지원해야 하는 암호문 크기의 하한(4096옥텟)이고 우리 내용은 그보다 훨씬 작다
RECORD_SIZE = 4096
# 왜 12시간: RFC 8292 2 는 VAPID JWT 의 exp 를 발급 후 24시간 이내로 제한한다. 그 절반으로 둔다(측정 아님)
VAPID_LIFETIME_SECONDS = 12 * 3600
# 왜 1시간: RFC 8030 5.2 가 TTL 헤더를 필수로 정한다. 지난 알림은 목록과 스트림에서 다시 볼 수 있어 푸시는
# 오래 쌓아 둘 필요가 없다(측정 아님)
PUSH_TTL_SECONDS = 3600
SEND_TIMEOUT_SECONDS = 10.0  # 왜 10: 푸시 서비스 한 곳에 오래 매이지 않으려는 선택이며 측정하지 않았다


def b64u(data: bytes) -> str:
    """패딩 없는 base64url(RFC 4648 5)."""
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def b64u_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _public_bytes(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def vapid_public_key(private_key_pem: bytes) -> str:
    """VAPID 개인키에서 브라우저가 구독할 때 쓰는 공개키(base64url, 65옥텟 → 87자)."""
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ValueError("VAPID 키는 P-256 타원곡선 키여야 한다")
    return b64u(_public_bytes(key))


def encrypt(
    plaintext: bytes,
    user_agent_public: bytes,
    auth_secret: bytes,
    *,
    server_private: ec.EllipticCurvePrivateKey | None = None,
    salt: bytes | None = None,
) -> bytes:
    """RFC 8291 3 의 aes128gcm 본문(머리글 + 암호문 한 레코드). 시험이 server_private·salt 를 고정한다."""
    server_private = server_private or ec.generate_private_key(ec.SECP256R1())
    salt = salt or os.urandom(16)
    server_public = _public_bytes(server_private)
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), user_agent_public)
    shared = server_private.exchange(ec.ECDH(), peer)
    key_info = b"WebPush: info\x00" + user_agent_public + server_public
    ikm = HKDF(algorithm=hashes.SHA256(), length=32, salt=auth_secret, info=key_info).derive(shared)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt, info=b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt, info=b"Content-Encoding: nonce\x00").derive(ikm)
    if len(plaintext) + 17 > RECORD_SIZE:
        raise ValueError("알림 내용이 한 레코드를 넘는다")
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)  # 0x02: 마지막 레코드 표시(RFC 8188 2)
    return salt + struct.pack(">IB", RECORD_SIZE, len(server_public)) + server_public + ciphertext


def vapid_authorization(endpoint: str, subject: str, private_key_pem: bytes, now: float | None = None) -> str:
    """VAPID Authorization 헤더 값(RFC 8292 3): `vapid t=<JWT>, k=<공개키>`."""
    parts = urlsplit(endpoint)
    issued = int(now if now is not None else time.time())
    claims = {"aud": f"{parts.scheme}://{parts.netloc}", "exp": issued + VAPID_LIFETIME_SECONDS, "sub": subject}
    token = jwt.encode(claims, private_key_pem, algorithm="ES256")
    return f"vapid t={token}, k={vapid_public_key(private_key_pem)}"


class WebPushNotifier:
    """Notifier 의 구현. 알림 내용(WebPushPayload)을 구독마다 암호화해 푸시 서비스로 보낸다."""

    def __init__(
        self,
        private_key_file: str,
        subject: str,
        *,
        egress_proxy: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._key = Path(private_key_file).read_bytes()
        self._subject = subject
        self.public_key = vapid_public_key(self._key)
        self._client = httpx.AsyncClient(proxy=egress_proxy if transport is None else None, transport=transport)

    async def push(self, record: AlertRecord, subscriptions: tuple[PushSubscription, ...]) -> tuple[str, ...]:
        """보낸다. 404·410 은 구독이 사라졌다는 뜻(RFC 8030 7.3)이라 그 주소를 돌려줘 지우게 한다. 다른
        실패는 삼키지 않고 기록 대상이다."""
        body = alert.push_payload(record).model_dump_json().encode()
        gone: list[str] = []
        for subscription in subscriptions:
            endpoint = str(subscription.endpoint.root)
            data = encrypt(body, b64u_decode(subscription.keys.p256dh.root), b64u_decode(subscription.keys.auth.root))
            headers = {
                "Content-Encoding": "aes128gcm",
                "Content-Type": "application/octet-stream",
                "TTL": str(PUSH_TTL_SECONDS),
                "Authorization": vapid_authorization(endpoint, self._subject, self._key),
            }
            try:
                response = await self._client.post(
                    endpoint, content=data, headers=headers, timeout=SEND_TIMEOUT_SECONDS
                )
            except httpx.HTTPError:
                continue  # 왜: 푸시는 최선 전달이다. 알림은 이미 DB 와 스트림에 있고 직원 화면이 다시 읽는다
            if response.status_code in {404, 410}:
                gone.append(endpoint)
        return tuple(gone)

    async def close(self) -> None:
        await self._client.aclose()
