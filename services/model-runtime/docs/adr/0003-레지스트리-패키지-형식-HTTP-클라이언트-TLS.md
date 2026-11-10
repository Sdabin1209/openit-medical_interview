# 0003. 레지스트리와 모델 패키지 형식, HTTP 클라이언트, 영역 사이 TLS

## 상태
승인(2026-11-10, model-runtime 영역 작업자). 계약이 비워 둔 곳은 변경 요청 model-runtime-003 으로 헤드에게 넘겼다.

일부 대체(2026-11-11): 7항(영역 사이 TLS)과 8항의 기계 토큰은 [ADR 0005](0005-기계-호출자는-JWT-접근-토큰-서비스는-평문-HTTP.md) 가 대체한다. 3항(패키지 파일 형식)·2항(기본 인증)은 [ADR 0006](0006-계약-9.0.0-입력-엔진-주소-이름-표-자격-어댑터-배치.md) 이 계약 9.0.0 에 맞춰 확인했다. 아래 본문은 결정 당시 그대로 둔다.

## 결정
1. **레지스트리 클라이언트는 ORAS(oras-py, Apache-2.0).** 받기는 `get_manifest` 대신 `do_request` 로 매니페스트 원래 바이트를 받는다(digest 를 바이트로 확인하려고). 파일은 `get_blob` 을 스트림으로 받는다. 올리기는 `upload_blob` 과 매니페스트 `PUT`(바이트를 우리가 정한다. 계약 매니페스트는 annotations 가 없어 `oras push` 의 매니페스트와 다르다).
2. **인증은 기본 인증(`auth_backend="basic"`).** 플랫폼 레지스트리는 Distribution 앞의 Caddy 라 기본 인증이다. oras 의 기본 백엔드(토큰)는 기본 인증 도전(`WWW-Authenticate: Basic`)을 다루지 못하고 재시도에서 멈추는 것을 시험으로 확인했다. `login()` 은 사용자 전역 docker 설정을 건드려 쓰지 않는다(`auth.set_basic_auth`).
3. **패키지 파일 형식:** 가중치 layer = 어댑터 폴더(PEFT 출력)를 이름순·시각 0·소유자 0 으로 묶은 tar(같은 입력이면 같은 바이트). vLLM 이 읽는 어댑터는 폴더다. 풀 때는 `tarfile` 의 `data` 필터(PEP 706)로 폴더 밖 경로, 링크, 특수 파일을 막고 `adapter_config.json` 이 있어야 한다. 시스템 프롬프트 layer = UTF-8 글.
4. **파일 검증은 받는 쪽이 한다(D49):** 매니페스트 바이트의 sha256 = 요청한 digest, config·layer 의 digest 와 크기 = 목록표, 매니페스트 layers 집합 = 목록표 어댑터 파일 집합. 이미 받은 파일은 다시 해시해 같으면 다시 받지 않는다.
5. **HTTP 클라이언트는 httpx2(BSD-3-Clause).** openai SDK 3 가 httpx2 의 클라이언트를 요구한다(pyright 가 httpx 클라이언트를 거부하는 것을 확인). Starlette TestClient 도 httpx2 를 쓴다(ADR 0005). 그래서 이 영역의 제품 코드는 httpx 가 아니라 httpx2 를 쓴다(ADR 0001 의 httpx 선택을 이 영역에서만 바꾼다).
6. **추론 엔진 호출은 openai SDK(Apache-2.0)** 로 OpenAI 호환 채팅 완성을 부르고, 어댑터 올리기·내리기는 vLLM 의 런타임 LoRA 갱신 API(`/v1/load_lora_adapter`)를 같은 클라이언트로 부른다.
7. **영역 사이 TLS:** 서비스가 `OPENIT_LISTEN_PORT` 에서 TLS 를 끝내고 클라이언트 인증서를 요구한다(사설 루트가 신뢰 앵커, RFC 8705). 컨테이너 `HEALTHCHECK` 는 인증서 없이 볼 수 있도록 `127.0.0.1:18081` 의 건강 확인 전용 서버(같은 프로세스)가 맡는다. 이 포트는 컨테이너 밖에서 닿지 않는다.
8. **인증:** 추출·응답·적재 상태는 기계 토큰(`inference-caller`), 패키지 읽기·롤백은 사람 접근 토큰(`operator` 또는 `release-approver`), 활성화는 `release-approver`. 접근 토큰은 계약 README 의 RFC 9068 프로파일(typ, 비대칭 alg, JWKS 서명, iss, aud, exp·iat·sub·client_id·jti, 역할)을 모두 확인한다. 공개 키 집합은 알 수 없는 `kid` 가 올 때만 갱신하되 30초 간격을 둔다(엉터리 토큰으로 발급자를 두드리지 못하게. 측정하지 않은 값).

## 왜
표준: OCI Image Spec 1.1 과 OCI Distribution Spec, PEP 706, RFC 9068·7517·8705·7617. 기본 인증은 platform 의 구성에서 나온 가정이고(요청 003 4번), 가중치를 tar 로 묶는 것은 계약이 파일 형식을 정하지 않아서 고른 임시 선택이다(요청 003 5번).

## 검토한 대안과 버리는 이유
- **레지스트리 직접 HTTP 구현:** ORAS 가 표준 클라이언트다. 매니페스트 바이트만 다루는 부분은 ORAS 의 `do_request` 를 쓴다.
- **어댑터를 가중치 파일 하나로:** vLLM 이 어댑터 폴더를 읽는다.
- **mTLS 를 게이트웨이에만 맡기기:** `ModelRuntimeEnv` 가 서비스의 TLS 인증서와 개인키를 입력으로 준다.

## 결과와 되돌리는 조건
- 얻는 것: 표준 클라이언트와 표준 프로토콜, 파일 손상·경로 이탈을 적재 전에 막는다. 감수하는 것: httpx2 는 httpx 와 다른 패키지다. 서비스가 TLS 를 끝내므로 인증서 갱신 때 재시작이 필요하다(ADR 0014 와 맞춰야 한다).
- 헤드가 계약에서 파일 형식, 인증 방식, TLS 종단을 정하면 그에 맞춘다.
