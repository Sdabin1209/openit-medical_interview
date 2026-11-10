# 변경 요청 model-runtime-003: 환경 입력과 패키지 파일 형식에서 계약이 비어 있는 곳

- 영역: model-runtime
- 대상 계약: `ModelRuntimeEnv`, `ModelPackageBlobMediaType`, `ModelPackageBlobDescriptor`
- 상태: 헤드 결정 대기. 아래 임시 선택으로 구현했다(ADR services/model-runtime 0002, 0003).

| 번호 | 비어 있는 곳 | 임시 선택 | 요청 |
|---|---|---|---|
| 1 | `ModelRuntimeEnv` 에 추론 엔진 주소 입력이 없다. 환경 변수는 스키마에 있는 이름만 받을 수 있다 | 영역 안 고정 이름 `http://inference-engine:8000` 상수 | `OPENIT_INFERENCE_ENGINE_URL` 입력을 더한다 |
| 2 | 어댑터를 엔진에 올릴 때 경로가 엔진 컨테이너에서도 같아야 한다(vLLM 의 `lora_path`) | 캐시 폴더를 엔진 컨테이너가 같은 경로로 마운트한다고 가정 | 엔진이 보는 어댑터 폴더 입력을 정하거나 같은 경로 마운트를 배치 규칙으로 못박는다 |
| 3 | `OPENIT_HOSTS_TABLE_FILE`(이름 표 파일)의 형식이 없다 | 받기만 하고 쓰지 않는다 | 형식을 `HostsTable` 스키마로 정의한다 |
| 4 | `OPENIT_REGISTRY_CREDENTIALS_FILE`(자격 파일)의 내용 형식이 없다 | `사용자:비밀번호` 한 줄, 기본 인증(RFC 7617) | 형식과 인증 방식(기본 인증인지 토큰 인증인지)을 정한다 |
| 5 | 가중치 layer(`application/vnd.openit.model.adapter.weights.v1`)는 파일 하나인데 vLLM 어댑터는 폴더(adapter_config.json 과 가중치)다 | 어댑터 폴더를 같은 입력이면 같은 바이트의 tar 로 묶은 파일 | 미디어 유형 설명에 '어댑터 폴더의 tar' 를 적는다 |
| 6 | 서비스의 `OPENIT_MODEL_PROFILE` 이 하는 일이 정해져 있지 않다(기반 모델과 서빙 크기를 고른다고만 적혀 있다) | 받아서 읽기만 한다. 엔진 기반 모델은 엔진 컨테이너 설정이 정한다 | 프로파일이 정하는 값의 표(기반 모델, 서빙 크기)의 정본을 정한다 |
| 7 | 영역 사이 mTLS 를 서비스가 끝내는지 영역 게이트웨이가 끝내는지(Env 에는 서비스의 TLS 인증서와 개인키가 있다) | 서비스가 TLS 를 끝내고 클라이언트 인증서를 요구한다. 컨테이너 건강 확인은 루프백 포트 | 게이트웨이와의 역할을 정한다 |
| 8 | 이미지 라벨 `io.openit.inputs` 를 `docker-bake.hcl`·Dockerfile 틀이 만들지 않는다 | 영역 `inputs.json`(ContainerInputs 로 검증)을 Dockerfile 라벨에 글자 그대로 넣고 시험이 같은지 본다 | 틀이 라벨을 만들게 한다 |
