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
    targets = (bk.Target("survey-service", "survey-db", "survey", "db", (("survey", 12),)), bk.Target("platform", "postgres", "postgres", "svc", (("keycloak", 95), ("postgres", 0))))
    volumes = (bk.VolumeTarget("model-runtime", "model-runtime-data", "gpu", ("cache/model-runtime/release-log.jsonl",), (bk.FileEntry("cache/model-runtime/release-log.jsonl", 12, "a" * 64),)),)
    text = bk.manifest_json("2026-11-11T00:00:00Z", "openit", "16", targets, volumes)
    assert bk.parse_manifest(text) == bk.Manifest(targets, volumes)
    assert volumes[0].archive == "/stage/model-runtime/model-runtime-data.tar"
    document = json.loads(text)
    document["targets"][0]["databases"][0]["name"] = 'x"; drop'
    with pytest.raises(bk.BackupConfigError, match="데이터베이스 이름"):
        bk.parse_manifest(json.dumps(document))
    document = json.loads(text)
    document["volumes"][0]["paths"] = ["../etc"]  # 복구가 지우는 경로라 manifest 가 바뀌었어도 이탈을 받지 않는다
    with pytest.raises(bk.BackupConfigError, match="상대 경로"):
        bk.parse_manifest(json.dumps(document))
    with pytest.raises(bk.BackupConfigError):
        bk.parse_manifest('{"format": 3, "targets": []}')


def test_manifest_format_1_without_volumes_is_still_readable(bk: ModuleType) -> None:
    """이전 판이 만든 백업(데이터베이스만)도 복구·시험할 수 있다."""
    old = {"format": 1, "created_at": "2026-11-11T00:00:00Z", "project": "openit", "postgres_major": "16",
           "targets": [{"owner": "platform", "service": "postgres", "user": "postgres", "server": "svc", "databases": [{"name": "keycloak", "tables": 95}]}]}
    manifest = bk.parse_manifest(json.dumps(old))
    assert manifest.volumes == () and manifest.targets[0].databases == (("keycloak", 95),)


def test_volume_paths_are_relative_and_without_dot_elements(bk: ModuleType) -> None:
    assert bk.volume_paths("cache/model-runtime/release-log.jsonl state") == ("cache/model-runtime/release-log.jsonl", "state")
    for bad in ("", "/abs", "../x", "a/../b", "./a", "a//b", "a b/..", "a/.hidden", "a;rm"):
        with pytest.raises(bk.BackupConfigError):
            bk.volume_paths(bad)


def test_files_are_found_by_the_service_label_and_must_be_mounted_by_that_service(bk: ModuleType) -> None:
    model = {
        "volumes": {"data": {"name": "openit_data"}, "other": {"name": "openit_other"}},
        "services": {
            "app": {"labels": {"io.openit.service": "model-runtime", "io.openit.backup": "files", "io.openit.backup.volume": "data", "io.openit.backup.paths": "a/state.jsonl"},
                    "volumes": [{"type": "volume", "source": "data", "target": "/x"}]},
            "db": {"labels": {"io.openit.service": "platform", "io.openit.backup": "postgres"}},
            "plain": {"volumes": [{"type": "volume", "source": "data", "target": "/y"}]},
        },
    }
    assert bk.files_in(model) == [("model-runtime", "app", "data", "openit_data", ("a/state.jsonl",))]
    assert bk.services_using(model, "data") == ["app", "plain"]
    assert bk.targets_in(model, {}) == [("platform", "db", "postgres")]  # 같은 라벨 키의 postgres 값만 데이터베이스다
    model["services"]["app"]["labels"]["io.openit.backup.volume"] = "other"  # 그 서비스가 쓰지 않는 볼륨
    with pytest.raises(bk.BackupConfigError, match="쓰는 compose 볼륨"):
        bk.files_in(model)


def test_archive_entries_lists_regular_files_with_size_and_sha256(bk: ModuleType) -> None:
    import hashlib
    import io
    import tarfile

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        folder = tarfile.TarInfo("cache")
        folder.type = tarfile.DIRTYPE
        archive.addfile(folder)
        for name, data in (("cache/b.jsonl", b"second\n"), ("cache/a.jsonl", b"first\n")):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    entries = bk.archive_entries(io.BytesIO(buffer.getvalue()))
    assert [(e.path, e.size, e.sha256) for e in entries] == [
        ("cache/a.jsonl", 6, hashlib.sha256(b"first\n").hexdigest()),
        ("cache/b.jsonl", 7, hashlib.sha256(b"second\n").hexdigest()),
    ]
    empty = io.BytesIO()
    with tarfile.open(fileobj=empty, mode="w"):
        pass
    assert bk.archive_entries(io.BytesIO(empty.getvalue())) == []  # 빈 tar 는 파일이 없다는 뜻이다
    for broken in (b"", b"not a tar file" * 100):  # 0 바이트(잘린 스트림)와 tar 가 아닌 것은 오류다
        with pytest.raises(bk.BackupConfigError):
            bk.archive_entries(io.BytesIO(broken))


def test_model_runtime_state_label_matches_the_area_source_and_the_cache_is_not_backed_up(bk: ModuleType) -> None:
    """model-runtime 의 활성화·롤백 기록이 백업 대상이고(영역 소스의 경로와 같다) 받은 패키지는 대상이 아니다. 두 쪽 경로가 어긋나면 백업이 빈 것을 받는다."""
    found = {service: (owner, key, paths) for owner, service, key, _name, paths in bk.files_in(COMPOSE)}
    assert list(found) == ["model-runtime"]
    owner, key, paths = found["model-runtime"]
    assert owner == "model-runtime" and key == "model-runtime-data"
    main = (REPO / "services" / "model-runtime" / "src" / "model_runtime" / "main.py").read_text(encoding="utf-8")
    log = (REPO / "services" / "model-runtime" / "src" / "model_runtime" / "store" / "release_log.py").read_text(encoding="utf-8")
    state_folder = re.search(r'^_STATE_FOLDER = "([^"]+)"', main, re.M).group(1)  # type: ignore[union-attr]
    log_name = re.search(r'folder / "([^"]+)"', log).group(1)  # type: ignore[union-attr]
    env = COMPOSE["services"]["model-runtime"]["environment"]["OPENIT_MODEL_CACHE_DIR"]
    mount = next(v for v in COMPOSE["services"]["model-runtime"]["volumes"] if v.startswith("model-runtime-data:")).split(":")[1]
    assert env.startswith(mount + "/")  # 캐시 폴더는 볼륨 안이다
    assert paths == (f"{env.removeprefix(mount + '/')}/{state_folder}/{log_name}",)
    assert "packages" not in paths[0]  # 받은 패키지(<상태 폴더>/packages)는 레지스트리에서 다시 받는다


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
