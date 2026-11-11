"""배치 설정(계약 DeploymentLayout)을 읽어 서버마다 무엇을 어떻게 띄울지 정한다(ADR 0026). docker 를 부르지 않는 순수 계산이다.

- 읽기: `OPENIT_LAYOUT_FILE`(기본 `deploy/layout.json`)을 계약 스키마(JSON Schema 2020-12 에서 생성한 타입)로 검증하고, 계약이 말하지 않는 구조 규칙
  (서비스는 정확히 한 서버, 서버 이름·주소는 겹치지 않음)을 더 본다. 파일이 없으면 서버 한 대(이 관리 노드의 엔진)에 전부 띄운다(지금 동작).
- 서버마다 compose 프로젝트 하나(엔진이 서버마다 다르다). 서비스 선택은 compose 서비스의 라벨 `io.openit.service` 가 정한다(정본은 compose.yaml 한 곳).
- 서버를 넘는 길: 서버마다 가장자리 Envoy(area-edge), 이름→주소는 compose `extra_hosts`, 서버 사이에 열 포트는 호출 관계에서 계산한다.
- 원격 엔진은 관리 노드의 파일 경로를 모른다(bind mount 는 엔진 호스트의 경로다). 여러 서버일 때 파일은 엔진 API 로 서버의 스테이징 폴더에 올리고
  그 경로를 bind mount 한다(마운트의 뜻은 서버 한 대일 때와 같다).
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import socket
import tarfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

SERVICE_LABEL = "io.openit.service"  # compose 서비스가 어느 계약 서비스(ServiceName)에 속하는지. 값 `layout` 은 배치가 만드는 서비스(가장자리)다
LAYOUT_LABEL_VALUE = "layout"
PLATFORM = "platform"
AREA_SERVICES = ("survey-service", "model-runtime", "admin-console", "kiosk-frontend")  # 영역 게이트웨이를 가진 서비스
SERVICE_NAMES = (PLATFORM, *AREA_SERVICES)  # 계약 ServiceName 의 값 5개
EDGE = "area-edge"
STEP_CA = "step-ca"
STEP_CA_PORT = 9000  # ca.json 의 address(:9000)
REGISTRY_PORT = 443
ACME_PORT = 80
MONITOR_PORT = 9100
STAGE_DIR = "files"
MANAGER = "관리 노드"
LOCAL_SERVER = "local"  # 배치 파일이 없을 때의 서버 이름


class LayoutError(Exception):
    """배치 설정이 틀렸다. 문제 목록을 담는다."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Server:
    name: str
    address: str
    services: tuple[str, ...]

    @property
    def areas(self) -> tuple[str, ...]:
        """영역 게이트웨이를 가진 서비스들(이 서버에서 도는 것)."""
        return tuple(s for s in self.services if s in AREA_SERVICES)

    @property
    def bind(self) -> str:
        """게시 포트를 묶을 주소. IP 면 그 주소, 호스트 이름이면 모든 인터페이스(도커는 포트를 이름에 묶지 못한다)."""
        try:
            ipaddress.IPv4Address(self.address)
        except ValueError:
            return "0.0.0.0"  # noqa: S104  왜: 호스트 이름은 포트 게시의 주소가 될 수 없다. 방화벽이 닿는 곳을 정한다
        return self.address


@dataclass(frozen=True)
class Backup:
    """계약 DeployBackupConfig(배치 설정의 backup 칸). 파일 경로는 관리 노드(./deploy 를 실행하는 곳)의 절대 경로다."""

    repository_url: str
    password_file: str
    http_credentials_file: str
    encryption_key_file: str
    offsite_url: str
    offsite_credentials_file: str


