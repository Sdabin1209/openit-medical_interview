"""백업·복구의 순수 계산(ADR 0027). docker 를 부르지 않는다. 명령(backup, restore, restore-test, offsite-sync)의 조립은 ./deploy 가 한다.

- 백업 설정(계약 DeployBackupConfig)을 읽는 규칙: 저장소 주소, 자격 파일의 모양, 서버 밖 대상.
- 백업 한 번의 내용 목록(manifest): 어느 영역의 어느 DB 컨테이너에서 어떤 데이터베이스를 받았는가.
- 잡 실행 결과 한 줄(계약 JobRunResult).
"""

from __future__ import annotations

import ipaddress
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

# 왜 14일: 사용자 결정 2026-11-03(U31: 매일, 14일)과 D88 U4(백업 14일 일일). 백업 보관 기간은 운영 데이터의 가장 짧은 보존 기간 이하여야 한다(OPEN_GAPS U30:
# 운영 DB 에서 이미 지운 데이터가 백업에 남지 않게). 가장 짧은 보존은 D88 U4 의 처리 끝난 원본 Trace 30일이다. 계약 DeployBackupConfig 에는 보존 칸이 없다
RETENTION_WITHIN = "14d"
STAGE_DIR = "/stage"  # 스냅샷 안의 경로(컨테이너 안 마운트 위치). 정해져 있어야 restic 이 같은 대상의 스냅샷을 한 묶음(host, paths)으로 본다
SNAPSHOT_ID = re.compile(r"^[0-9a-f]{8,64}$")  # 계약 BackupSnapshotId
DB_NAME = re.compile(r"^[A-Za-z0-9_]+$")
USER_NAME = re.compile(r"^[A-Za-z0-9._-]+$")  # HTTP 기본 인증 사용자 = rest-server 의 저장소 폴더 이름
BACKUP_LABEL = "io.openit.backup"  # compose 서비스 라벨. 값 postgres 는 그 서비스가 영역 데이터베이스라는 뜻이다(주인은 io.openit.service 라벨)
POSTGRES = "postgres"


class BackupConfigError(Exception):
    """백업 설정이 틀렸다."""


@dataclass(frozen=True)
class Repository:
    """백업 저장소(restic REST 저장소) 주소의 부분."""

    host: str
    port: int
    path: str  # 사용자 이름과 같다(rest-server --private-repos)

    @property
    def url(self) -> str:
        return f"rest:https://{self.host}:{self.port}/{self.path}"


def parse_repository(url: str) -> Repository:
    """`rest:https://<이름>[:<포트>]/<저장소>`. 이름은 DNS 이름이어야 한다(사설 CA 의 ACME 가 IP 식별자를 발급하는지 확인하지 못했다, ADR 0026)."""
    if not url.startswith("rest:https://"):
        raise BackupConfigError("repository_url 은 rest:https:// 로 시작한다(계약 BackupRepositoryUrl)")
    parts = urlsplit(url.removeprefix("rest:"))
    host = parts.hostname or ""
    if parts.username or parts.password:
        raise BackupConfigError("repository_url 에 자격을 넣지 않는다(http_credentials_file 에 둔다)")
    if parts.query or parts.fragment:
        raise BackupConfigError("repository_url 에 질의·조각이 있다")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise BackupConfigError("repository_url 의 호스트는 IP 주소가 아니라 이름이어야 한다(저장소가 사설 CA 에서 인증서를 받을 이름)")
    if not host:
        raise BackupConfigError("repository_url 에 호스트가 없다")
    path = parts.path.strip("/")
    if not USER_NAME.fullmatch(path):
        raise BackupConfigError("repository_url 의 경로는 저장소 이름 하나다(글자 A-Z a-z 0-9 . _ -)")
    return Repository(host, parts.port or 443, path)


def parse_user_password(text: str) -> tuple[str, str]:
    """한 줄 '사용자:비밀번호'(HTTP 기본 인증의 user-pass, RFC 7617 2)."""
    lines = text.strip().splitlines()
    if len(lines) != 1 or ":" not in lines[0]:
        raise BackupConfigError("자격 파일은 한 줄 '사용자:비밀번호' 다")
    user, _, password = lines[0].partition(":")
    if not user or not password:
        raise BackupConfigError("자격 파일의 사용자와 비밀번호는 비어 있지 않다")
    return user, password


def parse_credentials(text: str, repository: Repository) -> tuple[str, str]:
    """백업 저장소 자격. 사용자는 저장소 이름과 같아야 한다(rest-server --private-repos 는 사용자 폴더만 열어 준다)."""
    user, password = parse_user_password(text)
    if not USER_NAME.fullmatch(user):
        raise BackupConfigError("http_credentials_file 의 사용자 글자는 A-Z a-z 0-9 . _ - 다")
    if user != repository.path:
        raise BackupConfigError(f"http_credentials_file 의 사용자는 repository_url 의 저장소 이름({repository.path})과 같아야 한다(rest-server --private-repos)")
    return user, password


def with_credentials(url: str, user: str, password: str) -> str:
    """restic 이 저장소 주소 파일에서 읽는 자격 포함 주소. 명령줄·환경 변수에 두지 않으려고 파일로만 준다."""
    scheme, _, rest = url.partition("://")
    return f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{rest}"


