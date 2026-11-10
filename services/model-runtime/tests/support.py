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
from model_runtime.link.auth import Authenticator, CallerTable, JwksCache, OidcVerifier
from model_runtime.link.engine import VllmEngine
from model_runtime.link.registry import OciPackageSource
from model_runtime.main import Dependencies, Settings, create_app

ISSUER = "https://idp.test/realms/openit"
AUDIENCE = "model-runtime"
BASE_MODEL = "Qwen/Qwen3-8B"  # 프로파일 rtx4090-24g 의 기반 모델(src/model_runtime/profiles.json)
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

    def machine_token(
        self,
        name: str = "survey-service",
        roles: tuple[str, ...] = ("inference-caller",),
        **override: Any,  # noqa: ANN401
    ) -> str:
        """기계 호출자의 JWT 접근 토큰(client credentials 로 받은 것과 같은 모양: client_id 는 machine-<이름>)."""
        return self.token(
            list(roles), **{"sub": f"service-account-machine-{name}", "client_id": f"machine-{name}", **override}
        )

    def idp_app(self) -> FastAPI:
        app = FastAPI()
        jwks_body = self.jwks()
        # 왜 암호화용 키를 함께: 실제 Keycloak 의 JWKS 는 서명 키(sig)와 함께 RSA-OAEP 암호화 키(enc)를 낸다.
        # 서명 키만 고르지 않으면 갱신 전체가 실패했다(통합 확인)
        sig_key = jwks_body["keys"][0]
        jwks_body = {
            "keys": [*jwks_body["keys"], {**sig_key, "kid": "keycloak-enc-key", "use": "enc", "alg": "RSA-OAEP"}]
        }

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
    # 호출자 표에는 비밀이 없다. client_secret_file 은 호출자가 읽는 경로이고 이 서비스는 읽지 않는다
    tokens.write_text(
        json.dumps(
            {
                "tokens": [
                    {
                        "client": "survey-service",
                        "roles": ["inference-caller"],
                        "client_secret_file": "/run/secrets/survey-service-client-secret",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    credentials = tmp / "registry.credentials"
    credentials.write_text(f"{REGISTRY_USER}:{REGISTRY_PASSWORD}\n", encoding="utf-8")
    values: dict[str, Any] = {
        "root_certificate_file": pki.root,
        "tls_certificate_file": pki.client_cert,
        "tls_private_key_file": pki.client_key,
        "listen_port": 8443,
        "oidc_issuer_url": ISSUER,
        "oidc_audience": AUDIENCE,
        "registry_url": registry_url,
        "registry_repository": "openit/model-package",
        "registry_credentials_file": credentials,
        "machine_tokens_file": tokens,
        "model_profile": "rtx4090-24g",
        "inference_engine_url": "http://engine",
        "model_cache_dir": tmp / "cache",
    }
    values.update(override)
    return Settings(**values)


def make_app(settings: Settings, pki: Pki, identity: Identity, engine: FakeEngine, clock: Any = None) -> FastAPI:  # noqa: ANN401
    """실제 부품(레지스트리 클라이언트, 엔진 클라이언트, 인증)을 쓰되 엔진과 신원 공급자만 시험용으로 바꿔 조립한다."""
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=engine.app()), base_url="http://engine")
    vllm = VllmEngine("http://engine", BASE_MODEL, http)
    idp = httpx.AsyncClient(transport=httpx.ASGITransport(app=identity.idp_app()))
    user, _, password = (settings.registry_credentials_file.read_text(encoding="utf-8").strip()).partition(":")
    source = OciPackageSource(
        settings.registry_url,
        settings.registry_repository.root,
        (user, password),
        pki.root,
        None,
        (settings.tls_certificate_file, settings.tls_private_key_file),
    )
    deps = Dependencies(
        source=source,
        chat=vllm,
        adapters=vllm,
        authenticator=Authenticator(
            CallerTable(settings.machine_tokens_file),
            OidcVerifier(JwksCache(idp, ISSUER, None), ISSUER, AUDIENCE),
        ),
        engine_ready=vllm.healthy,
        closers=[source.close],
    )
    return create_app(settings, deps, **({"clock": clock} if clock else {}))
