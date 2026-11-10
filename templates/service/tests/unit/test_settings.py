from pathlib import Path

import pytest

from __PKG__.main import Settings, create_app


def test_settings_read_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENIT_SERVICE_NAME", "model-runtime")
    assert Settings().service_name.value == "model-runtime"


def test_unknown_service_name_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    monkeypatch.setenv("OPENIT_SERVICE_NAME", "abc")  # 계약 ServiceName 에 없는 이름
    with pytest.raises(ValidationError):
        Settings()


def test_database_enabled_requires_secret_file(monkeypatch: pytest.MonkeyPatch) -> None:
    from __PKG__.main import SecretError

    monkeypatch.delenv("DATABASE_URL_FILE", raising=False)
    with pytest.raises(SecretError):
        create_app(Settings(database_enabled=True))


def test_database_enabled_adds_failing_readiness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fastapi.testclient import TestClient

    secret = tmp_path / "url"
    secret.write_text("postgresql+asyncpg://u:p@127.0.0.1:1/db\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL_FILE", str(secret))
    client = TestClient(create_app(Settings(database_enabled=True)))
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["detail"] == "준비되지 않은 점검: database"
