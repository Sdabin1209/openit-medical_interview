"""deploy/layout.py: 배치 설정 읽기와 구조 규칙, 서비스 선택, 서버 사이 포트, compose 덮개, 파일 올리기(docker 없음, ADR 0026)."""

import io
import json
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

from .conftest import REPO, _load

sys.path.insert(0, str(REPO / "platform" / "src"))


@pytest.fixture(scope="module")
def lay() -> ModuleType:
    return _load("layout_under_test", REPO / "deploy" / "layout.py")


def servers(lay: ModuleType, a: str = "192.0.2.10", b: str = "192.0.2.20") -> list[object]:
    return [
        lay.Server("svc", a, ("platform", "survey-service", "admin-console", "kiosk-frontend")),
        lay.Server("gpu", b, ("model-runtime",)),
    ]


def layout_of(lay: ModuleType, items: list[object]) -> object:
    return lay.Layout(tuple(items), explicit=True)


def test_example_file_is_valid_against_the_contract(lay: ModuleType) -> None:
    layout = lay.load_layout(REPO / "deploy" / "layout.example.json")
    assert layout.multi and layout.platform.name == "service-01"
    assert layout.server_of("model-runtime").name == "serving-01"


def test_missing_file_means_one_server_only_when_not_given(lay: ModuleType, tmp_path: Path) -> None:
    one = lay.load_layout(None)
    assert not one.multi and set(one.platform.services) == set(lay.SERVICE_NAMES)
    with pytest.raises(lay.LayoutError):
        lay.load_layout(tmp_path / "nope.json")


def test_contract_violation_is_reported(lay: ModuleType, tmp_path: Path) -> None:
    example = json.loads((REPO / "deploy" / "layout.example.json").read_text())
    example["servers"][0]["name"] = "Bad_Name"
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(example))
    with pytest.raises(lay.LayoutError, match="DeploymentLayout"):
        lay.load_layout(path)


def test_structure_rules(lay: ModuleType) -> None:
    two = servers(lay)
    assert lay.structure_problems(two) == []
    dup = [two[0], lay.Server("gpu", "192.0.2.20", ("model-runtime", "platform"))]
    text = " ".join(lay.structure_problems(dup))
    assert "platform 가 2개" in text
    same = [two[0], lay.Server("gpu", "192.0.2.10", ("model-runtime",))]
    assert "주소가 겹친다" in " ".join(lay.structure_problems(same))
    assert any("서비스가 없다" in p for p in lay.structure_problems([*two, lay.Server("x", "192.0.2.30", ())]))


def test_project_name_only_changes_for_several_servers(lay: ModuleType) -> None:
    assert lay.implicit_layout().project_name("openit", lay.implicit_layout().platform) == "openit"
    layout = layout_of(lay, servers(lay))
    assert layout.project_name("openit", layout.server_of("model-runtime")) == "openit-gpu"
    assert [s.name for s in layout.order()] == ["svc", "gpu"]


def test_bind_address(lay: ModuleType) -> None:
    assert lay.Server("a", "192.0.2.10", ()).bind == "192.0.2.10"
    assert lay.Server("a", "host.example.org", ()).bind == "0.0.0.0"


FLOW_ARGS = {
    "service_port": 8443,
    "listen_port": 9443,
    "registry_local": True,
    "egress": {"survey-service": [("model-runtime", 8443), ("openit.internal", 9443)], "model-runtime": [("registry", 443), ("openit.internal", 9443)]},
    "public_hosts": ("openit.internal",),
    "registry_hosts": ("registry",),
}


def test_one_server_has_no_flows(lay: ModuleType) -> None:
    assert lay.flows(lay.implicit_layout(), **FLOW_ARGS) == []


def test_flows_for_two_servers(lay: ModuleType) -> None:
    layout = layout_of(lay, servers(lay))
    found = {(f.src, f.dst, f.port) for f in lay.flows(layout, **FLOW_ARGS)}
    assert ("svc", "gpu", 8443) in found  # 입구와 survey-service 가 model-runtime 을 부른다
    assert ("svc", "gpu", 9100) in found and ("svc", "gpu", 80) in found  # 감시, ACME 검증
    assert ("gpu", "svc", 9000) in found and ("gpu", "svc", 443) in found and ("gpu", "svc", 9443) in found
    assert ("svc", "svc", 8443) not in found
    assert lay.published_ports(lay.flows(layout, **FLOW_ARGS), layout.server_of("model-runtime")) == [80, 8443, 9100]
    assert lay.published_ports(lay.flows(layout, **FLOW_ARGS), layout.platform) == [443, 9000, 9443]


