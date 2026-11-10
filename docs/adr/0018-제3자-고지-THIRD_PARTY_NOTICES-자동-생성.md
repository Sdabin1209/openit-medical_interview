# 0018. 제3자 고지(THIRD_PARTY_NOTICES) 자동 생성과 이미지 점검

## 상태
승인(2026-11-10, 헤드 위임). ADR 0017의 "제품 의존은 허용형만 쓴다"를 이어, 허용형 라이선스가 요구하는 고지 의무를 자동으로 지키게 한다.

## 맥락
MIT·BSD·ISC·Apache-2.0 같은 허용형 라이선스는 사용을 막지 않지만 조건이 있다. 배포물에 저작권 표시와 라이선스 전문을 함께 주어야 하고(MIT·BSD·ISC), Apache-2.0은 의존이 `NOTICE` 파일을 가지면 그 내용도 주어야 한다(Apache-2.0 4절 (d)). 이미지는 의존을 담아 배포되므로 이 조건이 걸린다. 지금까지 이미지에는 고지가 없었고, 의존이 바뀔 때마다 사람이 맞출 방법도 없었다. 규칙에는 점검이 따라야 한다.

## 결정
- **생성:** `openit-notices generate [영역 폴더...]`(`tools/checks`, 모듈 `openit_checks.notices`)가 잠금 파일에서 영역의 `THIRD_PARTY_NOTICES`(텍스트)를 만든다. 내용은 패키지 이름·버전·라이선스 식별자·주소·저작권 표시·라이선스 전문·(있으면) NOTICE이고, 머리말에 패키지 목록이 있다.
- **어느 의존이 들어가나:** 이미지에 실제로 들어가는 제품 의존만이다. ADR 0017과 같은 기준이고 Dockerfile의 설치와 같은 설치다.
  - Python: `uv sync --frozen --no-dev --no-install-project`로 임시 환경에 설치한 패키지. 잠금 파일에서 출처가 `editable`·`virtual`·`directory`인 것(우리 코드)은 뺀다.
  - npm: `package-lock.json`에서 `dev`·`devOptional` 표시가 없는 패키지를 `npm ci --omit=dev --ignore-scripts`로 임시 폴더에 설치해 읽는다. 화면 이미지는 이 의존이 번들된 정적 파일이므로 번들된 것이 곧 이 목록이다(트리 셰이킹으로 빠진 것까지 적는 쪽으로 틀린다. 빠뜨리는 쪽보다 낫다).
- **어디서 읽나(표준 도구와 직접 읽기의 경계):**
  - 이름·버전·라이선스 식별자·저자·주소: Python은 `pip-licenses`(MIT, 이미 ADR 0007이 쓰는 도구)가 읽는 표준 메타데이터, npm은 `package-lock.json`과 패키지의 `package.json`.
  - 라이선스 전문과 NOTICE: 설치된 패키지 폴더의 파일을 직접 읽는다. Python은 `*.dist-info/licenses/` 아래 모든 파일(PEP 639가 `License-File`로 정한 위치)과 옛 방식의 `dist-info` 바로 아래 `LICENSE*`·`COPYING*`·`NOTICE*`, npm은 패키지 최상위의 `LICENSE*`·`LICENCE*`·`COPYING*`·`NOTICE*`·`UNLICENSE*`. 이름이 `NOTICE`로 시작하면 NOTICE 절에, 나머지는 라이선스 전문 절에 넣는다. 같은 내용의 파일은 한 번만 넣는다.
  - 저작권 표시: 라이선스 전문과 NOTICE에서 `Copyright (c)·©` 또는 연도가 있는 `Copyright` 줄을 뽑는다. 하나도 없으면 "없다"와 패키지 메타데이터의 저자를 그대로 적는다(지어내지 않는다).
  - 파일이 없는 패키지: 생성이 실패한다. 사람이 `tools/checks/notices-overrides.toml`에 대체 전문을 근거(reason)와 함께 적어야 통과한다. 대체는 라이선스 식별자가 같을 때만 적용되고, 패키지가 파일을 실으면 쓰지 않는다. 지금 항목은 `react-remove-scroll-bar`(npm 타르볼에 LICENSE 파일 없음, 직접 확인) 하나다.