@dataclass(frozen=True)
class Layout:
    servers: tuple[Server, ...]
    explicit: bool
    placements: tuple[tuple[str, str], ...] = ()  # 계약 DevicePlacement: (기기 ID, 기본 문진표). 배치 설정 파일이 있을 때만 있다
    backup: Backup | None = None  # 배치 설정 파일이 있을 때만 있다(계약상 필수 칸). 없으면 백업을 시작하지 않는다

    @property
    def multi(self) -> bool:
        return len(self.servers) > 1

    @property
    def platform(self) -> Server:
        return self.server_of(PLATFORM)

    def server_of(self, service: str) -> Server:
        return next(s for s in self.servers if service in s.services)

    def project_name(self, base: str, server: Server) -> str:
        """서버가 하나면 설정한 이름 그대로(지금 동작), 여럿이면 서버 이름을 붙인다(엔진은 다르지만 한 엔진에 시험으로 올릴 수도 있다)."""
        return f"{base}-{server.name}" if self.multi else base

    def order(self) -> list[Server]:
        """띄우는 순서: 플랫폼 서버(신뢰의 뿌리, 레지스트리) -> 나머지. 내리는 순서는 이것의 반대다."""
        return [self.platform, *(s for s in self.servers if s is not self.platform)]


def implicit_layout() -> Layout:
    return Layout((Server(LOCAL_SERVER, "127.0.0.1", SERVICE_NAMES),), explicit=False)


def structure_problems(servers: Iterable[Server]) -> list[str]:
    """계약 스키마가 말하지 않는 구조 규칙. 비어 있으면 통과."""
    items = list(servers)
    problems: list[str] = []
    names = [s.name for s in items]
    problems += [f"서버 이름이 겹친다: {n}" for n in sorted({n for n in names if names.count(n) > 1})]
    addresses = [s.address for s in items]
    problems += [f"서버 주소가 겹친다: {a} (한 주소에 같은 포트를 두 번 게시할 수 없다. 서비스를 한 서버로 합친다)" for a in sorted({a for a in addresses if addresses.count(a) > 1})]
    for server in items:
        if not server.services:
            problems.append(f"서버 {server.name} 에 서비스가 없다(서버마다 서비스가 하나 이상이다)")
        if ":" in server.address:
            problems.append(f"서버 {server.name} 의 주소 {server.address}: IPv6 주소는 지원하지 않는다(IPv4 주소나 호스트 이름)")
    placed = [svc for s in items for svc in s.services]
    for service in SERVICE_NAMES:
        count = placed.count(service)
        if count == 0:
            problems.append(f"서비스 {service} 가 어느 서버에도 없다(모든 서비스를 정확히 한 서버에 둔다)")
        elif count > 1:
            problems.append(f"서비스 {service} 가 {count}개 서버에 있다(한 서비스는 한 서버에서만 돈다)")
    return problems


def placement_problems(placements: Iterable[tuple[str, str]]) -> list[str]:
    """한 기기에 기본 문진표가 둘이면 어느 것이 기본인지 정할 수 없다(survey-service 는 기기 ID 로 하나를 고른다). 비어 있으면 통과."""
    devices = [device for device, _ in placements]
    return [f"기기 {device} 의 기본 문진표가 여러 개다(기기마다 하나)" for device in sorted({d for d in devices if devices.count(d) > 1})]


def placement_table(placements: Iterable[tuple[str, str]]) -> str:
    """survey-service 가 파일로 받는 기기별 기본 문진표 배치표(계약 DevicePlacementTable, SURVEY_DEVICE_PLACEMENTS_FILE)의 JSON 글자.

    왜 DevicePlacement 로 한 줄씩 검증한다: 배치 설정이 쓰는 계약 타입이고, 표는 그 줄의 목록 하나뿐이다(DevicePlacementTable 은 survey-service 의 타입이라 이 도구가 생성하는 타입에 없다).
    받는 쪽이 표 전체를 같은 스키마로 읽는지는 시험이 계약 스키마로 확인한다. 배치가 없으면 빈 표다(그러면 survey-service 는 활성 문진표가 하나일 때만 정한다).
    """
    from openit_platform.contract.models import DevicePlacement  # noqa: PLC0415

    rows = [DevicePlacement.model_validate({"device_id": d, "questionnaire_id": q}).model_dump(mode="json") for d, q in placements]
    return json.dumps({"placements": rows}, indent=2, ensure_ascii=False) + "\n"


