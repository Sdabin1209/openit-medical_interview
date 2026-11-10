from pathlib import Path

import pytest
from pydantic import ValidationError

from fakes.pki import make_pki
from model_runtime.contract.models import ModelRuntimeEnv
from model_runtime.main import Settings
from support import settings_for


def test_settings_names_are_exactly_the_contract_env_inputs() -> None:
    """환경 변수는 계약 ModelRuntimeEnv 에 있는 이름만 받는다. 어긋남이 생기면 이 시험이 먼저 깨진다."""
    names = {f"OPENIT_{name.upper()}" for name in Settings.model_fields}
    assert names == set(ModelRuntimeEnv.model_fields)


def test_required_inputs_follow_the_contract() -> None:
    required = {f"OPENIT_{name.upper()}" for name, field in Settings.model_fields.items() if field.is_required()}
    contract = {name for name, field in ModelRuntimeEnv.model_fields.items() if field.is_required()}
    assert required == contract


def test_settings_read_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pki = make_pki(tmp_path / "pki")
    expected = settings_for(tmp_path, pki, "https://registry")
    monkeypatch.setenv("OPENIT_ROOT_CERTIFICATE_FILE", str(pki.root))
    monkeypatch.setenv("OPENIT_TLS_CERTIFICATE_FILE", str(pki.server_cert))
    monkeypatch.setenv("OPENIT_TLS_PRIVATE_KEY_FILE", str(pki.server_key))
    monkeypatch.setenv("OPENIT_LISTEN_PORT", "8443")
    monkeypatch.setenv("OPENIT_OIDC_ISSUER_URL", expected.oidc_issuer_url)
    monkeypatch.setenv("OPENIT_OIDC_AUDIENCE", "model-runtime")
    monkeypatch.setenv("OPENIT_REGISTRY_URL", "https://registry")
    monkeypatch.setenv("OPENIT_REGISTRY_REPOSITORY", "openit/model-package")
    monkeypatch.setenv("OPENIT_REGISTRY_CREDENTIALS_FILE", str(expected.registry_credentials_file))
    monkeypatch.setenv("OPENIT_MACHINE_TOKENS_FILE", str(expected.machine_tokens_file))
    monkeypatch.setenv("OPENIT_MODEL_PROFILE", "p")
    monkeypatch.setenv("OPENIT_MODEL_CACHE_DIR", str(tmp_path))
    loaded = Settings()  # pyright: ignore[reportCallIssue]
    assert loaded.listen_port == 8443 and loaded.registry_repository.root == "openit/model-package"


def test_unknown_audience_is_rejected(tmp_path: Path) -> None:
    pki = make_pki(tmp_path / "pki")
    with pytest.raises(ValidationError):
        settings_for(tmp_path, pki, "https://registry", oidc_audience="abc")  # 계약 ServiceName 에 없는 이름