- **결정성:** 패키지는 (이름 소문자, 버전)으로 정렬하고 시각·경로·환경 값을 넣지 않는다. 같은 잠금 파일이면 같은 파일이다(Python 예시 두 번 생성해 바이트 비교로 확인).
- **이미지 안의 자리:** `/usr/share/doc/openit/THIRD_PARTY_NOTICES`(서비스·화면 모두, FHS의 문서 폴더). 화면은 번들된 JavaScript가 브라우저로 배포되므로 `/usr/share/nginx/html/THIRD_PARTY_NOTICES.txt`에도 둔다(`/THIRD_PARTY_NOTICES.txt`로 받아 볼 수 있다). Dockerfile의 마지막 단계(이미지에 남는 단계)에서 영역 폴더의 파일을 `COPY`한다.
- **점검 두 단계:**
  1. `openit-check notices`(`openit-check all`에 들어간다): services/·web/의 모든 영역에 대해 ① 잠금 파일이 있고 ② `THIRD_PARTY_NOTICES`가 있고 ③ 그것이 잠금 파일에서 다시 만든 것과 글자까지 같고(어긋나면 잠금 파일에만 있는 패키지와 고지에만 있는 패키지 개수를 알린다) ④ Dockerfile 마지막 단계가 정해진 경로로 `COPY`하고 ⑤ `.dockerignore`가 그 파일을 빼지 않는지 본다. `templates/`의 Dockerfile도 ④를 본다.
  2. `deploy/deploy build`가 이미지를 만든 뒤, 1단계를 다시 확인하고 이미지에서 `docker create`·`docker cp`로(이미지를 실행하지 않는다) 고지를 꺼내 영역의 파일과 바이트까지 같은지 본다(`openit-notices image`). 파일이 없거나 다르면 빌드가 실패하고 `images.lock`에 digest를 쓰지 않는다. docker 호출은 `deploy/dockerenv.py`의 격리 설정을 쓴다. Trivy 검사 앞에서 돈다.
- **템플릿:** 템플릿 Dockerfile이 `COPY`를 갖고, `tools/new-area`가 잠금 파일을 만든 직후 고지를 생성하므로 새 영역은 처음부터 고지를 가진다. 의존을 바꾼 개발자는 `openit-notices generate <영역>`을 다시 돌린다(점검이 어긋남을 알려 준다).

## 왜
- **표준 도구 먼저:** 메타데이터(이름·버전·라이선스 식별자)는 pip-licenses와 잠금 파일이라는 표준 출처에서 읽는다. pip-licenses를 이미 쓰고 있어 새 의존이 없다.
- **전문을 직접 읽는 이유(측정):** `pip-licenses -l --with-notice-file`을 `services/_example`의 제품 의존 25개에 돌려 보았다. 패키지마다 라이선스 파일을 하나만 주었다. `greenlet`(MIT AND PSF-2.0)은 `LICENSE`와 `LICENSE.PSF`가 있는데 하나만 나왔다. 저작권 표시를 따로 주는 칸이 없다. 이 예시에는 NOTICE 파일을 가진 패키지가 없어 `--with-notice-file`의 동작은 확인하지 못했다. 둘 다 PEP 639가 정한 위치의 파일을 읽으면 해결되므로 그 부분만 직접 읽는다.
- **npm에서 license-checker 계열을 쓰지 않은 이유:** 이 도구도 `node_modules` 설치가 필요하므로 설치 단계가 같고, 하는 일은 패키지 최상위의 라이선스 파일 읽기와 같다. Python 점검 도구에 Node 도구 의존을 더하는 이득이 없다. 직접 돌려 비교해 보지는 않았다. 그래서 이 선택은 측정이 아니라 단순함에 근거한다.
- **임시 환경에 설치하는 이유:** 영역의 `.venv`·`node_modules`를 건드리지 않고, Dockerfile의 설치(`--no-dev`, `--omit=dev`)와 같은 설치를 읽기 위해서다. 잠금 파일만 읽어서는 파일의 내용을 알 수 없다.
- **`/usr/share/doc/openit/`:** FHS와 Debian 정책이 배포물의 라이선스·저작권 문서를 두는 자리다.
- **이미지 점검을 `deploy build`에 붙이는 이유:** 완료의 기준은 이미지 안의 파일이다. 영역 폴더의 파일이 맞아도 Dockerfile이나 `.dockerignore`가 빠뜨리면 이미지에는 없다.
- **도구 라이선스:** pip-licenses(MIT), uv(MIT 또는 Apache-2.0), npm CLI(Artistic-2.0), license-expression(Apache-2.0). 모두 `tools/checks`나 빌드·점검에서 실행만 하고 이미지에 들어가지 않는다(ADR 0017). 새로 더한 패키지 의존은 없다.

