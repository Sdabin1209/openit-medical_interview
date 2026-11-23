"""package_publish(도구) 진입점: 이미 학습한 어댑터를 평가 집합으로 평가해 보고서를 만들고 모델 패키지로 레지스트리에
올린다.

관리 노드에서 실행하는 명령이다. 추론은 실제 엔진(vLLM 의 OpenAI 호환 서버)이 필요하므로 GPU 에서 돈다.
평가의 위반 판정과 지표 계산은 운영과 같은 `libs/model-io` 를 쓴다(D97). 레지스트리 TLS 신뢰는 사설 루트다(ADR 0013).

사용: package-publish publish ... | package-publish question-bank --reference-db <sqlite> --out <json>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from model_io import (
    ExtractionSample,
    GuardContext,
    ResponseSample,
    build_field_index,
    build_flow_index,
    build_report,
    evaluate_extraction,
    evaluate_responses,
)

from model_runtime.components.inference import call_engine
from model_runtime.components.package_publish import AdapterFiles, build_package, pack_adapter_folder
from model_runtime.components.prompt import extraction_request, response_request
from model_runtime.contract.models import ServingConfig
from model_runtime.link.engine import VllmEngine
from model_runtime.link.publish_registry import OciPackagePublisher, PublishError
from model_runtime.types import EngineError, ExtractionTurn, LoadedAdapter, ServiceFault

# 왜 건너뛰기 분기를 코드에 두나: 문진 참조 DB 에는 건너뛰기 규칙이 조건 문장(questionnaire_rules)으로만 있고, 정본
# labels.py 의
# next_after 가 정한 여섯 규칙이 서빙과 평가의 순서표다(계약 QuestionFlowTable). 문항 세트를 올리는 survey-service 가
# 같은 표를 만든다
_SKIPS: dict[str, tuple[str, Any, str]] = {
    "Q4": ("Q4.answer", False, "Q5"),
    "Q5": ("Q5.answer", False, "Q6"),
    "Q6": ("Q6.answer", False, "Q7"),
    "Q7": ("Q7.does_not_drink", True, "Q8_1"),
    "Q8_1": ("Q8_1.days", 0, "Q9_1"),
    "Q9_1": ("Q9_1.days", 0, "Q10"),
}
# 왜 학습 파일 관측 최대의 2배: 학습 서버 final·finaltest 정답 출력의 최대 길이 A 604자, B 134자(계약 UD 규칙 '관측
# 최대의 2배').
# 글자 수를 토큰 수의 상한으로 본 값이고 토크나이저로 재지 않았다(미확인)
_DEFAULT_MAX_NEW_TOKENS_A = 1208
_DEFAULT_MAX_NEW_TOKENS_B = 268
_DEFAULT_CONCURRENCY = 8  # 왜 8: vLLM 이 요청을 묶어 처리하므로 한 번에 몇 개를 보낸다. 측정으로 정한 값이 아니다
_EXTRACT_LIMIT = 20  # 계약 D125 추출 상한(초)
_RESPOND_LIMIT = 25  # 계약 D125 응답 상한(초)


def question_bank_from_reference_db(db_path: Path) -> dict[str, Any]:
    """문진 참조 DB(데이터셋 db/questionnaire_reference.sqlite3)에서 순서표와 칸 규격(계약 모양)을 만든다."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        items = [row[0] for row in conn.execute("SELECT item_id FROM question_items ORDER BY sequence_no")]
        rules: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            following = items[index + 1] if index + 1 < len(items) else "END"
            branches: list[dict[str, Any]] = []
            if item in _SKIPS:
                slot, value, target = _SKIPS[item]
                branches.append({"when": {"slot": slot, "operator": "EQ", "value": value}, "next_item": target})
            branches.append({"next_item": following})
            rules.append({"item_id": item, "branches": branches})
        options: dict[str, list[dict[str, str]]] = {}
        for field_id, code, label in conn.execute("SELECT field_id, option_code, label FROM field_options"):
            options.setdefault(field_id, []).append({"option_code": code, "label": label})
        fields: list[dict[str, Any]] = []
        query = (
            "SELECT field_id, item_id, field_name, data_type, unit, constraints_json, repeat_keys_json "
            "FROM question_fields"
        )
        for field_id, item, name, data_type, unit, constraints, repeat in conn.execute(query):
            spec: dict[str, Any] = {"item_id": item, "field_name": name, "data_type": data_type}
            if unit:
                spec["unit"] = unit
            spec.update(json.loads(constraints))
            # 왜 빈 키를 뺀다: 계약 RepeatKey 는 소문자 글자만 받는다. 술 종류를 모르는 값(빈 키)은 검증기가 저장하지
            # 않는 값에만 허용한다
            keys = [key for key in json.loads(repeat) if key]
            if keys:
                spec["repeat_keys"] = keys
            if field_id in options:
                spec["options"] = options[field_id]
            fields.append(spec)
    finally:
        conn.close()
    return {"flow": {"start_item": items[0], "rules": rules}, "fields": fields}


