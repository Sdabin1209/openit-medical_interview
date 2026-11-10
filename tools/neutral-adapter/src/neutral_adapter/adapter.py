"""중립 어댑터 만들기.

중립이란 LoRA 의 B 행렬이 모두 0 이라 어댑터를 얹어도 기반 모델의 출력이 바뀌지 않는다는 뜻이다(LoRA 의 출력 변화는 B·A·x 이므로 B=0 이면 0).
E2E 의 파이프라인 모드가 학습된 어댑터 없이 적재·활성화·추론 경로를 끝까지 지나가게 하려고 쓴다. 학습된 값은 하나도 없다.

가중치 전체를 받지 않는다: 모델 구성(config)만으로 가중치 없는 모델(meta 장치)을 만들고 PEFT 로 LoRA 층을 얹어 모양과 이름을 얻는다.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoConfig, AutoModelForCausalLM, PretrainedConfig

# 왜 16: 학습된 어댑터의 rank 다. DECISIONS.md D74(3)가 'Qwen3 기반 rank 16, 모든 선형층'으로 정했다. vLLM 의 --max-lora-rank 기본값(16)이 넘기지 못하는 값이기도 하다(D48).
# 학습 서버의 run_config.json(rank 의 실제 값)은 읽지 못했다(서버 접속 금지). D74 의 값을 따른다.
RANK = 16
# 왜 all-linear: D74(3)의 '모든 선형층'을 PEFT 가 표준으로 표현하는 값이다(출력층 lm_head 제외). 저장할 때 PEFT 가 실제 모듈 이름 목록으로 풀어 쓴다.
TARGET_MODULES = "all-linear"
# 왜 32(2배 rank): 학습 인자 --alpha 의 값을 읽지 못했다(미확인). 중립 어댑터에서는 B=0 이라 alpha 가 출력에 영향이 없으므로 PEFT·LoRA 논문 관행의 2배 rank 를 둔다.
ALPHA = 32
DROPOUT = 0.0  # 왜 0: 추론용 어댑터다. 학습 때의 dropout 은 추론에 쓰이지 않는다(PEFT 는 eval 에서 끈다)
# 왜 역할마다 다른 시드: A 행렬 값만 시드로 정해진다. 두 어댑터가 같은 바이트면 적재 시험에서 서로 바뀌어도 알 수 없다. 값 자체에 의미는 없다
SEEDS = {"LORA_A": 20261111, "LORA_B": 20261112}


@dataclass(frozen=True)
class AdapterSpec:
    """LoRA 어댑터 구성. 값의 근거는 위 상수의 주석."""

    rank: int = RANK
    alpha: int = ALPHA
    dropout: float = DROPOUT
    target_modules: str = TARGET_MODULES


def load_model_config(base_model: str, config_dir: Path | None = None) -> PretrainedConfig:
    """모델 구성 파일(config.json) 하나만 읽는다. config_dir 가 있으면 그 폴더에서(허브에 접속하지 않는다)."""
    return AutoConfig.from_pretrained(str(config_dir) if config_dir else base_model)


def _lora_pairs(model: PeftModel) -> Iterator[tuple[str, torch.nn.Linear, torch.nn.Linear]]:
    for name, module in model.named_modules():
        lora_a = getattr(module, "lora_A", None)
        lora_b = getattr(module, "lora_B", None)
        if lora_a is not None and lora_b is not None and "default" in lora_a:
            yield name, lora_a["default"], lora_b["default"]


def _materialize(model: PeftModel, seed: int) -> None:
    """meta 장치의 LoRA 가중치를 CPU 값으로 채운다. A: PEFT 기본 초기화(kaiming uniform, a=√5)와 같은 범위의 시드 고정 균등분포, B: 0."""
    generator = torch.Generator(device="cpu").manual_seed(seed)
    for _name, lora_a, lora_b in _lora_pairs(model):
        bound = 1.0 / lora_a.in_features**0.5  # kaiming_uniform_(a=√5)의 한계: sqrt(6 / ((1 + 5) * fan_in)) = 1 / sqrt(fan_in)
        values = (torch.rand(lora_a.weight.shape, generator=generator, dtype=torch.float32) * 2 - 1) * bound
        lora_a.weight = torch.nn.Parameter(values)
        lora_b.weight = torch.nn.Parameter(torch.zeros(lora_b.weight.shape, dtype=torch.float32))


def build_adapter(config: PretrainedConfig, base_model: str, out_dir: Path, role: str, spec: AdapterSpec | None = None) -> Path:
    """어댑터 폴더 하나(adapter_config.json, adapter_model.safetensors)를 만든다. 같은 입력이면 같은 바이트다."""
    if role not in SEEDS:
        raise ValueError(f"알 수 없는 역할 {role}. 가능: {', '.join(SEEDS)}")
    spec = spec or AdapterSpec()
    with torch.device("meta"):
        model = AutoModelForCausalLM.from_config(config)
    lora = LoraConfig(
        r=spec.rank,
        lora_alpha=spec.alpha,
        lora_dropout=spec.dropout,
        target_modules=spec.target_modules,
        task_type="CAUSAL_LM",
        base_model_name_or_path=base_model,
    )
    peft_model = get_peft_model(model, lora)
    _materialize(peft_model, SEEDS[role])
    saved = peft_model.peft_config["default"]
    # 왜 직접 적나: from_config 로 만든 모델은 허브 이름을 모른다. PEFT 가 모델에서 읽는 base_model_name_or_path 가 비므로 기반 모델 이름을 적는다(적재 쪽이 기반 모델 일치를 이 값으로 확인한다)
    saved.base_model_name_or_path = base_model
    # 왜 짧은 이름으로 접나: PEFT 가 'all-linear' 를 층마다 전체 경로(model.layers.0.self_attn.q_proj ...)로 풀어 쓴다. 학습된 어댑터의 관례(층 이름 없는 모듈 이름 집합)로 접는다
    # 정렬한 목록으로 쓴다: 집합을 그대로 저장하면 문자열 해시 시드에 따라 순서가 달라져 같은 입력이 프로세스마다 다른 바이트가 된다
    saved.target_modules = sorted({name.rsplit(".", 1)[-1] for name in saved.target_modules})  # type: ignore[union-attr]
    out_dir.mkdir(parents=True, exist_ok=True)
    # 왜 save_embedding_layers=False: 어댑터는 임베딩을 바꾸지 않는다. 기본값(auto)은 허브에 접속해 어휘 크기를 비교하고, 다르면 기반 가중치(meta)까지 저장하려 해 실패한다
    peft_model.save_pretrained(str(out_dir), safe_serialization=True, save_embedding_layers=False)
    # 왜 지우나: PEFT 가 쓰는 모델 카드(README.md)에는 라이브러리 버전이 들어가 어댑터 내용과 무관하게 바이트가 달라진다. 어댑터가 읽는 파일이 아니다
    (out_dir / "README.md").unlink(missing_ok=True)
    return out_dir


def folder_digest(folder: Path) -> str:
    """어댑터 폴더의 내용 해시(파일 이름과 바이트, 이름 순). 같은 입력이면 같은 바이트인지 비교하는 데 쓴다."""
    digest = hashlib.sha256()
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        digest.update(path.relative_to(folder).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def describe(folder: Path) -> dict[str, object]:
    """만든 어댑터의 요약(구성 파일에서 읽는다)."""
    config = json.loads((folder / "adapter_config.json").read_text(encoding="utf-8"))
    return {
        "base_model": config["base_model_name_or_path"],
        "rank": config["r"],
        "target_modules": sorted(config["target_modules"]),
        "sha256": folder_digest(folder),
    }