## 검토한 대안과 버리는 이유
- **고지를 생성하지 않고 라이선스 식별자 목록만 이미지 라벨에 넣기:** 전문과 저작권 표시가 없어 MIT·BSD의 조건을 채우지 못한다.
- **고지 파일을 리포에 두지 않고 빌드할 때마다 Dockerfile 안에서 생성:** 이미지 빌드에 점검 도구와 네트워크를 끌어들이고, 같은 입력에서 같은 파일이라는 점검(리포의 파일과 비교)을 못 한다.
- **FOSSA·ScanCode 등 상용·대형 도구:** ADR 0007과 같은 이유로 규모에 비해 크고 일부는 SaaS다.
- **라이선스 파일이 없을 때 식별자만 적고 통과:** 조건을 채우지 못한 채 조용히 통과한다. 실패시키고 사람이 근거와 함께 대체 전문을 적게 했다.

## 결과
- **얻는 것:** 이미지에 고지가 없거나 잠금 파일과 어긋나면 `openit-check all`과 `deploy build`가 실패한다. 의존을 바꾼 뒤 한 명령으로 고지를 다시 만든다.
- **감수하는 것:**
  - 의존을 바꿀 때마다 고지 파일의 diff가 크다(전문 포함). 의존 변경 커밋에 함께 들어간다.
  - 점검과 생성은 `uv sync`·`npm ci`를 하므로 네트워크나 캐시가 필요하다(ADR 0007의 라이선스 점검도 `uv sync`를 한다).
  - Python 설치는 점검을 도는 플랫폼의 설치다. 이미지는 linux라 linux에서 생성한다. 플랫폼에 따라 설치되는 패키지가 다른 의존이 생기면 다른 플랫폼의 결과가 달라질 수 있다. linux 한 환경에서만 확인했다.
  - npm의 플랫폼 전용 선택 의존이 제품 의존으로 들어오면 설치된 폴더가 없어 실패한다(현재는 없다). 그때 잠금 파일의 `os`·`cpu` 처리를 이 ADR에서 정한다.
  - 이 고지는 의존 패키지만 다룬다. 기반 이미지의 운영체제 패키지와 파이썬·nginx 자체의 고지는 기반 이미지가 자기 문서 폴더에 싣고 있는 것에 맡긴다(이 점검은 보지 않는다. ADR 0017에도 같은 한계가 있다). 이 부분은 확인하지 않았다.
  - 저작권 표시는 라이선스 파일의 줄을 뽑는 것이다. 파일에 표시가 없는 패키지는 저자를 적을 뿐이다.
  - 대체 전문(`react-remove-scroll-bar`)은 표준 MIT 전문에 package.json의 author를 저작권자로 넣은 것이고 연도는 쓰지 않았다. 헤드가 확인할 항목이다.

## 되돌리는 조건
- 고지를 이미지 밖(예: 별도 배포 문서)에서 전달하는 방식으로 정하면 이 ADR을 대체한다.
- 의존의 고지 전문을 전부 담는 크기가 문제가 되면(이미지 크기·화면 서빙) 전문 대신 식별자와 링크를 쓰는 방안을 라이선스별로 따져 대체한다. 지금은 측정하지 않았다.
- 표준 도구가 저작권 표시·전문·NOTICE를 모두 주게 되면 직접 읽는 부분을 그 도구로 바꾼다.
