"""명령: neutral-adapter --profile <프로파일> --out <폴더>. 프로파일의 기반 모델에 맞는 중립 LoRA-A·LoRA-B 어댑터를 만든다.

표준 출력에 JSON 한 줄(기반 모델, 어댑터 폴더와 요약)을 낸다. 같은 입력이면 같은 바이트의 어댑터가 나온다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .adapter import SEEDS, build_adapter, describe, load_model_config

# 왜 이 경로: 프로파일 표(기반 모델)의 정본은 model-runtime 영역의 profiles.json 이다(model-runtime ADR 0007, 계약 9.0.0). 이 도구는 같은 리포 안의 개발 도구라 읽기만 한다
DEFAULT_PROFILES = Path(__file__).resolve().parents[4] / "services" / "model-runtime" / "src" / "model_runtime" / "profiles.json"
FOLDER_NAMES = {"LORA_A": "lora-a", "LORA_B": "lora-b"}


def base_model_of(profile: str, profiles_file: Path) -> str:
    table = json.loads(profiles_file.read_text(encoding="utf-8"))["profiles"]
    if profile not in table:
        raise SystemExit(f"알 수 없는 프로파일 {profile}. 가능: {', '.join(table)}")
    return str(table[profile]["base_model"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="neutral-adapter", description=__doc__)
    parser.add_argument("--profile", required=True, help="프로파일 이름(예: gpu-12g). 기반 모델은 프로파일 표에서 읽는다")
    parser.add_argument("--out", required=True, type=Path, help="어댑터를 만들 폴더(lora-a/, lora-b/ 가 생긴다)")
    parser.add_argument(
        "--profiles-file", type=Path, default=DEFAULT_PROFILES, help="프로파일 표 파일(기본: model-runtime 의 profiles.json)"
    )
    parser.add_argument(
        "--config-dir", type=Path, default=None, help="모델 구성(config.json)이 든 폴더. 없으면 허브에서 config.json 만 받는다"
    )
    args = parser.parse_args(argv)
    base_model = base_model_of(args.profile, args.profiles_file)
    config = load_model_config(base_model, args.config_dir)
    adapters: dict[str, dict[str, object]] = {}
    for role in SEEDS:
        folder = build_adapter(config, base_model, args.out / FOLDER_NAMES[role], role)
        adapters[role] = {"path": str(folder), **describe(folder)}
    print(json.dumps({"profile": args.profile, "base_model": base_model, "adapters": adapters}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
