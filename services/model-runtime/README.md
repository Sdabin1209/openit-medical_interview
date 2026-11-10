# model-runtime

## 1. 하는 일
모델 패키지(OCI 아티팩트)를 레지스트리에서 digest 로 받아 검증·적재하고, 적재한 모델로 LoRA-A 추출과 LoRA-B 응답 문장을 낸다. 추출 출력이 계약의 합격 조건을 지키는지 한 번 검사하고(output_guard) 값 고쳐 쓰기(D115)를 적용한다. 활성화 승인과 롤백을 받고 그 기록(승인자, 시각, 사유)을 남긴다. 추론 엔진(vLLM 의 OpenAI 호환 서버)은 별도 컨테이너이고 이 서비스가 부른다. 모델 패키지를 만드는 `package-publish` 도구도 이 영역에 있다. 모델 입출력 글자 규칙은 [libs/model-io](../../libs/model-io/README.md) 가 가진다.

## 2. 받는 계약·내는 계약
- HTTP 계약: [contracts/openapi/model-runtime.yaml](../../contracts/openapi/model-runtime.yaml)(작업 여섯 개와 `/healthz`, `/readyz`, `/metrics`). 타입은 `src/model_runtime/contract/models.py` 로 생성한다(`pyproject.toml` 의 `[tool.openit.contract]` 가 정본).
- 환경 입력: 계약 `ModelRuntimeEnv`. `tests/unit/test_settings.py` 가 설정 이름이 계약과 같은지 본다.
- 모델 패키지: 계약 `ModelPackageOciManifest`, `ModelPackageManifest`(README 의 '모델 패키지' 절).
- 이미지가 주입받는 것: [inputs.json](inputs.json)(계약 `ContainerInputs`, 이미지 라벨 `io.openit.inputs`).
- 추출·응답 요청은 계약 8.0.0 의 구조화된 값(질문 문항, 직전 문항, 상담원 말, 발화, 저장된 칸, 순서표, 칸 규격 / 행동, A 출력의 값·대상, 다음 자리와 질문 문장)이다. 모델 입력의 글과 state 는 이 서비스가 libs/model-io 로 만든다([변경 요청 004](../../docs/change-requests/model-runtime-004.md) 처리됨).

## 3. 컴포넌트
| 컴포넌트 | 파일 | 입력 → 출력 | 하는 일 |
|---|---|---|---|
| link_api | `link/api.py`, `link/auth.py`, `link/runtime.py` | 계약 요청 → 명령 | HTTP 서버, 인증(기계 토큰·사람 접근 토큰), 컴포넌트 호출 순서와 적재 작업 |
| link_registry | `link/registry.py` | 패키지 digest → 파일 | OCI Distribution(ORAS)으로 받기 |
| package_loader | `components/package_loader.py` | 패키지 digest → 적재된 모델 | 매니페스트·파일 digest·모델 입출력 버전·서빙 버전 검증, 어댑터 적재 |
| release | `components/release.py`, `store/release_log.py` | 활성화·롤백 요청 → 활성 패키지 | 활성 포인터와 기록(승인자, 시각, 사유) |
| prompt | `components/prompt.py` | 구조화된 요청 → 모델 입력 | state 에 넣을 문항 고르기, 사람 말 조각 만들기, 학습 데이터와 글자가 같은 직렬화 |
| inference | `components/inference.py`, `link/engine.py` | 모델 입력 → 모델 출력 글자 | 엔진 호출과 시간 상한(추출 20초, 응답 25초) |
| output_guard | `components/output_guard.py` | 모델 출력 → 검증된 추출 결과 | 위반 코드 10개 검사, D115 고쳐 쓰기, 출력 불가 |
| responder | `components/responder.py` | 모델 출력 → 응답 문장 | 비었거나 길거나 JSON 으로 감싼 출력을 거른다 |
| package_publish(도구) | `components/package_publish.py`, `publish.py`, `link/publish_registry.py` | 어댑터 폴더·평가 집합 → 패키지 digest | 평가 보고서를 만들고 OCI 아티팩트로 올린다 |

진입점: 서버 `model-runtime`(`serve.py`: 영역 사이 mTLS 서버와 컨테이너 안 루프백 건강 확인), 도구 `package-publish`(`publish.py`).

### 모델 패키지 게시(관리 노드에서)
```
package-publish question-bank --reference-db <questionnaire_reference.sqlite3> --out bank.json
package-publish publish --adapter-a <LoRA-A 폴더> --adapter-b <LoRA-B 폴더> --system-prompt-a a.txt --system-prompt-b b.txt \
  --question-bank bank.json --eval-a <finaltest/lora_a_test.jsonl> --eval-b <finaltest/lora_b_test.jsonl> \
  --engine-url <vLLM 주소> --registry-url https://<레지스트리> --repository <저장소> --credentials-file <사용자:비밀번호 파일> \
  --root-certificate-file <사설 루트> --base-model Qwen/Qwen3-8B --dataset-version-id <UUID> --training-run-a <UUID> --training-run-b <UUID> \
  --runtime-contract-version 1 --workdir <작업 폴더> --report-out report.json
```
성공하면 표준 출력 마지막 줄이 패키지 digest 다. 평가는 엔진이 어댑터 폴더 경로를 같은 경로로 읽을 수 있어야 하고 GPU 에서 돈다.

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
tools/smoke service model-runtime           # 이미지 스모크(mTLS, 자체 HEALTHCHECK, 비 root, 라벨)
```
`libs/model-io` 를 고친 뒤에는 `uv sync --reinstall-package openit-model-io` 로 이 영역의 설치본을 갱신한다(경로 의존은 소스 변경을 자동으로 보지 않는다).

## 5. 시험 상태
2026-11-10 측정(검증 환경: 이 작업 트리의 WSL2 한 곳. 깨끗한 두 번째 환경은 확인하지 못했다).

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
- 계약 개정 전 요청 모양, `io.openit.inputs` 라벨을 만드는 틀(요청 003).
- 값의 근거를 측정하지 않은 것: 평가 동시성 8, 어댑터 보관 개수 2, JWKS 갱신 간격 30초, 지표 구간, 루프백 포트 18081(ADR 에 적었다).

## 6. ADR 목록
- [0001 템플릿에서 시작](docs/adr/0001-템플릿에서-시작.md)
- [0002 활성화·롤백 기록은 덧붙이는 파일 하나](docs/adr/0002-활성화-롤백-기록은-덧붙이는-파일-하나.md)
- [0003 레지스트리와 모델 패키지 형식, HTTP 클라이언트, 영역 사이 TLS](docs/adr/0003-레지스트리-패키지-형식-HTTP-클라이언트-TLS.md)
- [0004 추론 호출과 검증의 구조](docs/adr/0004-추론-호출과-검증의-구조.md)

변경 요청: [001](../../docs/change-requests/model-runtime-001.md) 계약 문구와 정본의 차이, [002](../../docs/change-requests/model-runtime-002.md) D115 R1·R3, [003](../../docs/change-requests/model-runtime-003.md) 환경 입력·파일 형식, [004](../../docs/change-requests/model-runtime-004.md) 구조화된 요청.
