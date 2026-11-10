"""deploy/backup.py: 백업 설정 읽기, 목록(manifest), 잡 결과, 복구 순서 계산(docker 없음, ADR 0027)."""

import json
import re
from pathlib import Path
from types import ModuleType

import jsonschema
import pytest
import yaml

from .conftest import REPO, _load

COMPOSE = yaml.safe_load((REPO / "deploy" / "compose.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bk() -> ModuleType:
    return _load("backup_under_test", REPO / "deploy" / "backup.py")


def test_repository_url_is_parsed_and_must_name_one_repository(bk: ModuleType) -> None:
    repository = bk.parse_repository("rest:https://backup:8000/openit")
    assert (repository.host, repository.port, repository.path) == ("backup", 8000, "openit")
    assert repository.url == "rest:https://backup:8000/openit"
    assert bk.parse_repository("rest:https://backup/openit").port == 443
    for bad, why in (
        ("https://backup:8000/openit", "rest:https://"),
        ("rest:https://10.0.0.5:8000/openit", "IP"),
        ("rest:https://u:p@backup:8000/openit", "자격"),
        ("rest:https://backup:8000/", "저장소 이름"),
        ("rest:https://backup:8000/a/b", "저장소 이름"),
        ("rest:https://backup:8000/openit?x=1", "질의"),
    ):
        with pytest.raises(bk.BackupConfigError, match=why):
            bk.parse_repository(bad)


def test_credentials_must_be_one_line_and_user_must_be_the_repository(bk: ModuleType) -> None:
    repository = bk.parse_repository("rest:https://backup:8000/openit")
    assert bk.parse_credentials("openit:s3cret:with:colons\n", repository) == ("openit", "s3cret:with:colons")
    for bad in ("openit", "openit:", ":pw", "openit:a\nopenit:b", "other:pw"):
        with pytest.raises(bk.BackupConfigError):
            bk.parse_credentials(bad, repository)


def test_credentials_in_the_repository_address_file_are_percent_encoded(bk: ModuleType) -> None:
    url = bk.with_credentials("rest:https://backup:8000/openit", "openit", "p@ss/w:rd#")
    assert url == "rest:https://openit:p%40ss%2Fw%3Ard%23@backup:8000/openit"


def test_offsite_target_is_a_rest_repository_over_https(bk: ModuleType) -> None:
    assert bk.offsite_repository("https://backup.example.org/openit") == "rest:https://backup.example.org/openit"
    for bad in ("http://backup.example.org/openit", "https://u:p@backup.example.org/openit", "s3:backup"):
        with pytest.raises(bk.BackupConfigError):
            bk.offsite_repository(bad)


def test_htpasswd_line_is_stable_for_the_same_credentials(bk: ModuleType) -> None:
    first = bk.htpasswd_line("openit", "pw-1", None)
    assert first.startswith("openit:$2") and first.endswith("\n")
    assert bk.htpasswd_line("openit", "pw-1", first) == first  # bcrypt 는 소금이 매번 달라 맞으면 있던 줄을 쓴다
    changed = bk.htpasswd_line("openit", "pw-2", first)
    assert changed != first and bk.htpasswd_line("openit", "pw-2", changed) == changed


def test_allowed_names_follow_the_step_ca_policy(bk: ModuleType) -> None:
    allowed = ["registry", "backup", "*.openit.internal"]
    assert bk.allowed_name("backup", allowed)
    assert bk.allowed_name("store.openit.internal", allowed)
    assert not bk.allowed_name("a.b.openit.internal", allowed)  # 와일드카드는 한 단계다
    assert not bk.allowed_name("platform", allowed)


def test_default_ca_policy_and_example_layout_agree_on_the_repository_name(bk: ModuleType) -> None:
    env = (REPO / "deploy" / "env.example").read_text(encoding="utf-8")
    allowed = re.search(r"^OPENIT_CA_ALLOWED_DNS=(.*)$", env, re.M).group(1).split(",")  # type: ignore[union-attr]
    example = json.loads((REPO / "deploy" / "layout.example.json").read_text(encoding="utf-8"))
    repository = bk.parse_repository(example["backup"]["repository_url"])
    assert bk.allowed_name(repository.host, allowed)
    assert bk.parse_credentials(f"{repository.path}:x", repository)  # 예시의 저장소 이름이 자격의 사용자로 쓸 수 있는 글자다


def test_dependents_are_found_through_depends_on(bk: ModuleType) -> None:
    model = {"services": {"db": {}, "a": {"depends_on": {"db": {}}}, "b": {"depends_on": {"a": {}}}, "c": {"depends_on": {"x": {}}}, "x": {}}}
    assert bk.dependents(model, "db") == ["a", "b"]
    assert bk.dependents(model, "x") == ["c"]


def test_table_count_ignores_table_data_lines(bk: ModuleType) -> None:
    toc = "\n".join([
        "; Archive created at 2026-11-11",
        "215; 1259 16385 TABLE public backup_probe survey",
        "216; 1259 16390 TABLE public other survey",
        "3380; 0 16385 TABLE DATA public backup_probe survey",
        "3381; 0 16390 TABLE DATA public other survey",
        "2200; 1259 16400 SEQUENCE public s survey",
        "3000; 2606 16386 CONSTRAINT public backup_probe backup_probe_pkey survey",
    ])
    assert bk.toc_table_count(toc) == 2


def test_manifest_round_trips_and_rejects_unsafe_database_names(bk: ModuleType) -> None:
    targets = [bk.Target("survey-service", "survey-db", "survey", "db", (("survey", 12),)), bk.Target("platform", "postgres", "postgres", "svc", (("keycloak", 95), ("postgres", 0)))]
    text = bk.manifest_json("2026-11-11T00:00:00Z", "openit", "16", targets)
    assert bk.parse_manifest(text) == targets
    document = json.loads(text)
    document["targets"][0]["databases"][0]["name"] = 'x"; drop'
    with pytest.raises(bk.BackupConfigError, match="데이터베이스 이름"):
        bk.parse_manifest(json.dumps(document))
    with pytest.raises(bk.BackupConfigError):
        bk.parse_manifest('{"format": 2, "targets": []}')


def test_job_result_line_is_the_contract_job_run_result(bk: ModuleType) -> None:
    components = yaml.safe_load((REPO / "contracts" / "components.yaml").read_text(encoding="utf-8"))["components"]
    schema = {"$ref": "#/components/schemas/JobRunResult", "components": components}
    snapshot = "a" * 64
    for line in (
        bk.job_result_line("BACKUP", 0, "2026-11-11T00:00:00Z", "2026-11-11T00:01:00Z", 3, snapshot),
        bk.job_result_line("RESTORE_TEST", 75, "2026-11-11T00:00:00Z", "2026-11-11T00:01:00Z"),
        bk.job_result_line("OFFSITE_SYNC", 1, "2026-11-11T00:00:00Z", "2026-11-11T00:01:00Z", 0),
    ):
        jsonschema.validate(json.loads(line), schema, format_checker=jsonschema.FormatChecker())
        assert "\n" not in line
    with pytest.raises(ValueError):
        bk.job_result_line("BACKUP", 0, "2026-11-11T00:00:00Z", "2026-11-11T00:01:00Z", 1, "xyz")


def test_product_compose_labels_every_database_for_backup(bk: ModuleType) -> None:
    """영역 DB 는 라벨 하나로 백업 대상이 된다. 지금의 대상은 platform 의 postgres(Keycloak)와 survey-service 의 survey-db 다."""
    found = bk.targets_in(COMPOSE, {})
    assert found == [("platform", "postgres", "postgres"), ("survey-service", "survey-db", "survey")]
    postgres_images = {name for name, spec in COMPOSE["services"].items() if str(spec.get("image", "")).startswith("postgres:")}
    assert postgres_images == {name for _, name, _ in found}  # PostgreSQL 컨테이너가 라벨 없이 남지 않는다


def test_backup_services_are_platform_services_pinned_and_hidden_without_a_backup_section() -> None:
    services = COMPOSE["services"]
    for name in ("backup-store", "backup", "backup-client"):
        assert services[name]["labels"]["io.openit.service"] == "platform"
        assert "@sha256:" in services[name]["image"]
    assert services["backup-store"]["profiles"] == ["backup"] and services["backup"]["profiles"] == ["backup"]
    assert services["backup-client"]["profiles"] == ["tools"]
    assert "ports" not in services["backup"] and "ports" not in services["backup-store"]  # 서버 한 대에서는 호스트 포트를 게시하지 않는다
    assert "--private-repos" in services["backup-store"]["environment"]["OPTIONS"]
    assert "--append-only" not in services["backup-store"]["environment"]["OPTIONS"]  # D130
    assert "backup-data" in COMPOSE["volumes"]


def test_retention_is_within_the_shortest_data_retention(bk: ModuleType) -> None:
    """OPEN_GAPS U30: 백업 보관 기간 ≤ 운영 데이터의 가장 짧은 보존(D88 U4 처리 끝난 원본 Trace 30일). U31: 14일."""
    days = int(bk.RETENTION_WITHIN.removesuffix("d"))
    assert days == 14 and days <= 30
