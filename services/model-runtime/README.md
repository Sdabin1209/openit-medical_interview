# model-runtime

## 1. 하는 일
모델 패키지(OCI 아티팩트)를 레지스트리에서 digest 로 받아 검증·적재하고, 적재한 모델로 LoRA-A 추출과 LoRA-B 응답 문장을 낸다. 추출 출력이 계약의 합격 조건을 지키는지 한 번 검사하고(output_guard) 값 고쳐 쓰기(D115)를 적용한다. 활성화 승인과 롤백을 받고 그 기록(승인자, 시각, 사유)을 남긴다. 추론 엔진(vLLM 의 OpenAI 호환 서버)은 별도 컨테이너이고 이 서비스가 부른다. 모델 패키지를 만드는 `package-publish` 도구도 이 영역에 있다. 모델 입출력 글자 규칙은 [libs/model-io](../../libs/model-io/README.md) 가 가진다.

## 2. 받는 계약·내는 계약
계약은 [9.2.1](../../contracts/README.md)(`contracts/README.md` 의 9.0.0·9.1.0·9.2.0·9.2.1 절)이다. 적재 시간 상한은 계약 `TimeBudgetTable.model_load` 다([ADR 0012](docs/adr/0012-적재-시간-상한은-계약-값이다.md)).

- HTTP 계약: [contracts/openapi/model-runtime.yaml](../../contracts/openapi/model-runtime.yaml)(작업 여덟 개(응답 문장 스트림 `generateResponseStream` 포함)와 `/healthz`, `/readyz`, `/metrics`). 게시된 패키지 목록(`listModelPackages`)은 [ADR 0008](docs/adr/0008-게시된-모델-패키지-목록.md). 타입은 `src/model_runtime/contract/models.py` 로 생성한다(`pyproject.toml` 의 `[tool.openit.contract]` 가 정본).
- 환경 입력: 계약 `ModelRuntimeEnv`(엔진 주소 `OPENIT_INFERENCE_ENGINE_URL`, 이름 표 `HostsTable`, 레지스트리 자격은 한 줄 `사용자:비밀번호`의 HTTP 기본 인증: [ADR 0006](docs/adr/0006-계약-9.0.0-입력-엔진-주소-이름-표-자격-어댑터-배치.md)). `tests/unit/test_settings.py` 가 설정 이름이 계약과 같은지 본다.
- 인증: 사람과 기계 호출자 모두 IdP 가 낸 JWT 접근 토큰(RFC 9068). 기계 호출자는 `MachineIdentityClaims`(`client_id` 는 `machine-<이름>`, 역할 `inference-caller`)이고 호출자 표(`MachineTokenTable`, 비밀 없음)로 허용을 확인한다. 계약 밖 역할이 토큰에 실리면 401. TLS 는 영역 게이트웨이가 끝내고 서비스는 평문 HTTP 다([ADR 0005](docs/adr/0005-기계-호출자는-JWT-접근-토큰-서비스는-평문-HTTP.md)).
- 프로파일 표(`OPENIT_MODEL_PROFILE`): 영역 안 `src/model_runtime/profiles.json`(기반 모델)이고 영역이 소유한다([ADR 0007](docs/adr/0007-프로파일-표와-기반-모델.md)).
- 노출·나가는 호출 선언: [exposure.json](exposure.json)(계약 `Exposure`, 이미지 라벨 `io.openit.exposure`, [ADR 0009](docs/adr/0009-노출-선언과-나가는-호출-선언.md)). 이 영역에는 잡이 없어 `jobs.json` 이 없다.
- 모델 패키지: 계약 `ModelPackageOciManifest`, `ModelPackageManifest`(README 의 '모델 패키지' 절).
- 이미지가 주입받는 것: [inputs.json](inputs.json)(계약 `ContainerInputs`, 이미지 라벨 `io.openit.inputs`). Dockerfile 은 `ARG INPUTS`·`ARG EXPOSURE` 로 받아 라벨로 단다.
- 어댑터 배치 규칙: 어댑터 폴더는 쓰기 경로 `/var/lib/openit/model-runtime` 아래에 풀리고 추론 엔진 컨테이너가 그 경로를 같은 경로로 읽기 전용 마운트한다(ADR 0006).
- 추출·응답 요청은 계약 8.0.0 의 구조화된 값(질문 문항, 직전 문항, 상담원 말, 발화, 저장된 칸, 순서표, 칸 규격 / 행동, A 출력의 값·대상, 다음 자리와 질문 문장)이다. 모델 입력의 글과 state 는 이 서비스가 libs/model-io 로 만든다([변경 요청 004](../../docs/change-requests/model-runtime-004.md) 처리됨).