def load_layout(path: Path | None) -> Layout:
    """배치 파일을 읽는다. path 가 None 이면 서버 한 대 배치. 파일이 있는데 틀리면 LayoutError."""
    if path is None:
        return implicit_layout()
    if not path.is_file():
        raise LayoutError([f"배치 설정 파일이 없다: {path}"])
    from openit_platform.contract.models import DeploymentLayout  # noqa: PLC0415

    try:
        parsed = DeploymentLayout.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise LayoutError([f"{path.name} 이 계약 DeploymentLayout 을 어겼다: {error}"]) from error
    servers = tuple(
        Server(item.name.root, _text(item.address), tuple(_text(service) for service in item.services)) for item in parsed.servers
    )
    placements = tuple((_text(item.device_id), _text(item.questionnaire_id)) for item in parsed.device_placements)
    backup = Backup(**{name: _text(getattr(parsed.backup, name)) for name in Backup.__dataclass_fields__})
    problems = structure_problems(servers) + placement_problems(placements)
    if problems:
        raise LayoutError(problems)
    return Layout(servers, explicit=True, placements=placements, backup=backup)


def _text(value: Any) -> str:
    """계약 타입(RootModel·열거형)의 값 글자."""
    while hasattr(value, "root"):
        value = value.root
    return str(getattr(value, "value", value))


# ---------------------------------------------------------------- 서버 사이 호출과 열어야 하는 포트


@dataclass(frozen=True)
class Flow:
    src: str  # 서버 이름 또는 MANAGER
    dst: str  # 서버 이름
    port: int
    purpose: str


def flows(
    layout: Layout,
    *,
    service_port: int,
    listen_port: int,
    registry_local: bool,
    egress: dict[str, list[tuple[str, int]]],
    public_hosts: tuple[str, ...],
    registry_hosts: tuple[str, ...],
    backup_port: int | None = None,
) -> list[Flow]:
    """서버를 넘는 호출 목록. egress: 서비스 -> 나가는 터널이 닿는 (호스트, 포트). 서버 한 대면 비어 있다. backup_port: 백업 저장소의 포트(배치 설정에 backup 이 있을 때)."""
    if not layout.multi:
        return []
    platform = layout.platform
    found: list[Flow] = []

    def add(src: str, dst: str, port: int, purpose: str) -> None:
        item = Flow(src, dst, port, purpose)
        if src != dst and item not in found:
            found.append(item)

    for server in layout.servers:
        for area in server.areas:
            add(platform.name, server.name, service_port, f"입구가 {area} 의 영역 게이트웨이를 부른다(TLS, SNI 통과)")
            add(platform.name, server.name, MONITOR_PORT, f"감시가 {area} 의 상태·지표를 읽는다(평문, 플랫폼 서버에서만 열어 준다)")
            add(platform.name, server.name, ACME_PORT, f"사설 CA 가 {area} 의 인증서 발급을 검증한다(ACME http-01, RFC 8555 8.3)")
            add(server.name, platform.name, STEP_CA_PORT, f"{area} 의 영역 게이트웨이가 사설 CA 에서 인증서를 받는다(ACME)")
        if server is not platform:
            if registry_local:
                add(server.name, platform.name, REGISTRY_PORT, "서버의 엔진이 영역 이미지를 레지스트리에서 받는다")
        for service in server.services:
            for host, port in egress.get(service, []):
                target = _target_server(layout, host, public_hosts, registry_hosts)
                if target is None:
                    continue  # 서버 밖 상대(푸시 서비스 등)는 이 배치가 정하지 않는다
                add(server.name, target.name, port, f"{service} 의 나가는 터널이 {host}:{port} 에 닿는다")
    add(MANAGER, platform.name, listen_port, "관리 노드가 입구 인증서를 점검한다(ca status)")
    if registry_local:
        add(MANAGER, platform.name, REGISTRY_PORT, "관리 노드가 레지스트리에 이미지를 올린다(bootstrap)")
    if backup_port is not None:
        add(MANAGER, platform.name, backup_port, "관리 노드가 백업 저장소에 백업을 보내고 받는다(backup·restore·offsite-sync, restic REST, TLS)")
    for server in layout.servers:
        add(MANAGER, server.name, 22, "관리 노드가 docker context(SSH)로 서버의 엔진을 다룬다")
    return found


