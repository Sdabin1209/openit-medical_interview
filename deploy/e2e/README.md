# deploy/e2e

`./deploy e2e` 가 부르는 E2E 실행 도구다. 규약과 근거는 [ADR 0025](../../docs/adr/0025-E2E-실행-규약과-두-모드.md), 결과는 [E2E_RESULTS.md](../docs/E2E_RESULTS.md) 한 곳이다.

## 실행

```
deploy/deploy build                         # 영역 이미지가 이 엔진에 있어야 한다(없으면 시작 전에 멈춘다)
deploy/deploy e2e --mode pipeline           # D81 gpu-12g(Qwen3-1.7B)와 중립 어댑터(tools/neutral-adapter). 12GB GPU 면 된다
deploy/deploy e2e --mode product --adapters-a <폴더> --adapters-b <폴더> --profile rtx4090-24g
cd deploy/e2e && uv run pytest              # 도구 시험(docker 없음)
```

종료 코드: 0 모든 단계 통과, 1 실패, 2 사용법 오류. 실패하면 `.e2e/logs/<프로젝트>/`(git 제외)에 상태와 로그를 남기고 이 실행의 프로젝트(`openit-e2e-<무작위>`)만 `down -v` 한다. 기반 모델 가중치는 이름 있는 볼륨 `openit-e2e-hf-cache` 에 남겨 다음 실행이 쓴다(지우려면 `docker volume rm openit-e2e-hf-cache`).

## product 모드의 입력

- `--adapters-a`, `--adapters-b`: PEFT 어댑터 폴더(`adapter_config.json`, `adapter_model.safetensors` 또는 `adapter_model.bin`)와 **학습에 쓴 시스템 프롬프트 파일 `system_prompt.txt`**. LoRA-A 는 추출, LoRA-B 는 응답 문장이다. 기반 모델은 어댑터의 `base_model_name_or_path` 이고 A·B 가 같아야 한다.
- `--profile`: model-runtime 의 프로파일 이름(예: `rtx4090-24g`, 기반 Qwen3-8B). 어댑터의 기반 모델과 프로파일의 기반 모델이 다르면 model-runtime 이 활성화에서 거부한다(그것이 E2E 의 실패다).
- GPU: 프로파일의 기반 모델을 올릴 수 있는 GPU 한 장(`rtx4090-24g` 는 24GB급). 엔진 크기 인자는 제품 기본값을 쓴다. 기반 모델 가중치(Qwen3-8B 는 약 16GB)는 허브에서 받아 볼륨에 둔다.
- product 는 학습된 어댑터로 같은 시스템 규칙을 본다. 이 시험은 프레임워크 시험이라([ADR 0030](../../docs/adr/0030-E2E-product-판정은-프레임워크-기준.md)) 모델이 낸 결과(실패 신호, 확인·되묻기 반복, 문진 미완료, 대본 기대 값과 다른 저장)는 단계 기록에 '모델 관찰(판정 밖)'으로 적고 실패로 보지 않는다. 같은 문항이 세 번을 넘어 되돌아오면 세션을 끝내고 ⑥~⑧로 간다. 실패한 턴은 다시 보내지 않는다.
- pipeline 은 어댑터가 학습되지 않아 턴이 결정적으로 실패하는 것을 이용해 연속 실패 한도를 본다: 실패 1·2번째는 실패 신호이고 답·지금 문항이 그대로, 3번째는 실패 신호 없이 안내 문장(`ResponseSentence` 검증, 글은 비교하지 않음)과 다음 문항, 이어서 같은 모양이 되풀이된다. 실패한 `turn_id` 를 한 번 다시 보내도 연속 실패 수가 오르지 않아야 한다(성공을 바라는 재시도가 아니라 계약 규칙을 보는 의도된 호출 하나). ⑥은 건너뛴 문항의 빈칸 원인이 `FAILURE_LIMIT`, ⑦은 그 칸의 FHIR `data-absent-reason` 이 `error` 인지 본다.

## 파일

| 파일 | 역할 |
|---|---|
| `src/openit_e2e/cli.py` | 인자, 순서(준비 → 설치 → 엔진 → 시나리오 → 정리), 결과 기록 |
| `sandbox.py` | 사본 만들기, 설치 입력, compose 조각, 엔진·게시 도구 실행, 진단과 정리 |
| `scenario.py` | 여덟 단계와 판정 |
| `sse.py` | 응답 문장 스트림 읽기: SSE 파서(WHATWG HTML 9.2), 머리글·이벤트 규칙 점검. 5단계는 `startSessionStream`·`submitTurnStream` 으로 세션을 돌리고 건마다 delta 수·첫 delta·result 까지의 시간(단조 시계, 보고용이며 합격 조건이 아니다)을 기록한다. product 모드는 delta 가 한 번이라도 result 앞에 와야 한다 |
| `contract.py` | 계약 파일로 요청·응답 검증(format 단언 켬) |
| `ingress.py` | 입구로 요청하는 클라이언트(기기 인증서, 로그인 쿠키, 기계 토큰) |
| `questionnaire.py`, `script.py` | `contracts/inputs/SQL.md` 에서 만든 문항 세트, 발화 대본과 기대 값, 평가 집합 |
| `adapters.py`, `devices.py`, `report.py` | 어댑터 선택, 시험용 기기 PKI, 결과 기록 파일 |
