"""사람 인증(Keycloak realm)과 화면 로그인(oauth2-proxy) 설정 생성(design.md 2절 identity·identity_proxy, platform ADR 0004).

realm 은 파일로 가져온다(--import-realm). 비밀(클라이언트 비밀, 초기 admin 임시 비밀번호)은 `${이름}` 자리표시자이고 값은 비밀 파일에서 Keycloak 시작 명령이
그 프로세스 안에서만 환경 변수로 만든다(ADR 0008). 접근 토큰은 RFC 9068 프로파일이다(계약 README 의 표): typ at+jwt, iss·sub·aud·exp·iat·jti·client_id, 역할 realm_access.roles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contract.models import ExposureAudience, MachineRole, MachineTokenTable, UserRole
from .gateway import HEALTH_PATHS, load_operations
from .pki import ConfigError
from .settings import REALM, PlatformSettings

# 왜 300: Keycloak 의 기본값(5분)이다. RFC 9068 은 수명을 정하지 않고 RFC 6819 가 접근 토큰을 짧게 두라고 권한다. 측정하지 않았다(platform ADR 0004)
ACCESS_TOKEN_SECONDS = 300
OAUTH2_PROXY_CLIENT = "oauth2-proxy"
ADMIN_USER = "admin"  # 계약 UserRole.admin 설명: 초기 admin 계정은 임시 비밀번호로 시작한다
MACHINE_SECRET_DIR = "/run/machine-clients"  # noqa: S105  컨테이너 안 폴더. 파일 이름이 기계 클라이언트 이름이다(값이 아니다)


def machine_env_name(client: str) -> str:
    """기계 클라이언트 비밀의 자리표시자 이름(환경 변수 이름)."""
    return "MACHINE_CLIENT_SECRET_" + client.upper().replace("-", "_")


def machine_role_services(contracts: Path) -> dict[str, list[str]]:
    """기계 역할 -> 그 역할을 요구하는 작업이 있는 서비스들(계약 OpenAPI). 기계 토큰의 aud 가 된다(RFC 9068 2.2, 4)."""
    found: dict[str, set[str]] = {role.value: set() for role in MachineRole}
    for path in sorted((contracts / "openapi").glob("*.yaml")):
        for operation in load_operations(contracts, path.stem):
            if operation.path in HEALTH_PATHS:
                continue
            for alternative in operation.security:
                for role in alternative.get("machine_token", ()):
                    found.setdefault(role, set()).add(operation.service)
    return {role: sorted(services) for role, services in found.items()}


def load_machine_table(path: Path) -> MachineTokenTable:
    """기계 호출자 표. 파일이 없으면 호출자가 없다(기계 클라이언트를 만들지 않는다)."""
    if not path.is_file():
        return MachineTokenTable(tokens=[])
    try:
        return MachineTokenTable.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ConfigError(f"{path.name}: 기계 호출자 표(MachineTokenTable)가 계약을 어겼다: {error}") from error


def human_audiences(exposed: dict[str, list[ExposureAudience]]) -> list[str]:
    """사람 접근 토큰의 aud: 사람 인증(HUMAN_OIDC)을 요구하는 경로가 있는 서비스."""
    return sorted(service for service, audiences in exposed.items() if ExposureAudience.HUMAN_OIDC in audiences)


def _audience_mapper(service: str) -> dict[str, Any]:
    return {
        "name": f"audience-{service}",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "consentRequired": False,
        "config": {"included.custom.audience": service, "access.token.claim": "true", "id.token.claim": "false", "introspection.token.claim": "true"},
    }


def _client_id_mapper(client_id: str) -> dict[str, Any]:
    # 왜 고정 값: RFC 9068 2.2 의 client_id 는 토큰을 받은 클라이언트다. 클라이언트마다 매퍼가 따로 있어 값이 곧 그 클라이언트의 이름이다
    # (세션 노트 매퍼는 서비스 계정에만 값이 있어 사람 토큰에는 client_id 가 빠졌다: 시험에서 확인)
    return {
        "name": "client_id",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-hardcoded-claim-mapper",
        "consentRequired": False,
        "config": {"claim.name": "client_id", "claim.value": client_id, "jsonType.label": "String", "access.token.claim": "true", "id.token.claim": "false"},
    }


def _client_base(client_id: str, secret_ref: str) -> dict[str, Any]:
    return {
        "clientId": client_id,
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "secret": f"${{{secret_ref}}}",
        "clientAuthenticatorType": "client-secret",
        "directAccessGrantsEnabled": False,
        "implicitFlowEnabled": False,
        # 왜 fullScopeAllowed 거짓: 토큰의 realm_access.roles 에 이 클라이언트에 허용한 역할(scopeMappings)만 싣는다. Keycloak 의 기본 역할(offline_access,
        # uma_authorization, default-roles-openit)은 새 계정마다 붙고 가져오기로 비울 수 없다(시험에서 확인). 계약 UserIdentityClaims 의 roles 는 UserRole 열거만 허용한다
        "fullScopeAllowed": False,
        "attributes": {
            # 왜 이 속성: Keycloak 의 RFC 9068 지원. 접근 토큰 JOSE 헤더의 typ 을 at+jwt 로 한다(RFC 9068 2.1)
            "access.token.header.type.rfc9068": "true",
            "access.token.lifespan": str(ACCESS_TOKEN_SECONDS),
        },
    }


def render_realm(settings: PlatformSettings, human_services: list[str], machine: MachineTokenTable, role_services: dict[str, list[str]]) -> dict[str, Any]:
    """realm 파일. 같은 입력은 같은 출력이다."""
    user_roles = [role.value for role in UserRole]
    machine_roles = [role.value for role in MachineRole]
    proxy = _client_base(OAUTH2_PROXY_CLIENT, "OAUTH2_PROXY_CLIENT_SECRET")
    proxy.update(
        {
            "standardFlowEnabled": True,
            "redirectUris": [f"{settings.public_base_url}/oauth2/callback"],
            "webOrigins": [],
            "protocolMappers": [_client_id_mapper(OAUTH2_PROXY_CLIENT), *(_audience_mapper(service) for service in human_services)],
        }
    )
    clients: list[dict[str, Any]] = [proxy]
    scope_mappings = [{"client": OAUTH2_PROXY_CLIENT, "roles": user_roles}]
    users: list[dict[str, Any]] = [
        {
            "username": ADMIN_USER,
            "enabled": True,
            "realmRoles": [UserRole.admin.value],
            # 왜 temporary: 초기 admin 은 임시 비밀번호로 시작하고 처음 로그인에서 바꾼다(계약 UserRole.admin 설명)
            "credentials": [{"type": "password", "value": "${OPENIT_REALM_ADMIN_PASSWORD}", "temporary": True}],
            "requiredActions": ["UPDATE_PASSWORD"],
        }
    ]
    for entry in machine.tokens:
        client = entry.client.root
        base = _client_base(f"machine-{client}", machine_env_name(client))
        roles = [role.value for role in entry.roles]
        audiences = sorted({service for role in roles for service in role_services.get(role, [])})
        if not audiences:
            raise ConfigError(f"기계 호출자 {client}: 역할 {roles} 를 요구하는 작업이 계약에 없어 토큰의 aud 를 정할 수 없다")
        base.update(
            {
                "serviceAccountsEnabled": True,
                "standardFlowEnabled": False,
                "redirectUris": [],
                "webOrigins": [],
                "protocolMappers": [_client_id_mapper(base["clientId"]), *(_audience_mapper(service) for service in audiences)],
            }
        )
        clients.append(base)
        scope_mappings.append({"client": base["clientId"], "roles": roles})
        users.append({"username": f"service-account-{base['clientId']}", "enabled": True, "serviceAccountClientId": base["clientId"], "realmRoles": roles})
    return {
        "realm": REALM,
        "enabled": True,
        "sslRequired": "external",
        "registrationAllowed": False,
        "accessTokenLifespan": ACCESS_TOKEN_SECONDS,
        "bruteForceProtected": True,
        # 왜 기본 역할을 비움: 기본 역할(offline_access, uma_authorization)이 접근 토큰의 roles 에 들어가면 계약 UserRole 열거를 어긴다
        "defaultRole": {"name": f"default-roles-{REALM}", "description": "비어 있다: 사람과 기계 호출자는 계약의 역할만 갖는다", "composite": True, "composites": {"realm": []}},
        "roles": {
            "realm": [
                # 왜 명시: 기본 역할 default-roles-openit 의 구성 역할(offline_access, uma_authorization)을 비운다. 사람 계정은 만들어질 때 기본 역할을 받는다
                {"name": f"default-roles-{REALM}", "description": "비어 있다: 계약의 역할만 쓴다", "composite": True, "composites": {"realm": []}},
                *({"name": name, "description": "계약 UserRole" if name in user_roles else "계약 MachineRole"} for name in [*user_roles, *machine_roles]),
            ]
        },
        "scopeMappings": scope_mappings,
        "clients": clients,
        "users": users,
    }


def render_realm_text(realm: dict[str, Any]) -> str:
    return json.dumps(realm, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