def _target_server(layout: Layout, host: str, public_hosts: tuple[str, ...], registry_hosts: tuple[str, ...]) -> Server | None:
    if host in SERVICE_NAMES and host != PLATFORM:
        return layout.server_of(host)
    if host in public_hosts or host in registry_hosts or host == STEP_CA:
        return layout.platform
    return None


def published_ports(flow_list: Iterable[Flow], server: Server) -> list[int]:
    """이 서버가 게시해야 하는 포트(다른 곳에서 이 서버로 오는 호출의 포트, SSH 는 서버의 일이라 뺀다)."""
    return sorted({f.port for f in flow_list if f.dst == server.name and f.port != 22})


def port_problems(layout: Layout, flow_list: list[Flow], *, service_port: int, listen_port: int, registry_local: bool, backup_port: int | None = None) -> list[str]:
    """한 서버 안에서 게시 포트가 겹치는 것(입구와 영역 가장자리 등)."""
    problems: list[str] = []
    for server in layout.servers:
        owners: dict[int, list[str]] = {}
        for port in published_ports(flow_list, server):
            for owner in port_owners(layout, server, port, service_port=service_port, listen_port=listen_port, registry_local=registry_local, backup_port=backup_port):
                owners.setdefault(port, []).append(owner)
        for port, names in owners.items():
            if len(names) > 1:
                problems.append(f"서버 {server.name} 의 게시 포트 {port} 를 {', '.join(names)} 가 함께 쓴다. 설치 값(OPENIT_LISTEN_PORT 와 OPENIT_SERVICE_PORT)을 다르게 한다")
    return problems


def port_owners(layout: Layout, server: Server, port: int, *, service_port: int, listen_port: int, registry_local: bool, backup_port: int | None = None) -> list[str]:
    """이 서버의 이 포트를 게시하는 컨테이너들."""
    owners: list[str] = []
    is_platform = server is layout.platform
    if is_platform and port == listen_port:
        owners.append("ingress-acme")
    if is_platform and port == STEP_CA_PORT:
        owners.append(STEP_CA)
    if is_platform and registry_local and port == REGISTRY_PORT:
        owners.append("registry")
    if is_platform and backup_port is not None and port == backup_port:
        owners.append("backup")
    if server.areas and port in (service_port, ACME_PORT, MONITOR_PORT):
        owners.append(EDGE)
    return owners


# ---------------------------------------------------------------- 이름 -> 주소(compose extra_hosts)


def resolve_ip(address: str, resolver: Callable[[str], str] | None = None) -> str:
    """extra_hosts 는 이름이 아니라 IP 를 받는다. 서버 주소가 호스트 이름이면 관리 노드에서 IPv4 로 풀어 본다."""
    try:
        return str(ipaddress.IPv4Address(address))
    except ValueError:
        pass
    try:
        return (resolver or socket.gethostbyname)(address)
    except OSError as error:
        raise LayoutError([f"서버 주소 {address} 를 IPv4 주소로 풀지 못했다: {error}"]) from error


