"""저장소 참조(레지스트리 이름, 저장소 경로, digest 또는 태그)를 ORAS 의 Container 로 만든다.

게시·받기·목록이 같은 길을 쓴다.
"""

# oras 는 형 선언이 없는 라이브러리라 그 경계에서만 pyright 의 Unknown 보고를 끈다
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import oras.container
import oras.defaults


def oci_container(
    hostname: str, repository: str, *, digest: str | None = None, tag: str | None = None
) -> oras.container.Container:
    """레지스트리 `hostname` 의 저장소 `repository` 를 가리키는 Container.

    왜 문자열(`호스트/저장소@digest`)을 ORAS 에 넘겨 풀게 하지 않고 칸을 직접 채우나: ORAS 의 참조 정규식은 첫 조각에
    점이나 콜론이 있어야 레지스트리 이름으로 본다(docker 참조 규칙). 이름이 `registry` 같은 한 낱말이면 저장소 경로의
    일부로 읽어 `/v2/registry/<저장소>/…` 로 간다. 레지스트리 이름은 설치 값으로 알고 있으므로 추측하게 두지 않는다.
    """
    container = oras.container.Container(repository, registry=hostname)
    path = repository.strip("/")
    namespace, _, name = path.rpartition("/")
    container.registry = hostname
    container.namespace = namespace or None
    container.repository = name
    container.digest = digest
    container.tag = tag or oras.defaults.default_tag
    return container
