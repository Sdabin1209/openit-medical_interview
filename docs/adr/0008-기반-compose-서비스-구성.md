# 0008. 기반 compose 서비스 구성

## 상태
승인(2026-11-10, 헤드 위임. ADR 0004의 `deploy/compose.yaml`을 구체화)

## 맥락
영역과 무관한 기반 서비스(PostgreSQL, Envoy, Keycloak, oauth2-proxy, step-ca)를 먼저 둔다. 영역 서비스와 영역 라우트는 계약이 정해진 뒤 더한다.

## 결정
- 이미지: postgres 16.10, envoy v1.35.3, keycloak 26.3.5, oauth2-proxy v7.12.0, step-ca 0.28.4를 digest로 고정한다(2026-11-10에 `docker buildx imagetools inspect`로 읽은 값). 설치 시점의 최신 안정 태그를 골랐고 호환 시험은 이 구성의 기동·health 확인까지만 했다.
- 비밀은 compose secrets(파일)이다. 파일 이름은 `deploy/secrets/`에 있고 `./deploy secrets init`이 만든다. 파일 권한은 0644, 폴더는 0700이다. 이유: compose 파일 비밀은 bind mount라 호스트 권한이 컨테이너에 그대로 보여서, 컨테이너의 비root 사용자(postgres 999, keycloak 1000)가 0600 파일을 읽지 못했다(시험에서 확인). 호스트 쪽 접근은 폴더 권한이 막는다.
- 지원하는 곳은 `*_FILE`로 파일을 가리킨다(postgres `POSTGRES_PASSWORD_FILE`, step-ca `DOCKER_STEPCA_INIT_PASSWORD_FILE`, oauth2-proxy `--client-secret-file`·`--cookie-secret-file`). Keycloak은 설정 값에 `_FILE`을 지원하지 않아(`kc.sh start --help-all`로 확인), 컨테이너 진입 명령이 파일을 읽어 그 프로세스 안에서만 환경 변수로 만든다. compose 환경 변수와 이미지에는 값이 없다.
- 고정 호스트 포트는 없다. 게이트웨이(Envoy)만 `${OPENIT_BIND_ADDRESS}::8080`으로 Docker가 호스트 포트를 배정한다. 나머지는 `backend` 내부 네트워크에만 있다(`internal: true`: 밖으로 나가는 길이 없다).
- PostgreSQL에는 Keycloak 전용 역할·데이터베이스를 초기화 스크립트로 만든다. 공유 DB는 없다(영역 DB는 영역이 따로 가진다).
- Envoy 기반 설정은 `/healthz`만 직접 200으로 답하고 나머지는 503이다. 관리 인터페이스(admin)는 컨테이너 안 루프백에만 연다.
- HEALTHCHECK: 이미지에 curl이 없어 envoy·keycloak은 bash `/dev/tcp`로 확인한다(compose의 `CMD-SHELL`은 `/bin/sh`라 `/dev/tcp`가 안 되어 `CMD ["bash","-c",...]`를 쓴다). oauth2-proxy는 셸이 없는 distroless라 컨테이너 안 점검 수단이 없어 healthcheck를 두지 않는다(기동 로그와 `running` 상태만 확인).
- 백업은 `pg_dumpall` 한 파일이 아니라 `globals.sql`(역할)과 데이터베이스마다 `pg_dump` 파일이다. `pg_dumpall --clean`은 사용 중인 데이터베이스와 현재 사용자를 지우려다 복원이 실패했다(시험에서 확인). 복원은 서비스를 멈추고 `DROP DATABASE ... WITH (FORCE)` 후 다시 만든다.
- `doctor`가 `docker compose config`로 구성을 검증하고, 고정 호스트 포트가 없는지와 이미지가 digest로 고정되었는지 본다.

## 왜
- 이미지·비밀·포트 규칙은 ADR 0004와 워크스페이스 규칙(D84, D128)이다. 각 항목의 값 근거는 위 문장에 붙였다.

## 검토한 대안과 버리는 이유
- **비밀을 환경 변수로 Keycloak에 전달:** D84 위반이다.
- **0600 파일과 uid 맞추기:** compose(비 Swarm)는 secrets의 uid·mode를 지원하지 않는다.
- **oauth2-proxy 앞에 셸 달린 이미지로 healthcheck:** 공식 이미지를 벗어난다.

## 결과
- **얻는 것:** 다섯 서비스가 `./deploy up`으로 뜨고 `./deploy status`가 health를 보인다(이 환경에서 확인).
- **감수하는 것:** Keycloak realm(`openit`)은 oauth2-proxy 클라이언트 하나만 가진 최소 구성이다. 사람 인증 정책, Envoy 라우트와 oauth2-proxy 연동, step-ca 인증서 발급 흐름은 영역 계약이 정해진 뒤 정한다(남은 것). 기동 시험은 이 환경 한 곳에서만 했다.

## 후속
사설 CA 발급 흐름, 레지스트리, 감시는 ADR 0013~0015가 정한다. step-ca 구성(`step-ca-data` 볼륨, 초기화 환경 변수)은 그 ADR로 바뀌었다.

## 되돌리는 조건
Compose가 secrets의 `uid/gid/mode`를 지원하면 0644를 0400으로 좁힌다. Keycloak이 `_FILE`을 지원하면 진입 명령 우회를 없앤다.
