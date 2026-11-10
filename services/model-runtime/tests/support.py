"""시험 공용 도구: 시험용 신원 공급자(JWKS), 기계 토큰, 어댑터 폴더, 평가 집합, 앱 조립."""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx2 as httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from jwt.algorithms import RSAAlgorithm

from fakes.engine import FakeEngine
from fakes.pki import Pki
from model_runtime.link.auth import Authenticator, JwksCache, MachineTokens, OidcVerifier
from model_runtime.link.engine import VllmEngine
from model_runtime.link.registry import OciPackageSource
from model_runtime.main import Dependencies, Settings, create_app

ISSUER = "https://idp.test/realms/openit"
AUDIENCE = "model-runtime"
MACHINE_TOKEN = "machine-token-for-survey-service-0123456789"  # noqa: S105 - 시험용 값
REGISTRY_USER, REGISTRY_PASSWORD = "reader", "registry-password"


@dataclass
class Identity:
    """시험용 신원 공급자: 서명 키와 토큰 발급."""

    key: Any
    kid: str = "test-key-1"

    @classmethod
    def new(cls) -> "Identity":
        return cls(rsa.generate_private_key(public_exponent=65537, key_size=2048))

    def jwks(self) -> dict[str, Any]:
        jwk = json.loads(RSAAlgorithm.to_jwk(self.key.public_key()))
        return {"keys": [{**jwk, "kid": self.kid, "use": "sig", "alg": "RS256"}]}

    def token(self, roles: list[str], sub: str = "approver-1", **override: Any) -> str:  # noqa: ANN401
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "sub": sub,
            "aud": AUDIENCE,
            "exp": now + 300,
            "iat": now,
            "jti": "jti-1",
            "client_id": "admin-console",
            "realm_access": {"roles": roles},
        }
        extra_headers = override.pop("_headers", {})
        drop = override.pop("_drop", ())
        claims.update(override)
        headers: dict[str, Any] = {"typ": "at+jwt", "kid": self.kid}
        headers.update(extra_headers)
        return jwt.encode(
            {k: v for k, v in claims.items() if k not in drop}, self.key, algorithm="RS256", headers=headers
        )

    def idp_app(self) -> FastAPI:
        app = FastAPI()
        jwks_body = self.jwks()

        @app.get("/realms/openit/.well-known/openid-configuration")
        async def discovery() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            return {"issuer": ISSUER, "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs"}

        @app.get("/realms/openit/protocol/openid-connect/certs")
        async def certs() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
            return jwks_body

        return app


def adapter_folder(root: Path, name: str, weights: bytes = b"fake-weights") -> Path:
    """시험용 어댑터 폴더(PEFT 출력 모양). 가중치는 가짜 바이트다."""
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "adapter_config.json").write_text('{"peft_type": "LORA", "r": 8}', encoding="utf-8")
    (folder / "adapter_model.safetensors").write_bytes(weights)
    return folder


def settings_for(tmp: Path, pki: Pki, registry_url: str, **override: Any) -> Settings:  # noqa: ANN401
    """계약 ModelRuntimeEnv 의 필수 입력을 시험 폴더에서 채운 설정."""
    tokens = tmp / "machine-tokens.json"
    token_file = tmp / "inference-caller.token"
    token_file.write_text(MACHINE_TOKEN + "\n", encoding="utf-8")
    tokens.write_text(
        json.dumps(
            {"tokens": [{"client": "survey-service", "roles": ["inference-caller"], "token_file": str(token_file)}]}
        ),
        encoding="utf-8",
    )
    credentials = tmp / "registry.credentials"
    credentials.write_text(f"{REGISTRY_USER}:{REGISTRY_PASSWORD}\n", encoding="utf-8")
    values: dict[str, Any] = {
        "root_certificate_file": pki.root,
        "tls_certificate_file": pki.server_cert,
        "tls_private_key_file": pki.server_key,
        "listen_port": 8443,
        "oidc_issuer_url": ISSUER,
        "oidc_audience": AUDIENCE,
        "registry_url": registry_url,
        "registry_repository": "openit/model-package",
        "registry_credentials_file": credentials,
        "machine_tokens_file": tokens,
        "model_profile": "test-profile",
        "model_cache_dir": tmp / "cache",
    }
    values.update(override)
    return Settings(**values)


def make_app(settings: Settings, pki: Pki, identity: Identity, engine: FakeEngine, clock: Any = None) -> FastAPI:  # noqa: ANN401
    """실제 부품(레지스트리 클라이언트, 엔진 클라이언트, 인증)을 쓰되 엔진과 신원 공급자만 시험용으로 바꿔 조립한다."""
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=engine.app()), base_url="http://engine")
    vllm = VllmEngine("http://engine", http)
    idp = httpx.AsyncClient(transport=httpx.ASGITransport(app=identity.idp_app()))
    user, _, password = (settings.registry_credentials_file.read_text(encoding="utf-8").strip()).partition(":")
    source = OciPackageSource(
        settings.registry_url, settings.registry_repository.root, (user, password), pki.root, None
    )
    deps = Dependencies(
        source=source,
        chat=vllm,
        adapters=vllm,
        authenticator=Authenticator(
            MachineTokens(settings.machine_tokens_file),
            OidcVerifier(JwksCache(idp, ISSUER, None), ISSUER, AUDIENCE),
        ),
        engine_ready=vllm.healthy,
        closers=[source.close],
    )
    return create_app(settings, deps, **({"clock": clock} if clock else {}))
