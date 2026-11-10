# 0011. 저장소 경로는 레지스트리 이름과 따로 ORAS Container 로 만든다

## 상태
승인(2026-11-11, model-runtime 작업자). ADR 0008 의 결함을 고친다(E2E 첫 실행의 발견).

## 맥락
게시(`publish_registry`)와 받기(`registry`)는 `"<레지스트리>/<저장소>@<digest>"` 문자열을 ORAS 에 넘겨 풀게 했고, 태그 목록만 `requests` 로 `/v2/<저장소>/tags/list` 를 직접 불렀다. ORAS 의 참조 정규식(`oras/container.py` `docker_regex`)은 첫 조각에 점이나 콜론이 있어야 레지스트리 이름으로 본다. 기본 설치의 레지스트리 이름은 `registry`(점·콜론 없음)라 첫 조각이 저장소 경로로 읽혀 게시·받기는 `/v2/registry/<저장소>/…` 로 갔고 목록만 `/v2/<저장소>/…` 로 가서 404 → 목록이 늘 비었다. 시험용 레지스트리는 저장소 이름을 가리지 않았고 시험은 포트가 붙은 이름만 썼다.

## 결정
- `link/oci_reference.py` 의 `oci_container(hostname, repository, digest=…, tag=…)` 가 ORAS `Container` 를 칸을 직접 채워 만든다(문자열 추측 없음). 게시·받기·목록이 모두 이것을 쓰고, 태그 목록과 태그별 매니페스트 주소도 `Container.tags_url(N)`·`manifest_url(tag)` 로 같은 객체에서 얻는다(태그 쪽 나누기 `Link rel="next"` 는 그대로 따라간다).
- 시험용 레지스트리는 저장소 이름이 다르면 404(NAME_UNKNOWN)를 낸다. 시험은 이름 `registry`, `registry:443`, `registry.openit.test` 세 경우에 게시·받기·목록이 모두 `/v2/<저장소>/…` 로만 가는지 본다(한 낱말 이름은 포트 없이 443 이라 시험용 CONNECT 터널로 접속한다).
- 설치 값(레지스트리 이름)은 바꾸지 않는다.

## 왜
레지스트리 이름과 저장소 경로는 설치 값으로 이미 따로 알고 있다. 합쳐서 문자열로 만든 뒤 라이브러리가 다시 나누게 하면 이름 모양에 따라 달리 나뉜다. 표준 클라이언트(ORAS)의 `Container` 가 OCI Distribution 의 경로(`/v2/<name>/blobs|manifests|tags`)를 만드는 곳이므로 그것을 한 곳에서 쓴다.

## 검토한 대안과 버리는 이유
- **레지스트리 이름을 `registry.openit` 처럼 점이 있게 바꾼다:** 설치 값으로 결함을 피하는 우회다. 이름 모양이 맞아야만 동작하는 결합이 남는다.
- **`oras.provider.Registry.get_tags` 를 쓴다:** 404 를 예외(`ValueError`)로만 알려 '저장소 없음 = 빈 목록'(ADR 0008)과 다른 실패를 가를 수 없다. 같은 Container 의 `tags_url` 과 `do_request` 를 쓰면 같은 클라이언트·같은 경로이면서 상태 코드를 직접 본다.
- **저장소 참조에 `https://` 를 붙여 ORAS 가 풀게 한다:** 정규식이 스킴을 다루지 않는다.

## 결과
- 얻는 것: 어떤 모양의 레지스트리 이름에서도 세 호출이 같은 저장소를 본다.
- 감수하는 것: ORAS `Container` 의 칸(`namespace`, `repository`, `registry`, `tag`, `digest`)을 직접 채우므로 ORAS 가 이 속성 이름을 바꾸면 시험이 먼저 깬다. 이 변경 전에 `/v2/registry/<저장소>/…` 경로로 올라간 패키지는 새 경로에 없다(기본 설치의 기존 게시물이 있으면 다시 게시해야 한다. E2E 는 매 실행이 새 레지스트리다).

## 되돌리는 조건
ORAS 가 참조 문자열의 레지스트리 판별을 호출자가 정하게 하면(정규식 대신 명시 인자) 그 길로 바꾼다.