def hosts_for(
    layout: Layout,
    server: Server,
    *,
    resolver: Callable[[str], str] | None = None,
    platform_names: Iterable[str],
    remote_areas_wanted: bool = True,
) -> dict[str, str]:
    """이 서버의 컨테이너가 서버 밖 이름을 찾을 이름 표(이름 -> IP). 같은 서버 안의 이름은 compose 네트워크 별칭이 푼다.

    platform_names: 플랫폼 서버에 있는 이름들(사설 CA, 레지스트리 이름, 입구 이름).
    """
    table: dict[str, str] = {}
    if server is not layout.platform:
        ip = resolve_ip(layout.platform.address, resolver)
        for name in platform_names:
            table[name] = ip
    if remote_areas_wanted:
        for area in AREA_SERVICES:
            owner = layout.server_of(area)
            if owner is not server:
                table[area] = resolve_ip(owner.address, resolver)
    return dict(sorted(table.items()))


def acme_host(acme_directory_url: str) -> str:
    return urlsplit(acme_directory_url).hostname or STEP_CA


# ---------------------------------------------------------------- compose: 서비스 선택과 순서


def services_in(
    model: dict[str, Any],
    layout: Layout,
    server: Server,
    *,
    registry_local: bool,
    inference_local: bool,
    backup_local: bool = False,
) -> list[str]:
    """compose 모델(`docker compose config --format json`)에서 이 서버가 띄울 서비스들.

    라벨 io.openit.service 가 이 서버의 서비스이거나(가장자리는 서버가 여럿일 때만), 라벨이 있는데 프로파일로 막혀 있으면 그 프로파일을 켠 경우만 낸다.
    """
    active = {"layout-edge"} if layout.multi else set()
    if registry_local:
        active.add("local-registry")
    if inference_local:
        active.add("inference-engine")
    if backup_local:
        active.add("backup")
    chosen: list[str] = []
    for name, spec in sorted(model.get("services", {}).items()):
        owner = (spec.get("labels") or {}).get(SERVICE_LABEL)
        wanted = owner in server.services or (owner == LAYOUT_LABEL_VALUE and layout.multi and bool(server.areas))
        if wanted and set(spec.get("profiles") or []) <= active:
            chosen.append(name)
    return chosen


def unlabeled_services(model: dict[str, Any]) -> list[str]:
    """라벨이 없는 compose 서비스(어느 서버에도 배정되지 않는다). 도구 서비스(profiles: [tools])는 뺀다."""
    return sorted(
        name
        for name, spec in model.get("services", {}).items()
        if SERVICE_LABEL not in (spec.get("labels") or {}) and "tools" not in (spec.get("profiles") or [])
    )


def tiers(model: dict[str, Any], selected: list[str]) -> list[list[str]]:
    """depends_on 순서로 층을 나눈다(같은 층은 한 번에 띄운다). `--no-deps` 로 띄우면 compose 가 층 사이 순서를 지키지 않으므로 우리가 지킨다.

    왜 service_started 는 같은 층이다: `up --wait` 는 층의 모든 서비스가 healthy 가 될 때까지 기다린다. 영역 게이트웨이는 같은 서버의 가장자리(area-edge)가 뜬 뒤에야 healthy 가
    되는데(인증서 발급이 가장자리를 지난다), 가장자리는 게이트웨이가 시작된 뒤에 시작해야 한다(server_override, ADR 0029). 가장자리를 게이트웨이보다 앞 층에 두면 이름을 먼저 풀어
    첫 검증이 실패하고, 뒤 층에 두면 서로를 기다린다. compose 는 한 번의 `up --no-deps` 안에서 선택한 서비스끼리의 service_started 순서를 지킨다(시험에서 확인).
    그래서 service_started 의존은 상대와 같은 층에, 그 밖의 의존(service_healthy 등)은 상대의 다음 층에 둔다.
    """
    chosen = set(selected)
    needs: dict[str, dict[str, bool]] = {  # 이름 -> {의존 이름: 시작만 되면 되는가}
        name: {d: (spec or {}).get("condition") == "service_started" for d, spec in (model["services"][name].get("depends_on") or {}).items() if d in chosen}
        for name in selected
    }
    level: dict[str, int] = {}
    visiting: set[str] = set()

    def depth(name: str) -> int:
        if name in level:
            return level[name]
        if name in visiting:
            raise LayoutError([f"depends_on 가 순환한다: {', '.join(sorted(visiting))}"])
        visiting.add(name)
        level[name] = max((depth(dep) + (0 if started else 1) for dep, started in needs[name].items()), default=0)
        visiting.discard(name)
        return level[name]

    for name in selected:
        depth(name)
    return [sorted(name for name in selected if level[name] == n) for n in range(max(level.values(), default=-1) + 1)]