## 3. 컴포넌트
| 컴포넌트 | 파일 | 입력 → 출력 | 하는 일 |
|---|---|---|---|
| link_api | `link/api.py`, `link/auth.py`, `link/runtime.py` | 계약 요청 → 명령 | 평문 HTTP 서버, 인증(JWT 접근 토큰: 사람·기계), 컴포넌트 호출 순서와 적재 작업 |
| link_registry | `link/registry.py`, `link/oci_reference.py`, `link/hosts.py` | 패키지 digest → 파일, 저장소 → 게시된 매니페스트들 | OCI Distribution(ORAS)으로 받기와 태그 목록, 이름 표, 클라이언트 인증서 |
| package_catalog | `components/package_catalog.py` | 게시된 매니페스트들·활성 digest·Limit·Cursor → 패키지 목록 한 쪽 | 최근 것이 먼저, 쪽 나누기, 활성 여부 |
| package_loader | `components/package_loader.py` | 패키지 digest → 적재된 모델 | 매니페스트·파일 digest·모델 입출력 버전·서빙 버전·기반 모델(프로파일 표) 검증, 어댑터 적재 |
| release | `components/release.py`, `store/release_log.py` | 활성화·롤백 요청 → 활성 패키지 | 활성 포인터와 기록(승인자, 시각, 사유) |
| prompt | `components/prompt.py` | 구조화된 요청 → 모델 입력 | state 에 넣을 문항 고르기, 사람 말 조각 만들기, 학습 데이터와 글자가 같은 직렬화 |
| inference | `components/inference.py`, `link/engine.py` | 모델 입력 → 모델 출력 글자 | 엔진 호출(학습과 같은 비생각 모드, ADR 0010)과 시간 상한(추출 20초, 응답 25초) |
| output_guard | `components/output_guard.py` | 모델 출력 → 검증된 추출 결과 | 위반 코드 10개 검사, D115 고쳐 쓰기, 출력 불가 |
| responder | `components/responder.py` | 모델 출력 → 응답 문장 | 계약 `ResponseSentence` 로 가려 어긋나면 503. 스트림은 앞뒤 공백을 쥐거나 버리고 조각을 이어 같은 조건을 지킨다(ADR 0013) |
| package_publish(도구) | `components/package_publish.py`, `publish.py`, `link/publish_registry.py` | 어댑터 폴더·평가 집합 → 패키지 digest | 평가 보고서를 만들고 OCI 아티팩트로 올린다 |

진입점: 서버 `model-runtime`(`serve.py`: `OPENIT_LISTEN_PORT` 의 평문 HTTP. 컨테이너 `HEALTHCHECK` 도 그 포트의 `/healthz`), 도구 `package-publish`(`publish.py`).

### 모델 패키지 게시(관리 노드에서)
```
package-publish question-bank --reference-db <questionnaire_reference.sqlite3> --out bank.json
package-publish publish --adapter-a <LoRA-A 폴더> --adapter-b <LoRA-B 폴더> --system-prompt-a a.txt --system-prompt-b b.txt \
  --question-bank bank.json --eval-a <finaltest/lora_a_test.jsonl> --eval-b <finaltest/lora_b_test.jsonl> \
  --engine-url <vLLM 주소> --registry-url https://<레지스트리> --repository <저장소> --credentials-file <사용자:비밀번호 파일> \
  --root-certificate-file <사설 루트> --base-model Qwen/Qwen3-8B --dataset-version-id <UUID> --training-run-a <UUID> --training-run-b <UUID> \
  --runtime-contract-version 1 --model-io-version model-io-v3 --workdir <작업 폴더> --report-out report.json   # v2 어댑터면 --model-io-version 을 빼거나 model-io-v2
```
성공하면 표준 출력 마지막 줄이 패키지 digest 다. 패키지마다 태그 `sha256-<16진수>` 도 달아 목록(`listModelPackages`)에 나오게 한다. 평가는 엔진이 어댑터 폴더 경로를 같은 경로로 읽을 수 있어야 하고 GPU 에서 돈다.

## 4. 실행·시험 명령
```
uv sync
uv run pytest            # 단위, 시나리오(가짜 엔진), 계약 적합성(Schemathesis). 스모크는 제외
uv run lint-imports      # 경계 점검
uv run pyright           # 타입 검사(strict)
uv run ruff check        # 린트
uv run --project tools/checks openit-gen-contract services/model-runtime   # 계약 타입 다시 만들기(리포 루트에서, ADR 0020)
deploy/deploy build model-runtime   # 이미지 빌드(Trivy 포함)
uv run --project tools/checks openit-notices generate services/model-runtime   # 의존을 바꾼 뒤 THIRD_PARTY_NOTICES 를 다시 만든다(리포 루트에서, ADR 0018)
tools/smoke service model-runtime           # 이미지 스모크(평문 HTTP, 자체 HEALTHCHECK, 비 root, 라벨)
```
`libs/model-io` 를 고친 뒤에는 `uv sync --reinstall-package openit-model-io` 로 이 영역의 설치본을 갱신한다(경로 의존은 소스 변경을 자동으로 보지 않는다).

