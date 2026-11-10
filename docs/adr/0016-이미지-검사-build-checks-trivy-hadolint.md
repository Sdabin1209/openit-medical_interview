# 0016. 이미지 검사: Build Checks, Trivy, hadolint

## 상태
승인(2026-11-10, 사용자 결정. ADR 0004의 이미지 검사 항목을 보완한다. 0004의 "hadolint는 GPL-3.0이라 쓰지 않는다"는 ADR 0017로 대체되었다)

## 맥락
ADR 0004는 Dockerfile 검사를 `docker buildx build --check`(Docker Build Checks)로 정했다. 이것은 Dockerfile 작성 규칙을 본다. 이미지 안의 알려진 취약점, 보안 설정(루트 사용자 등), RUN 줄의 셸 명령 오류는 보지 못한다.

## 결정
- **세 도구가 서로 다른 것을 본다:**

  | 도구 | 보는 것 | 언제 |
  |---|---|---|
  | Docker Build Checks(`docker buildx bake --check`) | Dockerfile 작성 규칙(ARG 기본값, 단계 이름 등) | `openit-check dockerfile-lint`, `./deploy build --check` |
  | hadolint(ShellCheck 포함) | Dockerfile 모범 사례 규칙(DLxxxx)과 `RUN` 줄의 셸 명령(SCxxxx) | `openit-check dockerfile-lint` |
  | Trivy | Dockerfile·compose의 보안 설정(`trivy config`), 이미지의 알려진 취약점과 비밀 값(`trivy image`) | `./deploy build`(빌드 전 config, 빌드 뒤 image) |

- **`./deploy build`에 Trivy를 붙인다:** 빌드 전에 대상의 Dockerfile 폴더와 `deploy/compose.yaml`을 `trivy config`로, 빌드 뒤에 이미지를 `trivy image`로 검사한다. 실패하면 rc=1이고 `images.lock`에 그 이미지의 digest를 쓰지 않는다. 우회 플래그는 없다.
- **Trivy 실행:** 공식 컨테이너 이미지(`aquasec/trivy`)를 digest로 고정해 compose의 `trivy` 서비스(`tools` 프로파일, 일회용 `compose run`)로 돌린다. 이미지 빌드에는 어차피 도커가 필요하다. 이미지는 `docker save` 파일로 넘기며 도커 소켓을 Trivy에 주지 않는다. 취약점 DB 캐시는 리포의 git 제외 폴더 `.trivy-cache/`다.
- **실패 기준:** 심각도 CRITICAL·HIGH에서 실패하고, `trivy image`는 수정판이 없는 취약점을 무시한다(`--ignore-unfixed`). 이것은 Trivy 공식 문서가 CI 실패 기준으로 보이는 일반 예시다. 값을 측정으로 정하지 않았다.
- **예외:** 리포 루트의 `.trivyignore`(Trivy 표준 형식 `<ID> exp:<만료일>`)에만 둔다. 항목마다 바로 위에 `# 사유: ...` 주석과 만료일이 있어야 하고, `openit-check trivyignore`가 사유 주석, 형식, 만료 여부를 점검한다. 만료되면 다시 실패한다. 지금 항목은 없다.
- **hadolint:** `tools/checks`의 개발 의존(`hadolint-bin`, PyPI, 공식 hadolint 바이너리)으로 설치하고 `openit-check dockerfile-lint`가 모든 Dockerfile(`templates/`, `services/`, `web/`, `deploy/`)에 돌린다. 규칙 설정은 리포 루트 `.hadolint.yaml`(공식 형식)이고 무시 규칙은 항목마다 사유를 적는다. hadolint는 개발·점검에서 실행만 하며 이미지에 들어가지 않는다(라이선스는 ADR 0017). 현재 무시 규칙은 `DL3017`(`apk upgrade` 금지) 하나다.
- **이 구성이 처음 잡은 문제와 처리:** 화면 이미지의 기반(`nginxinc/nginx-unprivileged:stable-alpine`, digest 고정)에 수정판이 있는 CRITICAL·HIGH 취약점이 있었다(musl, zlib, expat 등). 최신 `stable-alpine` 태그도 같은 digest여서 기반을 올릴 수 없었다. 템플릿 Dockerfile에 `RUN apk upgrade --no-cache`를 넣어 고쳤고(`USER 0:0`로 잠깐 root), 그래서 `DL3017`을 사유와 함께 무시한다. 기반 이미지가 갱신되면 두 곳을 함께 지운다.

## 왜
- Build Checks는 Docker 표준이고 이미 쓰고 있어 유지한다. 작성 규칙은 이것이 본다.
- Trivy(Apache-2.0)는 이미지 취약점, Dockerfile 보안 설정, 비밀 값을 한 도구로 본다. 취약점 데이터베이스를 Trivy가 관리한다.
- hadolint는 Build Checks가 보지 않는 RUN 줄의 셸 명령(ShellCheck)과 모범 사례를 본다. Dockerfile이 템플릿에서 나오므로 작성 규칙의 이득은 작지만, 템플릿이 바뀔 때와 영역이 RUN 줄을 더할 때를 지키는 비용이 거의 없다.
- 실패 기준을 CRITICAL·HIGH로 한 이유는 공식 문서의 일반 예시를 따르기 위해서다. 수정판이 없는 항목은 사용자가 고칠 수 없으므로 빌드를 막지 않고, 수정판이 나오는 순간 막힌다.
- 예외에 만료일을 강제하는 이유는 무시 목록이 영구 면제가 되는 것을 막기 위해서다.

## 검토한 대안과 버리는 이유
- **hadolint만:** 취약점·보안 설정을 보지 못한다.
- **Trivy만:** Dockerfile 모범 사례와 셸 명령 검사가 얕다.
- **Grype, Docker Scout:** Trivy 하나로 이미지·설정·비밀을 함께 본다. Scout는 계정 연동이 필요하다.
- **Trivy를 호스트에 설치:** 서버마다 설치와 버전을 맞춰야 한다. digest로 고정한 컨테이너는 어디서나 같다.
- **`apk upgrade` 대신 `.trivyignore`로 취약점 무시:** 수정판이 있는 취약점을 무시하는 것은 예외의 목적에 맞지 않는다.

## 결과
- **얻는 것:** 빌드할 때마다 취약점·보안 설정이 검사되고, 통과하지 못하면 lock에 기록되지 않는다. 이 환경에서 `build _example`, `build web-example`이 Trivy 포함 rc=0이다.
- **감수하는 것:** 첫 검사에 취약점 DB 내려받기(인터넷)가 필요하고 빌드가 길어진다(측정하지 않음). `apk upgrade` 때문에 화면 이미지는 같은 입력에서 같은 이미지가 나오지 않는다. 새 취약점이 공개되면 이전에 통과한 빌드가 다시 실패할 수 있다(의도한 동작이다). `trivy config`가 compose 파일을 얼마나 검사하는지는 확인하지 못했다(통과만 확인). RUN 줄의 셸 명령은 템플릿에서 최소로 두고 템플릿 검토에서도 확인한다.

## 되돌리는 조건
검사 시간이 개발을 막으면 빌드 뒤 검사를 CI로 옮기는 새 ADR을 쓴다. 기반 이미지가 갱신되면 `apk upgrade`와 `DL3017` 무시를 지운다.