# ---------------------------------------------------------------- compose 덮개(override) 파일


class _Override(list):  # type: ignore[type-arg]
    """`!override` 시퀀스(합치지 않고 바꾼다)."""


class _Reset(list):  # type: ignore[type-arg]
    """`!reset` 시퀀스(비운다)."""


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:
        return True


_Dumper.add_representer(_Override, lambda d, data: d.represent_sequence("!override", list(data)))
_Dumper.add_representer(_Reset, lambda d, data: d.represent_sequence("!reset", list(data)))


def override_ports(ports: list[str]) -> _Override:
    return _Override(ports)


def dump_yaml(document: dict[str, Any], header: str) -> str:
    return f"# {header}\n" + yaml.dump(document, Dumper=_Dumper, sort_keys=False, allow_unicode=True)


def server_override(
    layout: Layout,
    server: Server,
    *,
    flow_list: list[Flow],
    hosts: dict[str, str],
    step_ca: tuple[str, str] | None,
    service_port: int,
    listen_port: int,
    registry_local: bool,
    backup_port: int | None = None,
) -> dict[str, Any]:
    """여러 서버일 때 이 서버의 compose 덮개: 가장자리의 포트·네트워크, 영역 게이트웨이의 바깥 길, 이름 표, 플랫폼 서버의 고정 게시 포트.

    제품 compose.yaml 은 그대로이고(설치처 차이는 설정 값, ADR 0015) 서버 한 대일 때는 이 덮개를 쓰지 않는다.
    """
    services: dict[str, Any] = {}
    published = set(published_ports(flow_list, server))
    is_platform = server is layout.platform
    hosts_list = [f"{name}:{ip}" for name, ip in hosts.items()]
    if is_platform:
        # 왜 고정 게시: 다른 서버가 이 서버의 포트를 이름으로 찾는다. 고정 포트 없음 규칙(스모크가 포트를 겹치지 않게)은 한 서버에 설치 하나인 제품 배치에 쓰지 않는다
        if listen_port in published:
            services["ingress-acme"] = {"ports": override_ports([f"{server.bind}:{listen_port}:{listen_port}"])}
        if STEP_CA_PORT in published:
            # 왜 edge: backend 는 internal 네트워크라 거기에만 붙은 컨테이너의 게시 포트는 열리지 않는다(시험에서 확인)
            services[STEP_CA] = {"ports": [f"{server.bind}:{STEP_CA_PORT}:{STEP_CA_PORT}"], "networks": {"edge": {}}}
        if registry_local and REGISTRY_PORT in published:
            services["registry"] = {"ports": override_ports([f"{server.bind}:{REGISTRY_PORT}:{REGISTRY_PORT}"])}
        if backup_port is not None and backup_port in published:
            # 왜 서버 주소에 게시: 관리 노드가 백업을 보내는 길이다. 백업 앞단은 이미 edge 에 있다(compose.yaml)
            services["backup"] = {"ports": override_ports([f"{server.bind}:{backup_port}:{backup_port}"])}
        for name in ("ingress-acme", STEP_CA, "prometheus"):
            if hosts_list:
                services.setdefault(name, {})["extra_hosts"] = list(hosts_list)
        if hosts_list:
            # 왜 edge: 다른 서버의 9100 을 긁으려면 바깥으로 나가는 길이 필요하다(backend 는 internal 이라 길이 없다. 시험에서 확인)
            services["prometheus"]["networks"] = {"edge": {}}
    for area in server.areas:
        # 왜 가장자리를 기다린 뒤 Caddy 를 시작한다: 게이트웨이는 시작하자마자 ACME 주문을 내고 사설 CA 는 곧바로 서비스 이름의 80 번(가장자리)으로 http-01 검증을 보낸다.
        # 가장자리가 아직 듣지 않으면 검증이 한 번 실패하고, step-ca 는 그 주문을 다시 검증하지 않아 Caddy 의 ACME 클라이언트가 약 5분(acmez 의 권한 확인 상한) 뒤에 포기하고
        # 1분 뒤 새 주문을 낸다(시험에서 측정: 가장자리를 늦게 올리면 인증서까지 약 366초, 게이트웨이 건강 확인의 상한(start_period 10초 + 5초 x 60)은 약 310초).
        # 가장자리는 이 게이트웨이가 시작된 뒤에 시작해(아래 depends_on) 시작할 때 게이트웨이 이름을 풀고(STRICT_DNS), 게이트웨이는 가장자리의 80 번이 열린 것(사건)을 보고 Caddy 를 시작한다.
        # busybox nc(-w 1)는 연결이 되면 0 이다. 폴링 간격 0.2초는 사건을 보는 주기일 뿐 기다리는 시간이 아니다(가장자리가 끝내 안 뜨면 compose 건강 확인이 unhealthy 로 끝낸다)
        gateway: dict[str, Any] = {
            "command": ["sh", "-c", f"until nc -w 1 {EDGE} {ACME_PORT} </dev/null; do sleep 0.2; done; exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile"],
        }
        if not is_platform:
            # 왜 edge: 이 서버의 영역 게이트웨이가 다른 서버의 사설 CA 에서 ACME 로 인증서를 받아야 한다(서비스 컨테이너는 안쪽 네트워크에만 둔다)
            gateway["networks"] = {"edge": {}}
            if step_ca is not None:
                gateway["extra_hosts"] = [f"{step_ca[0]}:{step_ca[1]}"]
        if gateway:
            services[f"{area}-gateway"] = gateway
    if server.areas:
        edge_networks: dict[str, Any] = {"backend": {}, "edge": {}}  # edge: 게시 포트(internal 네트워크에는 게시가 안 된다)와 나가는 터널의 바깥 길
        if not is_platform:
            for area in server.areas:
                edge_networks[f"{area}-area"] = {"aliases": ["gateway"]}  # 서비스의 OPENIT_EGRESS_PROXY(http://gateway:<포트>)가 이 가장자리를 가리킨다
        edge: dict[str, Any] = {
            "depends_on": {f"{area}-gateway": {"condition": "service_started"} for area in server.areas},
            "networks": edge_networks,
            "ports": [f"{server.bind}:{port}:{port}" for port in sorted(published & {service_port, ACME_PORT, MONITOR_PORT})],
        }
        if hosts_list and not is_platform:
            edge["extra_hosts"] = list(hosts_list)
        services[EDGE] = edge
    return {"services": services}


