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
| 공통 점검 | `cd tools/checks && uv run openit-check all` |
| 점검 자체 시험 | `cd tools/checks && uv run pytest` |
| 배포 환경 확인 | `deploy/deploy doctor` |

템플릿은 `templates/service`, `templates/web`이고 `services/_example`, `web/_example`은 템플릿 시험용으로 남겨 둔다(실제 영역이 아니다).
