"""감시 설정 생성(design.md 2절 monitoring, ADR 0014, platform ADR 0005).

- 인증서 만료 감시 대상(blackbox): step-ca, 레지스트리, 공개 입구.
- 영역 /metrics 수집 대상: 노출 선언이 있는 서비스.
- 경보 수신처(Alertmanager): 수신처 주소는 파일(url_file)로 준다. 웹훅 주소에 토큰이 들어 있는 경우가 많아 설정 파일에 적지 않는다(D84).
"""

from __future__ import annotations

from urllib.parse import urlsplit

import yaml

from .contract.models import Exposure
from .pki import fmt_minutes
from .settings import PlatformSettings

RECEIVER = "operator"
HEARTBEAT_RECEIVER = "operator-heartbeat"


def tls_targets(settings: PlatformSettings, registry_local: bool) -> str:
    # 왜 renewal 라벨: ACME 로 받는 리프는 만료 24시간 전 경보를 건다. step-ca 자신의 서버 인증서는 step-ca 가 24시간 수명으로 스스로 갱신해
    # 남은 시간이 늘 24시간 아래라 같은 규칙을 걸면 항상 경보다(시험에서 확인). 그것은 접속·검증 성공(probe_success)만 본다. 조직이 준 인증서는 사람이 갈아 끼운다
    ingress_renewal = "organization" if settings.ingress_mode == "organization" else "acme"
    rows = [
        {"targets": ["step-ca:9000"], "labels": {"renewal": "ca-self"}},
        {"targets": [f"{settings.public_host}:{settings.listen_port}"], "labels": {"renewal": ingress_renewal}},
    ]
    if registry_local:
        rows.append({"targets": ["registry:443"], "labels": {"renewal": "acme"}})
    return yaml.safe_dump(rows, sort_keys=False)


def area_targets(settings: PlatformSettings, exposures: dict[str, Exposure]) -> str:
    rows = [{"targets": [f"{service}:{settings.service_port}"], "labels": {"service": service}} for service in sorted(exposures)]
    return yaml.safe_dump(rows, sort_keys=False) if rows else "[]\n"


def alertmanager_config(settings: PlatformSettings) -> str:
    receivers: list[dict[str, object]] = [{"name": RECEIVER}, {"name": HEARTBEAT_RECEIVER}]
    glob: dict[str, str] = {}
    if settings.alert_receiver_url:
        scheme = urlsplit(settings.alert_receiver_url).scheme
        for receiver in receivers:
            if scheme == "https":
                # 왜 url_file: 웹훅 주소의 경로에 토큰이 든 경우가 많아 설정 파일에 적지 않는다
                receiver["webhook_configs"] = [{"url_file": "/etc/alertmanager/receiver-url", "send_resolved": True}]
            else:
                receiver["email_configs"] = [{"to": urlsplit(settings.alert_receiver_url).path, "send_resolved": True}]
        if scheme == "mailto":
            glob = {"smtp_smarthost": settings.alert_smtp_smarthost, "smtp_from": f"openit-alerts@{settings.public_host}"}
    heartbeat = fmt_minutes(settings.alert_heartbeat_minutes)
    config: dict[str, object] = {
        **({"global": glob} if glob else {}),
        "route": {
            "receiver": RECEIVER,
            "group_by": ["alertname", "instance"],
            # 왜 이 값들: Alertmanager 의 기본값(30s, 5m, 4h)이다. 측정하지 않았다
            "group_wait": "30s",
            "group_interval": "5m",
            "repeat_interval": "4h",
            "routes": [
                {
                    "matchers": ['alertname="Watchdog"'],
                    "receiver": HEARTBEAT_RECEIVER,
                    "group_wait": "0s",
                    "group_interval": heartbeat,
                    "repeat_interval": heartbeat,
                }
            ],
        },
        "receivers": receivers,
    }
    return yaml.safe_dump(config, sort_keys=False, allow_unicode=True)


def receiver_target(settings: PlatformSettings) -> str:
    """url_file 의 내용(웹훅일 때만)."""
    return settings.alert_receiver_url + "\n" if urlsplit(settings.alert_receiver_url).scheme == "https" else ""