def read_rows(path: Path, limit: int | None) -> list[tuple[dict[str, Any], str]]:
    """학습 형식(messages)의 JSON Lines 평가 집합에서 (모델 입력 값, 정답 글자) 쌍을 읽는다."""
    rows: list[tuple[dict[str, Any], str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        messages = json.loads(line)["messages"]
        rows.append((json.loads(messages[1]["content"]), messages[2]["content"]))
        if limit is not None and len(rows) >= limit:
            break
    return rows


async def evaluate(
    engine: VllmEngine,
    adapter_a: LoadedAdapter,
    adapter_b: LoadedAdapter,
    bank: dict[str, Any],
    rows_a: Sequence[tuple[dict[str, Any], str]],
    rows_b: Sequence[tuple[dict[str, Any], str]],
    concurrency: int,
    model_io_version: str = "model-io-v2",
) -> list[dict[str, object]]:
    """평가 집합을 엔진으로 추론해 계약 필수 지표를 센다. 호출이 실패한 표본은 출력 없음으로 센다."""
    gate = asyncio.Semaphore(concurrency)
    flow, fields = build_flow_index(bank["flow"]), build_field_index(bank["fields"])

    async def one_a(payload: dict[str, Any], gold: str) -> ExtractionSample:
        turn = ExtractionTurn(payload, list(payload["state"]))
        async with gate:
            try:
                raw, seconds = await call_engine(
                    engine, extraction_request(turn, adapter_a, model_io_version), _EXTRACT_LIMIT
                )
            except ServiceFault:
                raw, seconds = None, float(_EXTRACT_LIMIT)
        context = GuardContext(
            payload["question_id"], flow, fields, payload["state"], model_io_version=model_io_version
        )
        return ExtractionSample(context, json.loads(gold), raw, seconds)

    async def one_b(payload: dict[str, Any], _gold: str) -> ResponseSample:
        async with gate:
            try:
                text, seconds = await call_engine(engine, response_request(payload, adapter_b), _RESPOND_LIMIT)
            except ServiceFault:
                text, seconds = None, float(_RESPOND_LIMIT)
        return ResponseSample(payload, text, seconds)

    samples_a = await asyncio.gather(*(one_a(*row) for row in rows_a))
    samples_b = await asyncio.gather(*(one_b(*row) for row in rows_b))
    constrained = adapter_a.serving.constrained_decoding.root
    return [*evaluate_extraction(samples_a, constrained), *evaluate_responses(samples_b)]


def _serving(max_new_tokens: int, temperature: float, constrained: bool) -> dict[str, Any]:
    return {"max_new_tokens": max_new_tokens, "temperature": temperature, "constrained_decoding": constrained}


async def run_publish(args: argparse.Namespace) -> str:
    """평가하고 패키지를 만들어 올린 뒤 매니페스트 digest 를 돌려준다."""
    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    bank = json.loads(Path(args.question_bank).read_text(encoding="utf-8"))
    serving_a = _serving(args.max_new_tokens_a, args.temperature, args.constrained_decoding)
    serving_b = _serving(args.max_new_tokens_b, args.temperature, False)
    prompts = {"LORA_A": Path(args.system_prompt_a), "LORA_B": Path(args.system_prompt_b)}
    folders = {"LORA_A": Path(args.adapter_a), "LORA_B": Path(args.adapter_b)}
    tag = uuid.uuid4().hex[:8]
    engine = VllmEngine(args.engine_url, args.base_model)
    names = {role: f"publish-{role.lower()}-{tag}" for role in folders}
    try:
        for role, folder in folders.items():
            await engine.load_adapter(names[role], folder.resolve())
        adapter_a = LoadedAdapter(
            names["LORA_A"], prompts["LORA_A"].read_text(encoding="utf-8"), ServingConfig.model_validate(serving_a)
        )
        adapter_b = LoadedAdapter(
            names["LORA_B"], prompts["LORA_B"].read_text(encoding="utf-8"), ServingConfig.model_validate(serving_b)
        )
        metrics = await evaluate(
            engine,
            adapter_a,
            adapter_b,
            bank,
            read_rows(Path(args.eval_a), args.limit),
            read_rows(Path(args.eval_b), args.limit),
            args.concurrency,
            args.model_io_version,
        )
    finally:
        for name in names.values():
            await engine.unload_adapter(name)
    now = datetime.now(UTC)
    report = build_report(args.dataset_version_id, now, metrics)
    evaluation = report.model_dump(mode="json", exclude_none=True)
    if args.report_out:
        Path(args.report_out).write_text(json.dumps(evaluation, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    adapters: dict[str, AdapterFiles] = {}
    for role, folder in folders.items():
        archive = work / f"{role}.tar"
        pack_adapter_folder(folder, archive)
        adapters[role] = AdapterFiles(archive, prompts[role], serving_a if role == "LORA_A" else serving_b)
    package = build_package(
        adapters=adapters,
        base_model=args.base_model,
        runtime_contract_version=args.runtime_contract_version,
        model_io_version=args.model_io_version,
        model_runtime_version=version("openit-model_runtime"),
        dataset_version_id=args.dataset_version_id,
        training_run_ids=[args.training_run_a, args.training_run_b],
        evaluation=evaluation,
        created_at=now.isoformat(),
        workdir=work / "package",
    )
    user, _, password = Path(args.credentials_file).read_text(encoding="utf-8").strip().partition(":")
    publisher = OciPackagePublisher(
        args.registry_url,
        args.repository,
        (user, password),
        Path(args.root_certificate_file) if args.root_certificate_file else None,
    )
    try:
        return await asyncio.to_thread(publisher.publish, package)
    finally:
        publisher.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="package-publish", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    bank = sub.add_parser("question-bank", help="문진 참조 DB 에서 순서표와 칸 규격 JSON 을 만든다")
    bank.add_argument("--reference-db", required=True)
    bank.add_argument("--out", required=True)
    pub = sub.add_parser("publish", help="평가하고 모델 패키지로 레지스트리에 올린다")
    for name in ("adapter-a", "adapter-b", "system-prompt-a", "system-prompt-b", "question-bank", "eval-a", "eval-b"):
        pub.add_argument(f"--{name}", required=True)
    for name in ("engine-url", "registry-url", "repository", "credentials-file", "base-model", "dataset-version-id"):
        pub.add_argument(f"--{name}", required=True)
    pub.add_argument("--training-run-a", required=True)
    pub.add_argument("--training-run-b", required=True)
    pub.add_argument("--runtime-contract-version", type=int, required=True)
    pub.add_argument("--root-certificate-file", default=None)
    pub.add_argument("--workdir", required=True)
    pub.add_argument("--report-out", default=None)
    pub.add_argument("--max-new-tokens-a", type=int, default=_DEFAULT_MAX_NEW_TOKENS_A)
    pub.add_argument("--max-new-tokens-b", type=int, default=_DEFAULT_MAX_NEW_TOKENS_B)
    pub.add_argument("--temperature", type=float, default=0.0)
    pub.add_argument("--constrained-decoding", action="store_true")
    pub.add_argument("--concurrency", type=int, default=_DEFAULT_CONCURRENCY)
    # 왜 기본 v2: 이 인자가 생기기 전의 호출자(E2E pipeline, 운영 안내서)는 v2 어댑터만 올렸다.
    # v3 어댑터(1118)는 반드시 밝힌다
    pub.add_argument("--model-io-version", choices=["model-io-v2", "model-io-v3"], default="model-io-v2")
    pub.add_argument(
        "--limit", type=int, default=None, help="평가 집합의 앞 N 행만 쓴다(점검용. 보고서의 표본 수에 그대로 드러난다)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """명령 진입점. 성공하면 표준 출력 마지막 줄에 패키지 digest 를 낸다. 실패하면 0 이 아닌 값."""
    args = _parser().parse_args(argv)
    if args.command == "question-bank":
        Path(args.out).write_text(
            json.dumps(question_bank_from_reference_db(Path(args.reference_db)), ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        return 0
    try:
        digest = asyncio.run(run_publish(args))
    except (PublishError, EngineError, ValueError, OSError) as error:
        print(f"게시 실패: {error}", file=sys.stderr)
        return 1
    print(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