def test_listen_and_service_port_must_differ_on_the_platform_server(lay: ModuleType) -> None:
    layout = layout_of(lay, [lay.Server("svc", "192.0.2.10", ("platform", "survey-service", "admin-console", "kiosk-frontend")),
                             lay.Server("gpu", "192.0.2.20", ("model-runtime",))])
    args = {**FLOW_ARGS, "listen_port": 8443}
    flows = lay.flows(layout, **args)
    problems = lay.port_problems(layout, flows, service_port=8443, listen_port=8443, registry_local=True)
    # 서비스가 플랫폼 서버에서 서버 밖 호출을 받지 않으면 겹침이 없다. 받으면 겹친다
    flows.append(lay.Flow("gpu", "svc", 8443, "x"))
    problems = lay.port_problems(layout, flows, service_port=8443, listen_port=8443, registry_local=True)
    assert any("8443" in p and "ingress-acme" in p and "area-edge" in p for p in problems)


MODEL = {
    "services": {
        "step-ca": {"labels": {"io.openit.service": "platform"}, "image": "x"},
        "registry": {"labels": {"io.openit.service": "platform"}, "profiles": ["local-registry"], "depends_on": {"step-ca": {}}},
        "survey-service": {"labels": {"io.openit.service": "survey-service"}, "depends_on": {"step-ca": {}, "survey-db": {}}},
        "survey-db": {"labels": {"io.openit.service": "survey-service"}},
        "model-runtime": {"labels": {"io.openit.service": "model-runtime"}, "depends_on": {"model-runtime-gateway": {}, "inference-engine": {}}},
        "model-runtime-gateway": {"labels": {"io.openit.service": "model-runtime"}, "depends_on": {"step-ca": {}}},
        "inference-engine": {"labels": {"io.openit.service": "model-runtime"}, "profiles": ["inference-engine"]},
        "area-edge": {"labels": {"io.openit.service": "layout"}, "profiles": ["layout-edge"]},
        "registry-client": {"profiles": ["tools"]},
    }
}


def test_service_selection_by_label_and_profile(lay: ModuleType) -> None:
    layout = layout_of(lay, servers(lay))
    svc, gpu = layout.servers
    pick = lambda server, **kw: lay.services_in(MODEL, layout, server, **{"registry_local": True, "inference_local": False, **kw})  # noqa: E731
    assert pick(svc) == ["area-edge", "registry", "step-ca", "survey-db", "survey-service"]
    assert pick(gpu) == ["area-edge", "model-runtime", "model-runtime-gateway"]
    assert "inference-engine" in pick(gpu, inference_local=True)
    assert "registry" not in pick(svc, registry_local=False)
    one = lay.implicit_layout()
    assert "area-edge" not in lay.services_in(MODEL, one, one.platform, registry_local=True, inference_local=False)


def test_unlabeled_services_are_found_but_tools_are_not(lay: ModuleType) -> None:
    model = {"services": {**MODEL["services"], "stray": {}}}
    assert lay.unlabeled_services(model) == ["stray"]
    assert lay.unlabeled_services(MODEL) == []


def test_tiers_follow_depends_on_inside_the_selection(lay: ModuleType) -> None:
    assert lay.tiers(MODEL, ["model-runtime", "model-runtime-gateway"]) == [["model-runtime-gateway"], ["model-runtime"]]
    # 이 서버에 없는 의존(step-ca)은 순서에 넣지 않는다
    assert lay.tiers(MODEL, ["survey-service", "survey-db"]) == [["survey-db"], ["survey-service"]]
    cyclic = {"services": {"a": {"depends_on": {"b": {}}}, "b": {"depends_on": {"a": {}}}}}
    with pytest.raises(lay.LayoutError):
        lay.tiers(cyclic, ["a", "b"])


def test_hosts_table_names_remote_areas_and_platform_names(lay: ModuleType) -> None:
    layout = layout_of(lay, servers(lay))
    svc, gpu = layout.servers
    names = ["step-ca", "registry", "openit.internal"]
    assert lay.hosts_for(layout, svc, platform_names=names) == {"model-runtime": "192.0.2.20"}
    assert lay.hosts_for(layout, gpu, platform_names=names) == {
        "admin-console": "192.0.2.10", "kiosk-frontend": "192.0.2.10", "openit.internal": "192.0.2.10",
        "registry": "192.0.2.10", "step-ca": "192.0.2.10", "survey-service": "192.0.2.10",
    }


