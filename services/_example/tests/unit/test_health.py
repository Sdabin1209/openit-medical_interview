from fastapi.testclient import TestClient

from example.main import Settings, create_app


def test_healthz_ok() -> None:
    client = TestClient(create_app(Settings()))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_ready_without_checks() -> None:
    client = TestClient(create_app(Settings()))
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "failed": []}


def test_readyz_reports_failed_check_names_only() -> None:
    async def down() -> bool:
        return False

    async def boom() -> bool:
        raise RuntimeError("postgresql://user:SECRET@host/db")

    async def up() -> bool:
        return True

    client = TestClient(create_app(Settings(), {"a": down, "b": boom, "c": up}))
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "failed": ["a", "b"]}
    assert "SECRET" not in response.text
