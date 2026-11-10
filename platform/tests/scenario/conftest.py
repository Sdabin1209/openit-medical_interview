from __future__ import annotations

from collections.abc import Iterator

import pytest

from .sandbox import Sandbox


@pytest.fixture(scope="module")
def box(request: pytest.FixtureRequest) -> Iterator[Sandbox]:
    """샌드박스 설치 하나(모듈 안 시험이 함께 쓴다). 끝나면 이 프로젝트만 내리고 남은 것이 0개인지 본다."""
    sandbox = Sandbox()
    try:
        sandbox.prepare()
        sandbox.deploy("bootstrap")
        sandbox.start_test_services()
        sandbox.create_users()
        yield sandbox
    except BaseException:
        print(f"설치가 실패했다. 로그를 남겼다: {sandbox.save_logs()}")
        raise
    finally:
        if request.session.testsfailed:
            print(f"시험이 실패했다. 로그를 남겼다: {sandbox.save_logs()}")
        left = sandbox.teardown()
        assert not left, f"샌드박스 정리 뒤에 남은 것: {left}"