def test_hostname_addresses_are_resolved_to_ip(lay: ModuleType) -> None:
    assert lay.resolve_ip("192.0.2.5") == "192.0.2.5"
    assert lay.resolve_ip("gpu.example.org", lambda name: "198.51.100.7") == "198.51.100.7"
    with pytest.raises(lay.LayoutError):
        lay.resolve_ip("nope.invalid", lambda name: (_ for _ in ()).throw(OSError("x")))


def test_server_override_publishes_only_what_other_servers_call(lay: ModuleType) -> None:
    layout = layout_of(lay, servers(lay))
    svc, gpu = layout.servers
    flows = lay.flows(layout, **FLOW_ARGS)
    common = {"flow_list": flows, "service_port": 8443, "listen_port": 9443, "registry_local": True}
    over_gpu = lay.server_override(layout, gpu, hosts={"step-ca": "192.0.2.10"}, step_ca=("step-ca", "192.0.2.10"), **common)["services"]
    assert over_gpu["area-edge"]["ports"] == ["192.0.2.20:80:80", "192.0.2.20:8443:8443", "192.0.2.20:9100:9100"]
    assert set(over_gpu["area-edge"]["networks"]) == {"backend", "edge", "model-runtime-area"}
    assert over_gpu["area-edge"]["networks"]["model-runtime-area"] == {"aliases": ["gateway"]}  # OPENIT_EGRESS_PROXY 의 gateway
    assert over_gpu["model-runtime-gateway"]["extra_hosts"] == ["step-ca:192.0.2.10"]
    assert "step-ca" not in over_gpu and "registry" not in over_gpu
    over_svc = lay.server_override(layout, svc, hosts={"model-runtime": "192.0.2.20"}, step_ca=None, **common)["services"]
    assert over_svc["step-ca"]["ports"] == ["192.0.2.10:9000:9000"] and "edge" in over_svc["step-ca"]["networks"]  # internal 네트워크에는 게시가 안 된다
    assert set(over_svc["area-edge"]["networks"]) == {"backend", "edge"}
    assert over_svc["registry"]["ports"] == ["192.0.2.10:443:443"]
    assert over_svc["ingress-acme"]["ports"] == ["192.0.2.10:9443:9443"]
    assert over_svc["prometheus"]["extra_hosts"] == ["model-runtime:192.0.2.20"]
    assert over_svc["prometheus"]["networks"] == {"edge": {}}  # 다른 서버의 9100 을 긁는 바깥 길
    assert "edge" not in over_svc.get("survey-service-gateway", {}).get("networks", {})  # 플랫폼 서버의 게이트웨이는 안쪽 네트워크만


def test_gateway_waits_for_the_edge_and_the_edge_starts_after_the_gateways(lay: ModuleType) -> None:
    """ACME http-01 검증은 가장자리를 지난다. 게이트웨이는 가장자리의 80 번이 열린 뒤 Caddy 를 시작하고, 가장자리는 게이트웨이 시작 뒤에 시작해 이름을 푼다(ADR 0029)."""
    layout = layout_of(lay, servers(lay))
    svc, gpu = layout.servers
    common = {"flow_list": lay.flows(layout, **FLOW_ARGS), "service_port": 8443, "listen_port": 9443, "registry_local": True}
    over_gpu = lay.server_override(layout, gpu, hosts={"step-ca": "192.0.2.10"}, step_ca=("step-ca", "192.0.2.10"), **common)["services"]
    over_svc = lay.server_override(layout, svc, hosts={"model-runtime": "192.0.2.20"}, step_ca=None, **common)["services"]
    for over, areas in ((over_gpu, ["model-runtime"]), (over_svc, ["admin-console", "kiosk-frontend", "survey-service"])):
        for area in areas:
            command = over[f"{area}-gateway"]["command"]
            assert command[:2] == ["sh", "-c"] and "nc -w 1 area-edge 80" in command[2] and command[2].endswith("exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile")
            assert over["area-edge"]["depends_on"][f"{area}-gateway"] == {"condition": "service_started"}
        assert set(over["area-edge"]["depends_on"]) == {f"{area}-gateway" for area in areas}


def test_tiers_do_not_split_on_service_started(lay: ModuleType) -> None:
    """service_started 의존은 같은 층이다(up --wait 가 서로를 기다리지 않게). 건강 확인 의존은 층을 나눈다."""
    model = {"services": {
        "gw": {"depends_on": {"step-ca": {"condition": "service_healthy"}}},
        "edge": {"depends_on": {"gw": {"condition": "service_started"}}},
        "step-ca": {},
    }}
    assert lay.tiers(model, ["gw", "edge", "step-ca"]) == [["step-ca"], ["edge", "gw"]]