# ---------------------------------------------------------------- 원격 엔진에 파일 올리기(bind mount 대신 이름 있는 볼륨)


@dataclass(frozen=True)
class StageEntry:
    source: Path
    rel: str  # 볼륨 안 경로(STAGE_DIR/<해시>/<이름>)


def _entry(source: str) -> StageEntry:
    path = Path(source)
    return StageEntry(path, f"{STAGE_DIR}/{hashlib.sha256(source.encode()).hexdigest()[:16]}/{path.name}")


def stage_plan(model: dict[str, Any], selected: list[str], *, root: str) -> tuple[list[StageEntry], dict[str, Any], dict[str, list[str]]]:
    """선택한 서비스의 bind mount 와 파일 비밀을 서버의 스테이징 폴더(root, 엔진 호스트의 경로) 아래 경로의 bind mount 로 바꾸는 덮개와, 올릴 파일 목록.

    왜: `docker compose` 의 bind mount·file 비밀은 엔진 호스트의 경로다. 원격 엔진에는 관리 노드의 경로가 없다. 스테이징 폴더는 엔진 API(docker run -i 로 tar 를 푼다)로 채운다.
    왜 이름 있는 볼륨의 subpath 가 아닌가: 이미 있는 파일 위(이미지에 있는 /etc/caddy/Caddyfile 등)에 파일 subpath 를 마운트하면 엔진(moby 28.5.1)이
    'not a directory' 로 컨테이너를 만들지 못한다(시험에서 확인). bind mount 는 그 경우에도 된다.
    """
    entries: dict[str, StageEntry] = {}
    users: dict[str, list[str]] = {}  # 볼륨 안 경로 -> 그것을 마운트하는 서비스들
    services: dict[str, Any] = {}
    top_secrets = model.get("secrets", {})
    for name in selected:
        spec = model["services"][name]
        mounts: list[dict[str, Any]] = []
        for volume in spec.get("volumes") or []:
            if volume.get("type") != "bind":
                continue
            entry = entries.setdefault(volume["source"], _entry(volume["source"]))
            users.setdefault(entry.rel, []).append(name)
            mounts.append(_mount(root, entry, volume["target"], bool(volume.get("read_only"))))
        secrets = spec.get("secrets") or []
        for secret in secrets:
            definition = top_secrets.get(secret["source"], {})
            if "file" not in definition:
                raise LayoutError([f"서비스 {name} 의 비밀 {secret['source']} 는 file 이 아니다(여러 서버 배치는 file 비밀만 올린다)"])
            entry = entries.setdefault(definition["file"], _entry(definition["file"]))
            users.setdefault(entry.rel, []).append(name)
            mounts.append(_mount(root, entry, secret["target"], True))
        if mounts or secrets:
            item: dict[str, Any] = {"volumes": mounts}
            if secrets:
                item["secrets"] = _Reset()  # 같은 대상을 위 볼륨 마운트가 이미 채운다
            services[name] = item
    document: dict[str, Any] = {"services": services}
    return sorted(entries.values(), key=lambda e: e.rel), document, users


