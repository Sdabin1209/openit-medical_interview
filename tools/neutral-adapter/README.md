# neutral-adapter

기반 모델과 출력이 같은(LoRA B 행렬이 0) LoRA 어댑터를 Hugging Face PEFT(Apache-2.0)로 만드는 개발 도구다. E2E 의 파이프라인 모드(`./deploy e2e --mode pipeline`)가 학습된 어댑터 없이 게시·활성화·적재·추론 경로를 끝까지 지나가게 하려고 쓴다. 배포물에 들어가지 않는다.

```
uv run --project tools/neutral-adapter neutral-adapter --profile gpu-12g --out <폴더>    # 리포 루트에서. <폴더>/lora-a, lora-b 가 생기고 요약 JSON 한 줄을 낸다
cd tools/neutral-adapter && uv run pytest        # 시험(허브에 접속하지 않는다)
```

- **기반 모델:** 프로파일의 기반 모델이다. 표의 정본은 model-runtime 의 `profiles.json` 이고(`--profiles-file` 로 바꿀 수 있다) D81 이 `gpu-12g` 를 Qwen3-1.7B 로 정했다.
- **구성:** rank 16, 모든 선형층(`all-linear`, lm_head 제외). 근거는 `contracts/inputs/DECISIONS.md` D74(3)이다. `lora_alpha`(32)와 dropout(0)은 학습 서버 설정을 읽지 못해 정한 값이고 B=0 이라 출력에 영향이 없다(`src/neutral_adapter/adapter.py` 의 주석).
- **가중치 전체를 받지 않는다.** 모델 구성 파일(`config.json`) 하나만 허브에서 받고, 가중치 없는(meta 장치) 모델에 PEFT 로 LoRA 층을 얹어 이름·모양을 얻는다. 허브 접속을 피하려면 `--config-dir` 로 구성 폴더를 준다.
- **같은 입력이면 같은 바이트.** A 행렬은 역할마다 고정한 시드로 채우고(PEFT 기본 초기화와 같은 범위), B 는 0 이다. 모델 카드(README.md)는 지운다(라이브러리 버전이 들어가 바이트가 달라진다). 시험이 프로세스 해시 시드가 달라도 같은 바이트인 것과, 작은 Qwen3 에 얹은 로짓이 기반 모델과 같은 것을 본다.
- **CPU 바퀴:** `pyproject.toml` 이 PyTorch 의 CPU 인덱스에서 torch 를 받는다(GPU 라이브러리 수 GB 를 받지 않는다).