def test_override_yaml_uses_override_tag(lay: ModuleType) -> None:
    text = lay.dump_yaml({"services": {"registry": {"ports": lay.override_ports(["1.2.3.4:443:443"])}}}, "h")
    assert "ports: !override" in text


def test_stage_plan_turns_binds_and_file_secrets_into_staging_binds(lay: ModuleType, tmp_path: Path) -> None:
    conf = tmp_path / "a.conf"
    conf.write_text("x")
    secret = tmp_path / "pw"
    secret.write_text("s")
    model = {
        "services": {"svc": {"volumes": [{"type": "bind", "source": str(conf), "target": "/etc/a.conf", "read_only": True}, {"type": "volume", "source": "v", "target": "/d"}],
                             "secrets": [{"source": "pw", "target": "/run/secrets/pw"}]}},
        "secrets": {"pw": {"file": str(secret)}},
    }
    entries, document, users = lay.stage_plan(model, ["svc"], root="/var/lib/openit/stage/p")
    mounts = document["services"]["svc"]["volumes"]
    assert [m["target"] for m in mounts] == ["/etc/a.conf", "/run/secrets/pw"]
    assert all(m["type"] == "bind" and m["source"].startswith("/var/lib/openit/stage/p/files/") and m["read_only"] for m in mounts)
    assert "!reset" in lay.dump_yaml(document, "h")  # 비밀은 위 마운트가 대신한다
    assert set(users) == {e.rel for e in entries}
    with pytest.raises(lay.LayoutError):
        lay.stage_plan({"services": {"s": {"secrets": [{"source": "e", "target": "/x"}]}}, "secrets": {"e": {"environment": "V"}}}, ["s"], root="/r")


def test_tar_keeps_modes_and_makes_missing_sources_empty_dirs(lay: ModuleType, tmp_path: Path) -> None:
    folder = tmp_path / "d"
    folder.mkdir()
    (folder / "f").write_text("hello")
    (folder / "f").chmod(0o644)
    entries = [lay._entry(str(folder)), lay._entry(str(tmp_path / "missing"))]  # noqa: SLF001
    with tarfile.open(fileobj=io.BytesIO(lay.build_tar(entries))) as archive:
        members = {m.name: m for m in archive.getmembers()}
    assert members[f"{entries[0].rel}/f"].mode == 0o644 and members[f"{entries[0].rel}/f"].uid == 0
    assert members[entries[1].rel].isdir()
    before = lay.entry_digest(entries[0])
    (folder / "f").write_text("changed")
    assert lay.entry_digest(entries[0]) != before


def test_every_product_compose_service_is_assigned_to_a_service(lay: ModuleType) -> None:
    """compose.yaml 의 모든 서비스에 라벨이 있다(없으면 어느 서버에도 띄워지지 않는다). 라벨 값은 계약 ServiceName 이거나 layout 이다."""
    import yaml  # noqa: PLC0415

    model = yaml.safe_load((REPO / "deploy" / "compose.yaml").read_text(encoding="utf-8"))
    assert lay.unlabeled_services(model) == []
    values = {spec["labels"][lay.SERVICE_LABEL] for spec in model["services"].values() if lay.SERVICE_LABEL in (spec.get("labels") or {})}
    assert values <= {*lay.SERVICE_NAMES, lay.LAYOUT_LABEL_VALUE}
    assert model["services"][lay.EDGE]["profiles"] == ["layout-edge"]
    assert model["services"][lay.EDGE]["image"].split("@")[1].startswith("sha256:")  # digest 고정(image-pins)


def layout_file(tmp_path: Path, placements: list[dict[str, str]]) -> Path:
    example = json.loads((REPO / "deploy" / "layout.example.json").read_text())
    example["device_placements"] = placements
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(example))
    return path


def test_device_placements_are_read_from_the_layout_file(lay: ModuleType, tmp_path: Path) -> None:
    layout = lay.load_layout(layout_file(tmp_path, [{"device_id": "kiosk-01", "questionnaire_id": "national-health"}, {"device_id": "kiosk-02", "questionnaire_id": "dental"}]))
    assert layout.placements == (("kiosk-01", "national-health"), ("kiosk-02", "dental"))
    assert lay.load_layout(None).placements == ()


