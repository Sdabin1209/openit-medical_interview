# 0005. 설정은 pydantic-settings, 비밀은 파일

## 상태
승인(2026-11-10, 헤드 위임. ADR 0001의 Pydantic v2 선택을 구체화)

## 맥락
서비스는 설치처마다 다른 값(설정)과 비밀을 받는다. ADR 0004는 "설정은 환경 변수, 비밀은 `NAME_FILE`이 가리키는 파일에서만"이라고 정했다. 이 규칙을 코드로 어떻게 구현할지 정해야 한다.

## 결정
- 설정은 `pydantic-settings`(MIT)의 `BaseSettings`로 환경 변수에서 읽는다. 변수 이름은 `OPENIT_` 접두어를 쓴다. 칸마다 타입, 기본값, `description`을 둔다(`src/<패키지>/main.py`의 `Settings`).
- 비밀은 `read_secret(name)` 하나로만 읽는다. 환경 변수 `<NAME>_FILE`이 가리키는 파일의 내용을 읽고, 환경 변수 `<NAME>` 자체는 읽지 않는다. 파일이 없거나 비어 있으면 `SecretError`를 내는데, 메시지에는 비밀 이름만 넣고 값과 경로는 넣지 않는다.
- `/readyz`는 점검이 던진 예외의 내용을 응답에 싣지 않는다. 실패한 점검의 이름만 낸다(연결 문자열에 비밀이 들어 있을 수 있다).
- 시험 도구: Starlette `TestClient`가 요구하는 `httpx2`(BSD-3-Clause)를 개발 의존으로 둔다. Starlette가 `httpx` 지원을 폐기 예정으로 경고하기 때문이다. 제품 코드의 HTTP 클라이언트는 ADR 0001대로 `httpx`다.

## 왜
- 12-Factor 3(설정은 환경에): 설치처 차이를 코드 밖에 둔다. FastAPI 문서가 설정 관리로 권하는 도구가 pydantic-settings다. 타입 검증이 따라온다.
- 환경 변수의 비밀은 프로세스 목록, `docker inspect`, 자식 프로세스로 새 나간다. 파일은 권한으로 막고 Docker·Compose의 secrets가 표준으로 파일을 쓴다.

## 검토한 대안과 버리는 이유
- **`os.environ` 직접 읽기:** 타입 검증과 기본값 문서를 직접 써야 해서 빈틈이 생긴다.
- **python-dotenv, dynaconf:** `.env` 파일을 앱이 읽게 하면 비밀이 설정 파일에 섞인다. Compose가 이미 환경 변수를 주입한다.
- **pydantic-settings의 `secrets_dir`:** 파일 이름이 필드 이름과 같아야 해서 `NAME_FILE`로 경로를 주는 D84 규칙과 어긋난다.

## 결과
- **얻는 것:** 설정은 타입이 검증된 한 곳, 비밀은 파일 한 경로.
- **감수하는 것:** `pydantic-settings` 의존 하나. 버전은 `uv.lock`이 고정한다.

## 되돌리는 조건
pydantic-settings의 라이선스가 허용형이 아니게 되거나 유지가 끊기면 다른 표준 설정 라이브러리로 바꾼다. 비밀 전달 표준이 바뀌면(예: 외부 비밀 저장소) 이 ADR을 대체한다.
