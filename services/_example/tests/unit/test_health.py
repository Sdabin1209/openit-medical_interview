from fastapi.testclient import TestClient

from example.main import Settings, create_app


def test_healthz_is_pass_with_service_name() -> None:
    settings = Settings()
    response = TestClient(create_app(settings)).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "pass", "service": settings.service_name.value}


def test_readyz_passes_without_checks() -> None:
    response = TestClient(create_app(Settings())).get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "pass"
    assert response.json()["checks"] == []


def test_readyz_lists_passing_checks() -> None:
    async def up() -> bool:
        return True

    body = TestClient(create_app(Settings(), {"database": up})).get("/readyz").json()
    assert body["checks"] == [{"name": "database", "status": "pass"}]


def test_readyz_503_is_problem_details_with_check_names_only() -> None:
    async def down() -> bool:
        return False

    async def boom() -> bool:
        raise RuntimeError("postgresql://user:SECRET@host/db")

    async def up() -> bool:
        return True

    response = TestClient(create_app(Settings(), {"a": down, "b": boom, "c": up})).get("/readyz")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["retry-after"].isdigit()
    body = response.json()
    assert body["status"] == 503
    assert body["detail"] == "준비되지 않은 점검: a, b"
    assert "SECRET" not in response.text


def test_metrics_is_prometheus_text() -> None:
    response = TestClient(create_app(Settings())).get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# HELP" in response.text
