"""v3 에서만 쓰는 요청 칸(previous_screen_action)은 v2 패키지가 활성이면 쓰지 않는다.

v2 어댑터의 입력을 학습 때와 같게 두려는 것이다.
"""

from types import SimpleNamespace
from typing import Any, cast

from model_runtime.link.runtime import _for_version, _v3_only  # pyright: ignore[reportPrivateUsage]
from model_runtime.types import LoadedPackage


def _package(version: str) -> LoadedPackage:
    return cast("LoadedPackage", SimpleNamespace(model_io_version=SimpleNamespace(value=version)))


def test_extraction_uses_the_screen_action_only_for_v3() -> None:
    assert _v3_only("model-io-v3", "CONFIRM") == "CONFIRM"
    assert _v3_only("model-io-v2", "CONFIRM") is None
    assert _v3_only("model-io-v3", None) is None


def test_response_request_drops_the_screen_action_for_v2() -> None:
    request: dict[str, Any] = {"action": "NEXT", "previous_screen_action": "CONFIRM"}
    assert "previous_screen_action" not in _for_version(_package("model-io-v2"), request)
    assert _for_version(_package("model-io-v3"), request) is request