## 5. 시험 상태
**2026-11-11, 계약 9.1.0 반영 뒤**(검증 환경: 이 작업 트리의 WSL2 한 곳. 깨끗한 두 번째 환경은 확인하지 못했다). `uv run pytest` 167개 통과(스모크 5개 제외), 이미지 스모크 5개 통과, `ruff check`, `ruff format --check`, `pyright`, `lint-imports` 통과. `libs/model-io` 는 `pytest` 83개 통과와 같은 점검 통과. `openit-check` 의 `declarations`, `area-isolation`, `dockerfile-lint`, `notices`, `licenses` 통과.
이번에 시험이 새로 지키는 것: 레지스트리 이름이 `registry`·`registry:443`·점이 있는 이름일 때 게시·받기·목록이 같은 저장소 경로(ADR 0011), 채팅 호출이 학습과 같은 비생각 조건(ADR 0010), 적재 상한을 넘으면 FAILED 이고 이전 패키지 유지(ADR 0012). 앞서 지키던 것: JWT 기계 호출자 인증(호출자 표 허용, 계약 밖 역할 무시, 고정 문자열 토큰 거부), 평문 서버, 엔진 주소 입력, 이름 표(`HostsTable`)로 접속, 레지스트리 자격 형식(RFC 7617)과 클라이언트 인증서, 어댑터 tar 가 같은 입력이면 같은 바이트, 프로파일 표와 기반 모델 불일치 거부, 게시된 패키지 목록(정렬·쪽 나누기·활성 표시), `inputs.json`·`exposure.json` 이 계약과 작업 `security` 에 맞는 것.

**이번 작업에서 하지 못한 것:** 서빙 프롬프트가 학습 서열과 토큰 단위로 같은지 실제 vLLM 으로 비교하는 것(ADR 0010). 학습 파일 정답으로 위반 0 을 재는 시험(`-m dataset`)은 학습 파일이 이 트리에 없어 다시 재지 못했다. 아래 표는 2026-11-10 이전 작업의 측정이다(이번에 재확인하지 않았다).

**학습 서버 학습 파일 정답 출력(`final` 44563행 + `finaltest` 2092행 = LoRA-A 46655행, ssh 로 읽기만 함)**

| 측정 | 결과 |
|---|---|
| 정답 출력의 합격 조건 위반(위반 코드 10개) | **0행** |
| 정답 출력이 출력 불가가 된 행 / 고쳐 쓰기가 값을 바꾼 행 | 0행 / 0행 |
| A 입력 직렬화가 학습 user 메시지와 바이트까지 같음 | `final` 44563/44563. `finaltest` 92행(state 비어 있음)만 같고 2000행은 state 항목 안 키 순서가 달라 내용은 같다([변경 요청 001](../../docs/change-requests/model-runtime-001.md)) |
| B 입력 직렬화 | 46774행 중 46764행 같음. 10행은 학습 파일 자체가 정렬되어 있지 않다 |
| LoRA-A 입력을 저장된 칸 목록에서 만든 것(`compose_extraction_input`, state 고르기와 묶음 순서) | 46655행 모두 고른 문항 집합이 같다. 칸 순서까지 같음: `final` 43886/44563(98.48%), `finaltest` 1843/2092(88.1%). 바이트까지 같은 전체 입력 43978행. 틀린 순서는 학습 데이터가 시나리오 정보로 정한 것이다(prev_state.py, 재현 불가, libs/model-io ADR 0004). 직전 문항은 학습 파일에 없어 시험이 되만들었다 |
| LoRA-B 입력을 요청 모양(저장된 칸, A 출력의 값·대상, 다음 자리)에서 만든 것(`compose_response_from_request`) | 46655/46655행 내용 같음 |
| B 입력을 A 정답·state·다음 질문 문장에서 만든 것(`compose_response_input`) | 46655/46655행 내용 같음, 46645행 바이트까지 같음(10행은 위와 같은 정렬되지 않은 행), START 110/110 |
| next_item 규칙: 정본(labels.py) 방식 / 계약 문구 방식 | 불일치 0건 / 168건([변경 요청 001](../../docs/change-requests/model-runtime-001.md)) |

**명령별 결과**는 헤드 보고에 있다. 시험이 지키는 것: 위반 코드마다 위반 사례, 고쳐 쓰기, 패키지 검증 조건마다 위반 사례(매니페스트, 파일 digest, 미디어 유형, 모델 입출력 버전, 서빙 버전, 어댑터 tar 의 경로 이탈·링크), 인증(RFC 9068 프로파일 위반 13가지), 활성화·롤백 기록, 가짜 엔진 시나리오(게시 → 적재 → 활성화 → 추출(정상·고쳐 쓰기·출력 불가) → 응답 문장 → 롤백 → 재시작 복원), Schemathesis(적재 전·후, 인증 없음·있음), 이미지 스모크.

