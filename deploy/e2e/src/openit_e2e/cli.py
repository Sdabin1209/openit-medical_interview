"""명령: openit-e2e --mode pipeline | --mode product --adapters-a <폴더> --adapters-b <폴더> --profile <프로파일>. `./deploy e2e` 가 부른다.

종료 코드: 0 모든 단계 통과, 1 실패, 2 사용법 오류.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from . import adapters as adapter_module
from . import questionnaire, report
from .contract import Contract, StepFailure
from .ingress import Ingress
from .sandbox import REPO, WORK_ROOT, Sandbox, image_name
from .scenario import Context, run

RESULTS_FILE = REPO / "deploy" / "docs" / "E2E_RESULTS.md"
SQL_MD = REPO / "contracts" / "inputs" / "SQL.md"
# 왜 gpu-12g 만 크기 인자: 이 GPU(12GB, 화면 출력이 1.5GB 를 쓰고 있다)에서 vLLM 기본값(메모리 90%, 모델 최대 길이 40960)은 시작하지 못한다. 값은 첫 시도값이고
# 측정으로 정하지 않았다(ADR 0025). rtx4090-24g 는 기본값을 쓴다(이 환경에서 확인하지 못했다)
ENGINE_ARGS: dict[str, list[str]] = {"gpu-12g": ["--gpu-memory-utilization", "0.7", "--max-model-len", "8192"]}


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="openit-e2e", description=__doc__)
    parser.add_argument("--mode", required=True, choices=["pipeline", "product"])
    parser.add_argument("--adapters-a", type=Path, help="product: LoRA-A 어댑터 폴더(PEFT 어댑터와 system_prompt.txt)")
    parser.add_argument("--adapters-b", type=Path, help="product: LoRA-B 어댑터 폴더")
    parser.add_argument("--profile", help="product: 모델 프로파일(예: rtx4090-24g). pipeline 은 gpu-12g 로 정해져 있다")
    parser.add_argument("--note", default="", help="기록에 남길 한 줄 비고")
    args = parser.parse_args(argv)
    if args.mode == "pipeline":
        if args.adapters_a or args.adapters_b or (args.profile and args.profile != adapter_module.PIPELINE_PROFILE):
            parser.error(f"pipeline 모드는 어댑터 폴더를 받지 않고 프로파일은 {adapter_module.PIPELINE_PROFILE} 로 정해져 있다")
        args.profile = adapter_module.PIPELINE_PROFILE
    elif not (args.adapters_a and args.adapters_b and args.profile):
        parser.error("product 모드는 --adapters-a, --adapters-b, --profile 이 모두 필요하다")
    return args


def _capture(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def environment(sandbox: Sandbox, mode: str, cache: str, description: str) -> dict[str, str]:
    gpu = _capture(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]).replace("\n", " / ")
    server = sandbox.docker(["version", "--format", "{{.Server.Version}}"], check=False).stdout.strip()
    revisions: dict[str, str] = {}
    for folder in ("services/survey-service", "services/model-runtime", "web/admin-console", "web/kiosk-frontend"):
        name = image_name(REPO / folder)
        label = sandbox.docker(
            ["image", "inspect", "--format", '{{ index .Config.Labels "org.opencontainers.image.revision" }}', f"{name}:local"], check=False
        ).stdout.strip()
        revisions[name.removeprefix("openit/")] = label[:12]
    return {
        "GPU": gpu or "(nvidia-smi 가 읽지 못했다)",
        "프로파일·기반 모델": f"{sandbox.profile} · {sandbox.base_model}",
        "추론 엔진": f"{sandbox.vllm_image()} (크기 인자: {' '.join(sandbox.engine_args) or '제품 기본값'})",
        "어댑터": description,
        "기반 모델 가중치 볼륨": cache,
        "Docker 엔진": server,
        "영역 이미지 리비전": ", ".join(f"{name} {rev}" for name, rev in revisions.items()),
        "리포 리비전": _capture(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"]),
        "compose 프로젝트": sandbox.project,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse(argv)
    started_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    began = time.monotonic()
    stage = WORK_ROOT / f"adapters-{int(began)}"
    sandbox: Sandbox | None = None
    steps: list[report.StepResult] = []
    env_info: dict[str, str] = {}
    failure = ""
    leftovers: list[str] = []
    try:
        print("[준비] 어댑터와 문항 세트")
        adapters = (
            adapter_module.pipeline_adapters(stage)
            if args.mode == "pipeline"
            else adapter_module.product_adapters(args.adapters_a, args.adapters_b)
        )
        bank = questionnaire.load(SQL_MD)
        contract = Contract(REPO / "contracts")
        sandbox = Sandbox(args.profile, adapters.base_model, ENGINE_ARGS.get(args.profile, []))
        problems = sandbox.preflight()
        if problems:
            raise StepFailure("시작 조건을 만족하지 않는다:\n  " + "\n  ".join(problems))
        print(f"[1/6] 샌드박스 사본 만들기: {sandbox.project}")
        sandbox.prepare()
        adapter_module.install(adapters, sandbox.state)
        print(f"[2/6] 기반 모델 가중치 확인({adapters.base_model}). 없으면 허브에서 받는다")
        cache = sandbox.ensure_model_cache()
        print(f"      볼륨 {cache}")
        print("[3/6] ./deploy bootstrap(신뢰의 뿌리, 레지스트리, 이미지 올리기, 기동). 몇 분 걸린다")
        sandbox.run_deploy("bootstrap", log="bootstrap.log")
        sandbox.create_users()
        print("[4/6] 추론 엔진 기동과 model-runtime 준비")
        sandbox.start_engine()
        sandbox.wait_model_runtime_ready()
        env_info = environment(sandbox, args.mode, cache, adapters.description)
        print("[5/6] 시나리오")
        ingress = Ingress(sandbox.published_port("ingress-acme", 8443), sandbox.deploy_dir / "pki" / "trust-bundle.pem")
        context = Context(sandbox, ingress, contract, bank, args.mode, adapters.base_model, (adapters.prompt_a, adapters.prompt_b))
        try:
            steps = run(context, lambda line: print(f"      {line}"))
        finally:
            for client in context.clients.values():
                client.close()
    except (StepFailure, httpx.HTTPError, OSError, subprocess.SubprocessError) as error:
        failure = f"{type(error).__name__}: {error}"[:1500]
    finally:
        if sandbox is not None:
            failed = bool(failure) or any(step.status != "통과" for step in steps)
            if failed:
                print(
                    f"[진단] 실패했다. 로그와 상태를 먼저 남긴다: {sandbox.save_diagnostics() if sandbox.deploy_dir.is_dir() else '(사본이 없다)'}"
                )
            print("[6/6] 정리: 이 프로젝트만 down -v")
            leftovers = sandbox.teardown()
        shutil.rmtree(stage, ignore_errors=True)
    if failure:
        steps = [*steps, report.StepResult("준비·설치", "실패", detail=failure)]
    passed = bool(steps) and all(step.status == "통과" for step in steps) and not leftovers and not failure
    if sandbox is not None and not env_info:
        env_info = {"compose 프로젝트": sandbox.project, "프로파일·기반 모델": f"{sandbox.profile} · {sandbox.base_model}"}
    record = report.RunRecord(
        started_at, args.mode, "통과" if passed else "실패", env_info, steps, leftovers, time.monotonic() - began, args.note
    )
    report.update(RESULTS_FILE, record)
    print(report.render(record))
    print(f"기록: {RESULTS_FILE.relative_to(REPO)}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