def _mount(root: str, entry: StageEntry, target: str, read_only: bool) -> dict[str, Any]:
    return {"type": "bind", "source": f"{root}/{entry.rel}", "target": target, "read_only": read_only, "bind": {"create_host_path": False}}


def entry_digest(entry: StageEntry) -> str:
    """올릴 파일의 내용 지문(이름, 권한, 내용). 지난번과 다르면 그 파일을 쓰는 서비스를 다시 만든다."""
    digest = hashlib.sha256()
    source = entry.source
    if source.is_symlink() or not source.exists():
        return digest.hexdigest()
    paths = [source] if source.is_file() else sorted(p for p in source.rglob("*"))
    for path in paths:
        digest.update(str(path.relative_to(source) if path != source else Path(".")).encode())
        digest.update(oct(path.stat().st_mode).encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def build_tar(entries: list[StageEntry]) -> bytes:
    """볼륨에 올릴 tar. 파일은 모양(권한)을 지키고 없는 경로는 빈 폴더로 둔다(compose 가 bind 원본을 호스트에 만드는 것과 같다)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for entry in entries:
            if entry.source.is_symlink() or not entry.source.exists():
                info = tarfile.TarInfo(entry.rel)
                info.type, info.mode = tarfile.DIRTYPE, 0o755
                archive.addfile(info)
            else:
                _add_tree(archive, entry.source, entry.rel)
    return buffer.getvalue()


def _add_tree(archive: tarfile.TarFile, source: Path, rel: str) -> None:
    archive.add(str(source), arcname=rel, recursive=True, filter=_keep_mode)


def _keep_mode(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0  # 왜 root: 올리는 쪽 사용자 번호는 서버에서 의미가 없다. 읽는 권한은 파일 모드(0644/0755)가 정한다
    info.uname = info.gname = ""
    return info


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