**확인하지 못한 것**
- 실제 vLLM·GPU: 어댑터 올리기(`/v1/load_lora_adapter`), 제약 디코딩(`response_format` 의 json_schema), 평가 호출 시간. 가짜 엔진은 OpenAI 호환 API 의 이 영역이 쓰는 부분만 흉내 낸다. GPU 에서 확인해야 한다.
- 실제 OCI 레지스트리(Distribution + Caddy): 시험용 레지스트리는 OCI Distribution 의 push·pull 최소 부분이다.
- 실제 Keycloak: 시험용 신원 공급자(JWKS)로 RFC 9068 프로파일을 확인했다.
- `io.openit.inputs`·`io.openit.exposure` 라벨을 deploy build 가 `INPUTS`·`EXPOSURE` 인자로 넘겨 다는 것(헤드 몫, 이미지를 빌드하지 않았다). 레지스트리 egress 를 deploy 가 더하는 것(005 확정), platform 의 기계 클라이언트 범위 제한이 실제 Keycloak 토큰에서 적용되는지(006 확정), 인증서 파일 갱신 중 교체, 실제 vLLM 의 `/v1/models` 기반 모델 이름.
- 값의 근거를 측정하지 않은 것: 평가 동시성 8, 어댑터 보관 개수 2, JWKS 갱신 간격 30초, 지표 구간, 태그 목록 쪽 크기 100(ADR 에 적었다).

## 6. ADR 목록
- [0001 템플릿에서 시작](docs/adr/0001-템플릿에서-시작.md)
- [0002 활성화·롤백 기록은 덧붙이는 파일 하나](docs/adr/0002-활성화-롤백-기록은-덧붙이는-파일-하나.md)
- [0003 레지스트리와 모델 패키지 형식, HTTP 클라이언트, 영역 사이 TLS](docs/adr/0003-레지스트리-패키지-형식-HTTP-클라이언트-TLS.md)
- [0004 추론 호출과 검증의 구조](docs/adr/0004-추론-호출과-검증의-구조.md)
- [0005 기계 호출자는 JWT 접근 토큰, 서비스는 평문 HTTP](docs/adr/0005-기계-호출자는-JWT-접근-토큰-서비스는-평문-HTTP.md)(0003 의 7항·8항 일부를 대체)
- [0006 계약 9.0.0 입력: 엔진 주소, 이름 표, 자격, 어댑터 배치](docs/adr/0006-계약-9.0.0-입력-엔진-주소-이름-표-자격-어댑터-배치.md)
- [0007 프로파일 표와 기반 모델](docs/adr/0007-프로파일-표와-기반-모델.md)
- [0008 게시된 모델 패키지 목록](docs/adr/0008-게시된-모델-패키지-목록.md)
- [0009 노출 선언과 나가는 호출 선언](docs/adr/0009-노출-선언과-나가는-호출-선언.md)
- [0010 채팅 호출은 학습과 같은 템플릿 조건(비생각 모드)으로 한다](docs/adr/0010-채팅-호출은-학습과-같은-템플릿-조건-비생각-모드.md)
- [0011 저장소 경로는 레지스트리 이름과 따로 ORAS Container 로 만든다](docs/adr/0011-저장소-경로는-레지스트리-이름과-따로-ORAS-Container-로-만든다.md)(0008 의 목록 결함을 고침)
- [0012 모델 적재의 시간 상한은 계약 값이다](docs/adr/0012-적재-시간-상한은-계약-값이다.md)
- [0013 응답 문장 스트림은 Starlette StreamingResponse 와 작업 큐로 낸다](docs/adr/0013-응답-문장-스트림은-Starlette-StreamingResponse-와-큐로-낸다.md)

변경 요청: [001](../../docs/change-requests/model-runtime-001.md) 계약 문구와 정본의 차이, [002](../../docs/change-requests/model-runtime-002.md) D115 R1·R3(9.0.0 이 명시적 비활성으로 정함), [003](../../docs/change-requests/model-runtime-003.md) 환경 입력·파일 형식(9.0.0 이 정함), [004](../../docs/change-requests/model-runtime-004.md) 구조화된 요청, [005](../../docs/change-requests/model-runtime-005.md) 레지스트리 egress 선언(확정: deploy 가 설치 설정에서 더함), [006](../../docs/change-requests/model-runtime-006.md) 기계 토큰 역할 클레임(확정: platform 이 범위를 제한하고 서비스는 계약 모델로 그대로 검증). 모델 패키지 목록은 admin-console-002 를 구현했다.
