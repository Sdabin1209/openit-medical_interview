"""시험에 쓸 어댑터 두 개(LoRA-A, LoRA-B)와 그 시스템 프롬프트를 정한다.

- pipeline 모드(D81 의 gpu-12g): 개발 도구 `tools/neutral-adapter` 가 프로파일의 기반 모델에 맞춰 만든 중립 어댑터(B 행렬 0). 시스템 프롬프트는 학습한 것이 없어 중립 문장이다.
- product 모드: 호출자가 준 학습된 어댑터 폴더 둘. 폴더 형식은 PEFT 어댑터(adapter_config.json, adapter_model.safetensors 또는 adapter_model.bin)와
  학습할 때 쓴 시스템 프롬프트 파일 `system_prompt.txt` 다. 기반 모델은 어댑터가 학습한 모델(adapter_config.json 의 base_model_name_or_path)이고 A·B 가 같아야 한다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .contract import StepFailure
from .sandbox import HF_HOME, REPO, restricted_env
from .script import PIPELINE_SYSTEM_A, PIPELINE_SYSTEM_B

PIPELINE_PROFILE = "gpu-12g"  # D81: 파이프라인 데모용(12GB) 프로파일. 기반 모델은 model-runtime 의 프로파일 표가 정한다
PROMPT_FILE = "system_prompt.txt"
WEIGHT_FILES = ("adapter_model.safetensors", "adapter_model.bin")


@dataclass(frozen=True)
class AdapterSet:
    folder_a: Path
    folder_b: Path
    prompt_a: str
    prompt_b: str
    base_model: str
    description: str


def _read_adapter_folder(folder: Path, label: str) -> tuple[str, str]:
    """(기반 모델, 시스템 프롬프트). 형식이 맞지 않으면 StepFailure."""
    if not folder.is_dir():
        raise StepFailure(f"{label}: 폴더가 아니다: {folder}")
    config_file = folder / "adapter_config.json"
    if not config_file.is_file() or not any((folder / name).is_file() for name in WEIGHT_FILES):
        raise StepFailure(f"{label}: PEFT 어댑터 폴더가 아니다(adapter_config.json 과 {' 또는 '.join(WEIGHT_FILES)} 가 필요하다): {folder}")
    if not (folder / PROMPT_FILE).is_file():
        raise StepFailure(f"{label}: 학습할 때 쓴 시스템 프롬프트 파일 {PROMPT_FILE} 이 없다: {folder}")
    base = json.loads(config_file.read_text(encoding="utf-8")).get("base_model_name_or_path")
    if not isinstance(base, str) or not base:
        raise StepFailure(f"{label}: adapter_config.json 에 base_model_name_or_path 가 없다")
    return base, (folder / PROMPT_FILE).read_text(encoding="utf-8")


def product_adapters(folder_a: Path, folder_b: Path) -> AdapterSet:
    base_a, prompt_a = _read_adapter_folder(folder_a, "--adapters-a")
    base_b, prompt_b = _read_adapter_folder(folder_b, "--adapters-b")
    if base_a != base_b:
        raise StepFailure(f"LoRA-A 의 기반 모델({base_a})과 LoRA-B 의 기반 모델({base_b})이 다르다")
    return AdapterSet(folder_a, folder_b, prompt_a, prompt_b, base_a, "학습된 어댑터(호출자가 준 폴더)")


def pipeline_adapters(stage: Path) -> AdapterSet:
    """중립 어댑터 도구를 실행한다(허브에서는 모델 구성 파일 하나만 받는다)."""
    HF_HOME.mkdir(parents=True, exist_ok=True)
    env = {**restricted_env(), "HF_HOME": str(HF_HOME)}
    result = subprocess.run(
        ["uv", "run", "--project", str(REPO / "tools" / "neutral-adapter"), "neutral-adapter", "--profile", PIPELINE_PROFILE, "--out", str(stage)],
        capture_output=True, text=True, check=False, env=env, cwd=REPO, timeout=900,
    )  # fmt: skip
    if result.returncode != 0:
        raise StepFailure(f"중립 어댑터 도구 실패 rc={result.returncode}: {result.stderr.strip()[-800:]}")
    summary = json.loads(result.stdout.strip().splitlines()[-1])
    digests = ", ".join(f"{role} {info['sha256'][:12]}" for role, info in sorted(summary["adapters"].items()))
    return AdapterSet(
        stage / "lora-a",
        stage / "lora-b",
        PIPELINE_SYSTEM_A,
        PIPELINE_SYSTEM_B,
        summary["base_model"],
        f"중립 어댑터(B=0, rank {summary['adapters']['LORA_A']['rank']}, 내용 해시 {digests})",
    )


def install(adapters: AdapterSet, state: Path) -> None:
    """샌드박스 상태 폴더에 어댑터를 복사한다(엔진과 게시 도구가 같은 경로로 읽는다). 시스템 프롬프트 파일은 어댑터에 넣지 않는다(패키지의 별도 layer 다)."""
    for name, source in (("a", adapters.folder_a), ("b", adapters.folder_b)):
        target = state / "adapters" / name
        shutil.copytree(source, target, ignore=shutil.ignore_patterns(PROMPT_FILE))
        target.chmod(0o755)
        for path in target.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)  # 왜: 엔진(root)과 게시 도구(uid 10001)가 읽는다
