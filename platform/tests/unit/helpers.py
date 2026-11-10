"""단위 시험이 함께 쓰는 입력 만들기."""

from pathlib import Path
from typing import Any

from openit_platform import pki, settings
from openit_platform.contract.models import Exposure


def platform_settings(repo: Path, **override: str) -> settings.PlatformSettings:
    env = pki.parse_env_file(repo / "deploy" / "env.example")
    env.update(override)
    return settings.platform_settings(env, repo / "deploy")


def exposure(routes: list[dict[str, Any]], egress: list[Any] | None = None) -> Exposure:
    return Exposure.model_validate({"routes": routes, "egress": egress or []})


def route(prefix: str, audience: str, methods: tuple[str, ...] = ("GET",)) -> dict[str, Any]:
    return {"path_prefix": prefix, "methods": list(methods), "audience": audience}
