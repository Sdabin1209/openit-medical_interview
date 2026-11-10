"""설치 설정에서 platform 의 생성 파일 전부를 만든다(./deploy 가 호출한다). 같은 입력은 같은 출력이다.

만드는 것(deploy/generated/ 아래, git 제외):
  gateway/envoy.yaml, gateway/egress-proxies.json, ingress/Caddyfile, identity/openit-realm.json,
  monitoring/{tls-targets.yml, area-targets.yml, alertmanager.yml, receiver-url}, platform.env, compose.platform.yaml
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import gateway, identity, ingress, monitoring, pki, settings
from .contract.models import ExposureAudience
from .settings import GATEWAY_NAME, PlatformSettings


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:  # 왜: 같은 목록이 YAML 앵커(&id001)로 나가면 사람이 읽기 어렵다
        return True


DEVICE_CA_PLACEHOLDER = "gateway/device-ca.pem"
INGRESS_ORG_DIR = "pki/ingress"  # deploy/ 기준. organization 방식의 입구 인증서 복사본


@dataclass(frozen=True)
class Generated:
    files: dict[str, str]  # generated/ 기준 상대 경로 -> 내용
    settings: PlatformSettings
    gateway: gateway.Gateway
    summary: str
    certificate_paths: tuple[str, ...]  # 입구 설정이 읽는 인증서·키의 컨테이너 안 경로(설정 검증이 같은 자리에 시험용 파일을 둔다)


def generate(env: dict[str, str], deploy_dir: Path, repo_root: Path, *, registry_local: bool) -> Generated:
    cfg = settings.platform_settings(env, deploy_dir)
    exposures = gateway.load_exposures(cfg.exposures_dir)
    allowlist = gateway.load_allowlist(cfg.device_allowlist_file)
    contracts = repo_root / "contracts"
    plan = gateway.plan(cfg, exposures, contracts, cfg.device_ca_file is not None)
    internal_key = ingress.acme_issuer_key(cfg.internal_acme_directory_url)
    ingress_key = ingress.acme_issuer_key(cfg.acme_directory_url if cfg.ingress_mode == "acme-public" else cfg.internal_acme_directory_url)
    envoy = gateway.build_envoy(cfg, plan, allowlist, ingress_key, internal_key)
    machine = identity.load_machine_table(cfg.machine_tokens_file)
    exposed = {service: sorted({route.audience for route in exposure.routes}, key=lambda a: a.value) for service, exposure in exposures.items()}
    realm = identity.render_realm(cfg, identity.human_audiences(exposed), machine, identity.machine_role_services(contracts))
    cert_file, key_file = gateway.ingress_certificate_paths(cfg, ingress_key)
    client_cert, client_key = gateway.gateway_client_paths(internal_key)
    names = [GATEWAY_NAME] + ([] if cfg.ingress_mode == "organization" else list(cfg.public_names))
    aliases = sorted({*names, *cfg.public_names})
    override = {"services": {"ingress-acme": {"networks": {"backend": {"aliases": aliases}, "edge": {"aliases": aliases}}}}}
    agent_cert = client_cert if cfg.ingress_mode == "organization" else cert_file
    env_lines = {
        "OPENIT_PUBLIC_BASE_URL": cfg.public_base_url,
        # 왜 4/5: 접근 토큰이 만료되기 전에 갱신한다. 왜 10h: Keycloak 의 SSO Session Max 기본값(10시간)이다.
        # 그 뒤에는 갱신 토큰이 거절되어 다시 로그인해야 한다. 측정하지 않았다(platform ADR 0004)
        "OPENIT_PROXY_COOKIE_REFRESH": f"{identity.ACCESS_TOKEN_SECONDS * 4 // 5}s",
        "OPENIT_PROXY_COOKIE_EXPIRE": "10h",
        "OPENIT_INGRESS_CERT_FILE": cert_file,
        "OPENIT_GATEWAY_CERT_FILE": client_cert,
        "OPENIT_AGENT_CERT_FILE": agent_cert,
        "OPENIT_DEVICE_CA_MOUNT": str((deploy_dir / "generated" / DEVICE_CA_PLACEHOLDER).resolve()),
        "OPENIT_INGRESS_ORG_MOUNT": str((deploy_dir / INGRESS_ORG_DIR).resolve()),
    }
    files = {
        "gateway/envoy.yaml": gateway.render(envoy),
        **{f"gateway/sds/{name}": text for name, text in gateway.build_sds(cfg, ingress_key, internal_key).items()},
        "gateway/egress-proxies.json": json.dumps(gateway.egress_manifest(cfg, plan), indent=2, sort_keys=True) + "\n",
        "ingress/Caddyfile": ingress.render_caddyfile(cfg),
        "identity/openit-realm.json": identity.render_realm_text(realm),
        "monitoring/tls-targets.yml": monitoring.tls_targets(cfg, registry_local),
        "monitoring/area-targets.yml": monitoring.area_targets(cfg, exposures),
        "monitoring/alertmanager.yml": monitoring.alertmanager_config(cfg),
        "monitoring/receiver-url": monitoring.receiver_target(cfg),
        "platform.env": "# ./deploy 가 만든다. compose 가 읽는 파생 값이다. 손으로 고치지 않는다.\n" + "".join(f"{k}={v}\n" for k, v in env_lines.items()),
        "compose.platform.yaml": "# ./deploy 가 만든다. 입구 에이전트가 가질 이름(입구 이름과 gateway)이다. 손으로 고치지 않는다.\n"
        + yaml.dump(override, Dumper=_NoAliasDumper, sort_keys=False),
    }
    human = any(ExposureAudience.HUMAN_OIDC in a for a in exposed.values())
    summary = gateway.summary(plan) + f"\n기계 호출자 {len(machine.tokens)}명, 기기 허용 {len(allowlist.devices)}대" + ("" if human else "\n(사람 인증 경로 없음)")
    return Generated(files=files, settings=cfg, gateway=plan, summary=summary, certificate_paths=(cert_file, key_file, client_cert, client_key))


def device_ca_copy(cfg: PlatformSettings) -> str:
    """생성 폴더에 둘 기기 CA 사본 내용(없으면 빈 파일). 입구가 검증에 쓰는 신뢰 앵커는 조직 PKI 의 루트다(ADR 0015)."""
    if cfg.device_ca_file is None:
        return ""
    return pki.pem_text(pki.load_certs(cfg.device_ca_file))
