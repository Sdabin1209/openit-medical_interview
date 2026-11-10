# 0009. docker 설정 격리의 구현과 점검

## 상태
승인(2026-11-10, 헤드 위임. ADR 0004의 'Docker 설정 격리'를 구현)

## 맥락
사용자 전역 `~/.docker`(설정, 자격 도우미)에 기대면 사람마다·서버마다 결과가 달라진다. ADR 0004는 호출자가 준 `DOCKER_CONFIG` 또는 리포의 git 제외 폴더를 쓰고, 엔진 선택은 Docker CLI 공식 우선순위를 따르라고 했다.

## 결정
- 구현은 `deploy/dockerenv.py`(표준 라이브러리만) 하나다. 모든 docker 호출(`deploy/deploy`, `tools/smoke`, 영역의 스모크 시험)이 이 모듈이 만든 환경을 쓴다.
- 설정 폴더: `DOCKER_CONFIG`가 있으면 그대로, 없으면 `<리포>/.docker-config/`에 빈 설정(`{}`)을 만든다(git 제외).
- 엔진 선택 우선순위(Docker CLI 공식: `DOCKER_CONTEXT`가 `DOCKER_HOST`보다 우선):
  1. `DOCKER_CONTEXT`가 있으면 `DOCKER_HOST`와 무관하게 그 context를 해석하고, 실패하면 멈춘다.
  2. 성공하면 엔드포인트로 `DOCKER_HOST`를 덮어쓰고 `DOCKER_CONTEXT`를 지운다.
  3. `DOCKER_CONTEXT`가 없고 `DOCKER_HOST`가 있으면 그대로 둔다.
  4. 둘 다 없으면 현재 context를 해석하고 실패하면 멈춘다. 해석 실패를 삼켜 기본 엔진으로 넘어가지 않는다.
- 점검(`openit-check docker-isolation`): `argv`가 `"docker"`로 시작하는 `subprocess` 호출에 `env=`가 없으면 위반이다. 사용자 `~/.docker`를 가리키는 문자열이 있으면 위반이다. 셸 스크립트의 docker 호출은 위반이다(호출은 `deploy/deploy`를 지난다). 동작은 `tools/checks/tests/test_dockerenv.py`가 fake docker로 네 규칙을 모두 시험한다.

## 왜
- 워크스페이스 규칙(2026-11-05, 2026-11-09)과 Docker CLI 문서의 우선순위를 따른다. 해석을 삼키지 않는 이유는 틀린 엔진에 빌드·배포하는 사고를 막기 위해서다.
- 호출 모양(`env=`)을 AST로 점검하는 이유는 규칙을 사람 기억에 두지 않기 위해서다.

## 검토한 대안과 버리는 이유
- **`DOCKER_CONFIG`만 지정하고 엔진은 CLI에 맡기기:** 사용자 환경의 `DOCKER_HOST`와 `DOCKER_CONTEXT`가 섞이면 어느 쪽이 이겼는지 호출자가 알 수 없다.
- **셸 래퍼 스크립트:** 우선순위 시험을 쓰기 어렵다.

## 결과
- **얻는 것:** 사용자 설정과 무관한 docker 호출, 규칙 위반을 점검이 잡는다.
- **감수하는 것:** 격리된 빈 설정에는 사용자의 레지스트리 로그인이 없다. 비공개 레지스트리가 필요하면 `DOCKER_CONFIG`로 그 설정을 명시해 준다. 이 환경(Docker Desktop WSL, 기본 context)에서만 실제로 확인했다.

## 되돌리는 조건
Docker CLI의 우선순위가 바뀌면 이 ADR을 대체한다.
