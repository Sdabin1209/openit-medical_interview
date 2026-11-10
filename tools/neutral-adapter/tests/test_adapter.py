"""중립 어댑터 시험: 작은 Qwen3 구성(허브에 접속하지 않는다)으로 어댑터의 모양, 결정성, '기반 모델과 출력이 같다'를 본다."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import torch
from peft import PeftModel
from safetensors import safe_open
from transformers import AutoModelForCausalLM, Qwen3Config

from neutral_adapter import cli
from neutral_adapter.adapter import RANK, SEEDS, build_adapter, folder_digest

BASE = "Qwen/Qwen3-1.7B"
SHORT_MODULES = ["down_proj", "gate_proj", "k_proj", "o_proj", "q_proj", "up_proj", "v_proj"]


@pytest.fixture(scope="module")
def tiny() -> Qwen3Config:
    return Qwen3Config(
        hidden_size=64,
        intermediate_size=128,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=2,
        head_dim=16,
        vocab_size=300,
    )


def tensors(folder: Path) -> dict[str, torch.Tensor]:
    with safe_open(str(folder / "adapter_model.safetensors"), framework="pt") as handle:
        return {key: handle.get_tensor(key) for key in handle.keys()}  # noqa: SIM118 (safetensors 의 핸들은 keys() 만 준다)


def test_config_names_the_base_model_rank_and_all_linear_modules(tiny: Qwen3Config, tmp_path: Path) -> None:
    folder = build_adapter(tiny, BASE, tmp_path / "a", "LORA_A")
    config = json.loads((folder / "adapter_config.json").read_text(encoding="utf-8"))
    assert config["base_model_name_or_path"] == BASE
    assert config["r"] == RANK == 16  # D74(3)
    assert config["peft_type"] == "LORA" and config["task_type"] == "CAUSAL_LM"
    assert config["target_modules"] == SHORT_MODULES  # 모든 선형층(lm_head 제외)
    assert sorted(p.name for p in folder.iterdir()) == ["adapter_config.json", "adapter_model.safetensors"]


def test_every_lora_b_matrix_is_zero_and_a_is_not(tiny: Qwen3Config, tmp_path: Path) -> None:
    weights = tensors(build_adapter(tiny, BASE, tmp_path / "a", "LORA_A"))
    b_keys = [key for key in weights if ".lora_B." in key]
    a_keys = [key for key in weights if ".lora_A." in key]
    assert len(b_keys) == len(a_keys) == 2 * len(SHORT_MODULES)  # 층 2개와 모듈 7개
    assert all(torch.count_nonzero(weights[key]) == 0 for key in b_keys)
    assert all(torch.count_nonzero(weights[key]) > 0 for key in a_keys)
    assert all(weights[key].shape[0] == RANK for key in a_keys)  # A: (r, 입력 차원)
    assert all(weights[key].shape[1] == RANK for key in b_keys)  # B: (출력 차원, r)


def test_same_input_gives_same_bytes_and_roles_differ(tiny: Qwen3Config, tmp_path: Path) -> None:
    first = build_adapter(tiny, BASE, tmp_path / "1", "LORA_A")
    again = build_adapter(tiny, BASE, tmp_path / "2", "LORA_A")
    other = build_adapter(tiny, BASE, tmp_path / "3", "LORA_B")
    assert (first / "adapter_model.safetensors").read_bytes() == (again / "adapter_model.safetensors").read_bytes()
    assert (first / "adapter_config.json").read_bytes() == (again / "adapter_config.json").read_bytes()
    assert folder_digest(first) == folder_digest(again)
    assert folder_digest(first) != folder_digest(other)  # 역할마다 시드가 다르다


def test_bytes_do_not_depend_on_the_process_hash_seed(tiny: Qwen3Config, tmp_path: Path) -> None:
    """같은 입력이면 같은 바이트: 문자열 해시 시드가 다른 두 프로세스가 같은 폴더 해시를 낸다(집합 순서가 저장에 새지 않는다)."""
    config_dir = tmp_path / "config"
    tiny.save_pretrained(str(config_dir))
    digests: set[str] = set()
    for seed in ("1", "2"):
        out = tmp_path / f"out-{seed}"
        env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", ""), "PYTHONHASHSEED": seed}
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "neutral_adapter.cli", "--profile", "gpu-12g", "--out", str(out), "--config-dir", str(config_dir)],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        digests.add(json.dumps({role: info["sha256"] for role, info in json.loads(result.stdout)["adapters"].items()}, sort_keys=True))
    assert len(digests) == 1


def test_adapter_leaves_the_base_models_output_unchanged(tiny: Qwen3Config, tmp_path: Path) -> None:
    """중립의 정의: 같은 기반 모델에 PEFT 로 얹어도 로짓이 같다(B=0 이라 변화가 0)."""
    torch.manual_seed(0)
    base = AutoModelForCausalLM.from_config(tiny).eval()
    ids = torch.tensor([[1, 5, 9, 42, 7, 3]])
    expected = base(ids).logits
    folder = build_adapter(tiny, BASE, tmp_path / "a", "LORA_A")
    adapted = PeftModel.from_pretrained(base, str(folder)).eval()
    assert torch.equal(adapted(ids).logits, expected)


def test_unknown_role_is_refused(tiny: Qwen3Config, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="알 수 없는 역할"):
        build_adapter(tiny, BASE, tmp_path / "x", "LORA_C")


def test_cli_reads_the_profile_table_and_writes_both_adapters(
    tiny: Qwen3Config, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_dir = tmp_path / "config"
    tiny.save_pretrained(str(config_dir))
    assert cli.main(["--profile", "gpu-12g", "--out", str(tmp_path / "out"), "--config-dir", str(config_dir)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["base_model"] == "Qwen/Qwen3-1.7B"  # D81: gpu-12g 의 기반 모델(model-runtime 의 profiles.json)
    assert set(summary["adapters"]) == set(SEEDS)
    for role, name in cli.FOLDER_NAMES.items():
        assert Path(summary["adapters"][role]["path"]) == tmp_path / "out" / name
        assert (tmp_path / "out" / name / "adapter_config.json").is_file()


def test_cli_refuses_an_unknown_profile(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="알 수 없는 프로파일"):
        cli.main(["--profile", "no-such", "--out", str(tmp_path)])