def test_two_default_questionnaires_for_one_device_are_refused(lay: ModuleType, tmp_path: Path) -> None:
    path = layout_file(tmp_path, [{"device_id": "kiosk-01", "questionnaire_id": "a"}, {"device_id": "kiosk-01", "questionnaire_id": "b"}])
    with pytest.raises(lay.LayoutError, match="kiosk-01"):
        lay.load_layout(path)


def test_placement_table_is_the_contract_table_survey_service_reads(lay: ModuleType) -> None:
    """survey-service 는 SURVEY_DEVICE_PLACEMENTS_FILE 의 내용을 DevicePlacementTable 로 읽는다. deploy 가 쓴 글이 그 스키마를 지키고 빈 배치도 유효하다."""
    import jsonschema
    import yaml

    components = yaml.safe_load((REPO / "contracts" / "components.yaml").read_text(encoding="utf-8"))["components"]
    schema = {"$ref": "#/components/schemas/DevicePlacementTable", "components": components}
    text = lay.placement_table([("kiosk-01", "national-health"), ("kiosk-02", "dental")])
    jsonschema.validate(json.loads(text), schema)
    assert json.loads(text)["placements"][1] == {"device_id": "kiosk-02", "questionnaire_id": "dental"}
    jsonschema.validate(json.loads(lay.placement_table([])), schema)
    assert json.loads(lay.placement_table([])) == {"placements": []}
    with pytest.raises(ValueError):  # 계약의 문진표 식별자 문법을 어기면 쓰지 않는다
        lay.placement_table([("kiosk-01", "not valid!")])


def test_product_compose_gives_survey_service_the_generated_placement_file() -> None:
    import yaml

    service = yaml.safe_load((REPO / "deploy" / "compose.yaml").read_text(encoding="utf-8"))["services"]["survey-service"]
    assert service["environment"]["SURVEY_DEVICE_PLACEMENTS_FILE"] == "/etc/openit/device-placements.json"
    assert "./generated/survey-service/device-placements.json:/etc/openit/device-placements.json:ro" in service["volumes"]


def test_backup_store_is_reached_by_the_manager_across_servers(lay: ModuleType) -> None:
    """여러 서버일 때 백업 저장소의 포트는 플랫폼 서버가 게시하고 관리 노드가 부른다. 서버 한 대는 게시하지 않는다."""
    layout = layout_of(lay, servers(lay))
    flows = lay.flows(layout, **FLOW_ARGS, backup_port=8000)
    assert ("관리 노드", "svc", 8000) in {(f.src, f.dst, f.port) for f in flows}
    assert 8000 in lay.published_ports(flows, layout.platform) and 8000 not in lay.published_ports(flows, layout.servers[1])
    assert lay.flows(lay.implicit_layout(), **FLOW_ARGS, backup_port=8000) == []
    common = {"flow_list": flows, "service_port": 8443, "listen_port": 9443, "registry_local": True, "backup_port": 8000}
    over_svc = lay.server_override(layout, layout.platform, hosts={}, step_ca=None, **common)["services"]
    assert over_svc["backup"]["ports"] == ["192.0.2.10:8000:8000"]
    assert "backup" not in lay.server_override(layout, layout.servers[1], hosts={}, step_ca=("step-ca", "192.0.2.10"), **common)["services"]
    assert lay.port_owners(layout, layout.platform, 8000, service_port=8443, listen_port=9443, registry_local=True, backup_port=8000) == ["backup"]


def test_backup_port_may_not_collide_with_another_published_port(lay: ModuleType) -> None:
    layout = layout_of(lay, servers(lay))
    flows = lay.flows(layout, **FLOW_ARGS, backup_port=9443)  # 입구의 게시 포트와 같다
    problems = lay.port_problems(layout, flows, service_port=8443, listen_port=9443, registry_local=True, backup_port=9443)
    assert any("9443" in p and "backup" in p for p in problems)


def test_backup_profile_is_chosen_only_for_the_platform_server_when_asked(lay: ModuleType) -> None:
    import yaml

    model = yaml.safe_load((REPO / "deploy" / "compose.yaml").read_text(encoding="utf-8"))
    layout = layout_of(lay, servers(lay))
    svc, gpu = layout.servers
    chosen = lambda server, backup: lay.services_in(model, layout, server, registry_local=True, inference_local=False, backup_local=backup)  # noqa: E731
    assert {"backup", "backup-store"} <= set(chosen(svc, True))
    assert not {"backup", "backup-store"} & set(chosen(svc, False))
    assert not {"backup", "backup-store", "backup-client"} & set(chosen(gpu, False))