def offsite_repository(offsite_url: str) -> str:
    """서버 밖 대상은 restic 의 REST 백엔드로 쓴다(`rest:` + 주소). https 만 받는다(영역 사이 모든 HTTP 는 TLS, C14)."""
    if not offsite_url.startswith("https://"):
        raise BackupConfigError("offsite_url 은 https:// 로 시작한다")
    parts = urlsplit(offsite_url)
    if parts.username or parts.password:
        raise BackupConfigError("offsite_url 에 자격을 넣지 않는다(offsite_credentials_file 에 둔다)")
    return f"rest:{offsite_url}"


def htpasswd_line(user: str, password: str, existing: str | None) -> str:
    """rest-server 의 .htpasswd 줄(bcrypt). 이미 있는 줄이 이 자격과 맞으면 그대로 돌려준다(bcrypt 는 소금이 달라 매번 다르다. 파일이 바뀌면 저장소가 다시 만들어진다)."""
    import bcrypt  # noqa: PLC0415

    for line in (existing or "").splitlines():
        name, _, digest = line.partition(":")
        if name == user and bcrypt.checkpw(password.encode(), digest.encode()):
            return line + "\n"
    return f"{user}:{bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()}\n"


def allowed_name(host: str, allowed_dns: Iterable[str]) -> bool:
    """사설 CA 의 발급 허용 이름(step-ca x509 정책 allow)에 이 이름이 드는가. `*.예` 는 한 단계 아래 이름만이다."""
    for pattern in allowed_dns:
        if pattern == host:
            return True
        if pattern.startswith("*.") and "." in host and host.partition(".")[2] == pattern[2:]:
            return True
    return False


def dependents(model: Mapping[str, Any], service: str) -> list[str]:
    """service 에 (간접으로라도) depends_on 하는 compose 서비스들. 복구 동안 멈출 것들이다."""
    services = model.get("services", {})
    found: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, spec in services.items():
            needs = set(spec.get("depends_on") or {})
            if name not in found and name != service and (service in needs or needs & found):
                found.add(name)
                changed = True
    return sorted(found)


def toc_table_count(toc: str) -> int:
    """`pg_restore --list` 의 목차에서 테이블 항목 수(TABLE DATA 는 세지 않는다)."""
    return sum(1 for line in toc.splitlines() if re.match(r"^\d+; \d+ \d+ TABLE (?!DATA)", line))


@dataclass(frozen=True)
class Target:
    owner: str  # 계약 ServiceName(데이터의 주인 영역)
    service: str  # compose 서비스(DB 컨테이너)
    user: str  # 슈퍼유저(컨테이너의 POSTGRES_USER, 기본 postgres)
    server: str  # 배치 설정의 서버 이름
    databases: tuple[tuple[str, int], ...]  # (데이터베이스 이름, 백업 때 목차의 테이블 수)


def targets_in(model: Mapping[str, Any], owners_of: Mapping[str, str]) -> list[tuple[str, str, str]]:
    """compose 모델에서 영역 DB(라벨 io.openit.backup=postgres)인 서비스들: (소유 영역, 서비스, 슈퍼유저). 서비스 이름순.

    왜 라벨: DB 를 새 영역이 더해도 deploy 코드를 고치지 않는다(D126: DB 는 그 데이터 주인 영역의 것). 사용자는 컨테이너의 POSTGRES_USER 다.
    """
    found: list[tuple[str, str, str]] = []
    for name, spec in sorted(model.get("services", {}).items()):
        labels = spec.get("labels") or {}
        if labels.get(BACKUP_LABEL) != POSTGRES:
            continue
        owner = labels.get("io.openit.service", "")
        found.append((owner, name, (spec.get("environment") or {}).get("POSTGRES_USER", "postgres")))
    return found


def manifest_json(created_at: str, project: str, postgres_major: str, targets: Iterable[Target]) -> str:
    """스냅샷 안의 /stage/manifest.json. 비밀은 없다."""
    document = {
        "format": 1,
        "created_at": created_at,
        "project": project,
        "postgres_major": postgres_major,
        "targets": [
            {"owner": t.owner, "service": t.service, "user": t.user, "server": t.server,
             "databases": [{"name": name, "tables": tables} for name, tables in t.databases]}
            for t in targets
        ],
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def parse_manifest(text: str) -> list[Target]:
    try:
        document = json.loads(text)
        if document["format"] != 1:
            raise BackupConfigError(f"알 수 없는 백업 형식이다: {document['format']}")
        targets = [
            Target(item["owner"], item["service"], item["user"], item["server"],
                   tuple((db["name"], int(db["tables"])) for db in item["databases"]))
            for item in document["targets"]
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise BackupConfigError(f"백업의 manifest.json 을 읽지 못했다: {error}") from error
    for target in targets:
        for name, _ in target.databases:
            if not DB_NAME.fullmatch(name):
                raise BackupConfigError(f"데이터베이스 이름이 [A-Za-z0-9_] 가 아니다: {name!r}")
    return targets


def job_result_line(job: str, exit_code: int, started_at: str, finished_at: str, processed_count: int | None = None, snapshot_id: str | None = None) -> str:
    """잡의 표준 출력 마지막 줄(계약 JobRunResult, JSON Lines)."""
    document: dict[str, Any] = {"job": job, "exit_code": exit_code, "started_at": started_at, "finished_at": finished_at}
    if processed_count is not None:
        document["processed_count"] = processed_count
    if snapshot_id is not None:
        if not SNAPSHOT_ID.fullmatch(snapshot_id):
            raise ValueError(f"스냅샷 ID 모양이 계약 BackupSnapshotId 와 다르다: {snapshot_id}")
        document["snapshot_id"] = snapshot_id
    return json.dumps(document, separators=(",", ":"))
