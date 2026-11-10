"""Keycloak realm 파일: 사람 역할과 기계 클라이언트는 계약의 이름이고, 토큰은 RFC 9068 프로파일을 따르게 설정된다."""

import json
from pathlib import Path
from typing import Any

import pytest

from openit_platform import identity, pki
from openit_platform.contract.models import MachineRole, MachineTokenTable, UserRole

from .helpers import platform_settings

TABLE = MachineTokenTable.model_validate(
    {
        "tokens": [
            {"client": "hospital", "roles": ["result-reader"], "client_secret_file": "/run/secrets/a"},
            {"client": "model-lab", "roles": ["case-reader"], "client_secret_file": "/run/secrets/b"},
        ]
    }
)


def _realm(repo: Path, table: MachineTokenTable = TABLE) -> dict[str, Any]:
    roles = identity.machine_role_services(repo / "contracts")
    return identity.render_realm(platform_settings(repo), ["survey-service", "model-runtime"], table, roles)


def test_role_names_are_the_contract_enums(repo: Path) -> None:
    realm = _realm(repo)
    names = {role["name"] for role in realm["roles"]["realm"]} - {"default-roles-openit"}
    assert names == {item.value for item in UserRole} | {item.value for item in MachineRole}


def test_tokens_only_carry_contract_roles_through_scope_mappings(repo: Path) -> None:
    """Keycloak 의 기본 역할(offline_access 등)은 가져오기로 비울 수 없다. 클라이언트마다 범위를 계약의 역할로 제한한다(fullScopeAllowed 거짓)."""
    realm = _realm(repo)
    assert all(client["fullScopeAllowed"] is False for client in realm["clients"])
    mappings = {item["client"]: item["roles"] for item in realm["scopeMappings"]}
    assert mappings["oauth2-proxy"] == [role.value for role in UserRole]
    assert mappings["machine-hospital"] == ["result-reader"] and mappings["machine-model-lab"] == ["case-reader"]


def test_secrets_are_placeholders_never_values(repo: Path) -> None:
    text = identity.render_realm_text(_realm(repo))
    assert "${OAUTH2_PROXY_CLIENT_SECRET}" in text and "${MACHINE_CLIENT_SECRET_HOSPITAL}" in text and "${OPENIT_REALM_ADMIN_PASSWORD}" in text
    realm = json.loads(text)
    admin = next(user for user in realm["users"] if user["username"] == "admin")
    assert admin["credentials"][0]["temporary"] is True and admin["realmRoles"] == ["admin"]  # 초기 admin 은 임시 비밀번호로 시작한다


def test_rfc9068_attributes_and_audiences(repo: Path) -> None:
    realm = _realm(repo)
    clients = {client["clientId"]: client for client in realm["clients"]}
    assert set(clients) == {"oauth2-proxy", "machine-hospital", "machine-model-lab"}
    for client in clients.values():
        assert client["attributes"]["access.token.header.type.rfc9068"] == "true"  # typ: at+jwt(RFC 9068 2.1)
        assert client["publicClient"] is False and client["directAccessGrantsEnabled"] is False
        assert any(m["name"] == "client_id" for m in client["protocolMappers"])  # RFC 9068 2.2 의 client_id 클레임
    audience = lambda client: sorted(m["config"]["included.custom.audience"] for m in client["protocolMappers"] if m["protocolMapper"] == "oidc-audience-mapper")  # noqa: E731
    assert audience(clients["oauth2-proxy"]) == ["model-runtime", "survey-service"]
    assert audience(clients["machine-hospital"]) == ["survey-service"]  # result-reader 를 요구하는 작업은 survey-service 에만 있다
    assert clients["machine-hospital"]["serviceAccountsEnabled"] is True and clients["machine-hospital"]["standardFlowEnabled"] is False
    assert clients["oauth2-proxy"]["redirectUris"] == ["https://openit.internal:8443/oauth2/callback"]


def test_service_account_gets_exactly_the_table_roles(repo: Path) -> None:
    realm = _realm(repo)
    accounts = {user["username"]: user["realmRoles"] for user in realm["users"] if "serviceAccountClientId" in user}
    assert accounts == {"service-account-machine-hospital": ["result-reader"], "service-account-machine-model-lab": ["case-reader"]}


def test_machine_role_services_from_contract(repo: Path) -> None:
    mapping = identity.machine_role_services(repo / "contracts")
    assert mapping == {"result-reader": ["survey-service"], "risk-detector": ["survey-service"], "inference-caller": ["model-runtime"], "case-reader": ["survey-service"]}


def test_caller_without_matching_operation_is_rejected(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity, "machine_role_services", lambda _contracts: {role.value: [] for role in MachineRole})
    with pytest.raises(pki.ConfigError, match="aud"):
        identity.render_realm(platform_settings(repo), [], TABLE, identity.machine_role_services(repo / "contracts"))


def test_same_input_same_output(repo: Path) -> None:
    assert identity.render_realm_text(_realm(repo)) == identity.render_realm_text(_realm(repo))


def test_machine_table_file_is_validated(tmp_path: Path) -> None:
    path = tmp_path / "machine-callers.json"
    assert identity.load_machine_table(path).tokens == []  # 파일이 없으면 호출자가 없다
    path.write_text('{"tokens":[{"client":"Bad_Name","roles":["result-reader"],"client_secret_file":"/x"}]}', encoding="utf-8")
    with pytest.raises(pki.ConfigError, match="계약을 어겼다"):
        identity.load_machine_table(path)


def test_oauth2_proxy_client_gives_realm_roles_as_the_groups_claim(repo: Path) -> None:
    """admin-console-001: oauth2-proxy 의 /oauth2/userinfo groups 는 ID 토큰의 groups 클레임이다. 표준 매퍼(User Realm Role)가 realm 역할을 낸다."""
    realm = _realm(repo)
    clients = {client["clientId"]: client for client in realm["clients"]}
    mapper = next(m for m in clients["oauth2-proxy"]["protocolMappers"] if m["name"] == "groups")
    assert mapper["protocolMapper"] == "oidc-usermodel-realm-role-mapper" and mapper["protocol"] == "openid-connect"
    config = mapper["config"]
    assert config["claim.name"] == "groups" and config["multivalued"] == "true" and config["jsonType.label"] == "String"
    assert {config[key] for key in ("access.token.claim", "id.token.claim", "userinfo.token.claim")} == {"true"}
    # 범위가 UserRole 로 제한되어 있어(fullScopeAllowed 거짓) groups 에도 UserRole 만 나온다. 기계 클라이언트에는 이 매퍼가 없다
    assert clients["oauth2-proxy"]["fullScopeAllowed"] is False
    assert all(m["name"] != "groups" for name, client in clients.items() if name != "oauth2-proxy" for m in client["protocolMappers"])
