# openit v7

문진 키오스크 시스템. 리포 하나(모노레포)에 모든 영역이 폴더로 들어 있다.

```
openit-v7/
├── contracts/   영역 사이 계약(OpenAPI 3.1, JSON Schema 2020-12)과 린트 규칙. 헤드 소유
├── libs/        여러 영역이 쓰는 라이브러리(link, model-runtime)
├── services/    서비스 영역. 폴더 하나 = 서비스 하나 = Docker 이미지 하나
├── web/         화면(키오스크, 관리 화면)
├── jobs/        서버가 아닌 잡 영역(합성 데이터, 모델 개발)
├── deploy/      배포 구성과 배포 명령(compose, images.lock, ./deploy)
└── docs/adr/    전체에 걸친 결정 기록(ADR)
```

- 영역끼리는 코드를 가져다 쓰지 않고 `contracts/`의 계약으로만 만난다(점검: import-linter).
- 배포: `git clone` 뒤 `deploy/`의 명령 하나로 띄운다(ADR 0002).

## 도구

| 하는 일 | 명령 |
|---|---|
| 새 영역 만들기(템플릿에서) | `tools/new-area {service\|web} <이름>` |
| 이미지 빌드 | `deploy/deploy build [대상]` |
| 이미지 스모크 | `tools/smoke {service\|web} <영역>` |
| 화면 브라우저 시험(컨테이너) | `tools/web-e2e <영역>` |
| 제3자 고지 생성(의존을 바꾼 뒤) | `uv run --project tools/checks openit-notices generate <영역 폴더>` |
| 공통 점검 | `cd tools/checks && uv run openit-check all` |
| 점검 자체 시험 | `cd tools/checks && uv run pytest` |
| 배포 환경 확인 | `deploy/deploy doctor` |
| 처음 설치(신뢰의 뿌리, 레지스트리, 이미지, 기동) | `deploy/deploy bootstrap` |
| 사설 CA 상태·교체 | `deploy/deploy ca status`, `deploy/deploy ca rotate` ([절차](deploy/docs/CA.md)) |

템플릿은 `templates/service`, `templates/web`이고 `services/_example`, `web/_example`은 템플릿 시험용으로 남겨 둔다(실제 영역이 아니다).

## ADR 목록

- [0001 표준 기술 묶음과 허용형 라이선스](docs/adr/0001-표준-기술-묶음과-허용형-라이선스.md)
- [0002 모노레포와 배포 방식](docs/adr/0002-모노레포와-배포-방식.md)
- [0003 영역 폴더의 표준 구조](docs/adr/0003-영역-폴더의-표준-구조.md)
- [0004 도커와 배포 도구](docs/adr/0004-도커와-배포-도구.md)
- [0005 설정은 pydantic settings 비밀은 파일](docs/adr/0005-설정은-pydantic-settings-비밀은-파일.md)
- [0006 서비스 이미지 기반과 빌드 규칙](docs/adr/0006-서비스-이미지-기반과-빌드-규칙.md)
- [0007 라이선스 점검 도구와 규칙](docs/adr/0007-라이선스-점검-도구와-규칙.md)
- [0008 기반 compose 서비스 구성](docs/adr/0008-기반-compose-서비스-구성.md)
- [0009 docker 설정 격리 구현과 점검](docs/adr/0009-docker-설정-격리-구현과-점검.md)
- [0010 화면 영역의 기술 묶음과 도구](docs/adr/0010-화면-영역의-기술-묶음과-도구.md)
- [0011 정적 화면 이미지와 웹 서버](docs/adr/0011-정적-화면-이미지와-웹-서버.md)
- [0012 화면 시험과 playwright 컨테이너](docs/adr/0012-화면-시험과-playwright-컨테이너.md)
- [0013 관리 노드와 부트스트랩 순서](docs/adr/0013-관리-노드와-부트스트랩-순서.md)
- [0014 인증서 수명과 자동 갱신](docs/adr/0014-인증서-수명과-자동-갱신.md)
- [0015 신뢰 구성](docs/adr/0015-신뢰-구성.md)
- [0016 이미지 검사 build checks trivy hadolint](docs/adr/0016-이미지-검사-build-checks-trivy-hadolint.md)
- [0017 라이선스 원칙 의무가 생기는 사용 금지](docs/adr/0017-라이선스-원칙-의무가-생기는-사용-금지.md)
- [0018 제3자 고지 THIRD_PARTY_NOTICES 자동 생성과 이미지 점검](docs/adr/0018-제3자-고지-THIRD_PARTY_NOTICES-자동-생성.md)
