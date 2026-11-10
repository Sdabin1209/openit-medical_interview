#!/bin/bash
# Keycloak 전용 DB 와 역할을 만든다. 비밀은 파일(compose secrets)에서만 읽고 출력하지 않는다.
# 왜 별도 역할: 공유 DB 는 없고 DB 는 데이터 주인의 컴포넌트다(워크스페이스 D126). Keycloak 데이터는 Keycloak 역할만 만진다.
set -euo pipefail
password="$(cat /run/secrets/keycloak_db_password)"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v kcpass="$password" <<'SQL'
CREATE ROLE keycloak LOGIN PASSWORD :'kcpass';
CREATE DATABASE keycloak OWNER keycloak;
SQL
