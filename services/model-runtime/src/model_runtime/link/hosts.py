"""이름 표(HostsTable, OPENIT_HOSTS_TABLE_FILE): 다른 서버에 있는 레지스트리와 이웃 영역의 이름을 주소로 찾는다(ADR
0006).

표는 hosts(5)(`/etc/hosts`)와 같은 일을 한다: 표에 있는 이름만 표의 주소로 풀고 나머지는 시스템 이름 풀이에 맡긴다.
접속은 원래 이름으로 하고(TLS 서버 이름 확인과 Host 머리글이 그대로다) 주소만 바꾼다.
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

from model_runtime.contract.models import HostsTable


def read_hosts_table(path: Path) -> dict[str, str]:
    """표 파일을 계약 HostsTable 로 읽어 이름(소문자) -> 주소로 만든다. 호스트 이름은 대소문자를 가리지 않는다(RFC
    1035 2.3.3)."""
    table = HostsTable.model_validate_json(path.read_text(encoding="utf-8"))
    return {entry.name.root.lower(): str(entry.address.root.root) for entry in table.hosts}


def install_hosts_table(mapping: dict[str, str]) -> Callable[[], None]:
    """프로세스의 이름 풀이(`socket.getaddrinfo`)에 표를 먼저 적용한다. 되돌리는 함수를 돌려준다.

    왜 getaddrinfo 를 감싸나: 레지스트리 클라이언트(requests), 엔진·이웃 클라이언트(httpx)가 모두 이 함수로 이름을 푼다.
    컨테이너는 읽기 전용 루트라 `/etc/hosts` 를 고칠 수 없고, 어느 클라이언트에도 같은 표가 적용되어야 한다.
    """
    original: Any = socket.getaddrinfo

    def resolve(host: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        if isinstance(host, str) and (address := mapping.get(host.lower())) is not None:
            return original(address, *args, **kwargs)
        return original(host, *args, **kwargs)

    socket.getaddrinfo = resolve

    def restore() -> None:
        socket.getaddrinfo = original

    return restore
