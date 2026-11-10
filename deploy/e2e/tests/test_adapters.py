"""product 모드의 어댑터 폴더 형식 점검."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openit_e2e import adapters
from openit_e2e.contract import StepFailure


def folder(root: Path, name: str, base: str = "Qwen/Qwen3-8B", prompt: bool = True, weights: bool = True) -> Path:
    path = root / name
    path.mkdir()
    (path / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": base, "r": 16}), encoding="utf-8")
    if weights:
        (path / "adapter_model.safetensors").write_bytes(b"w")
    if prompt:
        (path / "system_prompt.txt").write_text("시스템 프롬프트 " + name, encoding="utf-8")
    return path


def test_valid_folders_give_base_model_and_prompts(tmp_path: Path) -> None:
    chosen = adapters.product_adapters(folder(tmp_path, "a"), folder(tmp_path, "b"))
    assert chosen.base_model == "Qwen/Qwen3-8B"
    assert chosen.prompt_a == "시스템 프롬프트 a" and chosen.prompt_b == "시스템 프롬프트 b"


def test_missing_prompt_weights_or_config_is_refused(tmp_path: Path) -> None:
    good = folder(tmp_path, "good")
    with pytest.raises(StepFailure, match=r"system_prompt\.txt"):
        adapters.product_adapters(folder(tmp_path, "noprompt", prompt=False), good)
    with pytest.raises(StepFailure, match="PEFT 어댑터 폴더가 아니다"):
        adapters.product_adapters(good, folder(tmp_path, "noweights", weights=False))
    with pytest.raises(StepFailure, match="폴더가 아니다"):
        adapters.product_adapters(tmp_path / "none", good)


def test_adapters_with_different_base_models_are_refused(tmp_path: Path) -> None:
    with pytest.raises(StepFailure, match="이 다르다"):
        adapters.product_adapters(folder(tmp_path, "a", "Qwen/Qwen3-8B"), folder(tmp_path, "b", "Qwen/Qwen3-4B"))


def test_install_copies_adapters_without_the_prompt_file(tmp_path: Path) -> None:
    state = tmp_path / "state"
    (state / "adapters").mkdir(parents=True)
    chosen = adapters.product_adapters(folder(tmp_path, "a"), folder(tmp_path, "b"))
    adapters.install(chosen, state)
    for name in ("a", "b"):
        assert sorted(path.name for path in (state / "adapters" / name).iterdir()) == ["adapter_config.json", "adapter_model.safetensors"]
