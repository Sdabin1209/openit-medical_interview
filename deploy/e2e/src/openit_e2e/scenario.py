"""시나리오: 한 건의 문진을 입구(Envoy)를 지나는 실제 HTTP 로 끝까지(ADR 0025).

① 어댑터 게시(package-publish) ② 승인자가 패키지 조회·활성화·적재 대기 ③ 문항 세트 올리기·활성화 ④ 시작 코드 발급
⑤ 키오스크 세션(시작, 턴 여러 번, 종료) ⑥ 의사가 결과 조회·확인 표시 ⑦ 병원 시스템이 결과·FHIR 로 당겨 감 ⑧ 직원 호출 알림.

모든 호출은 계약 검증을 거친다(contract.Contract.call): 상태 코드가 계약에 있고 기대한 것인지, 응답이 그 상태의 스키마를 지키는지.
pipeline 모드는 계약대로 응답하는지와 실패 처리를 본다: 출력 불가 -> 실패 신호(저장된 답·지금 문항 불변), 연속 실패가 TurnFailureLimit(계약 9.3.0)에 닿는 턴 -> 실패 신호 없이 그 문항을 건너뛴
결과(빈칸 원인 FAILURE_LIMIT, FHIR data-absent-reason error), 같은 turn_id 의 재전송은 연속 실패 수를 올리지 않는다. product 모드는 학습된 어댑터로 같은 시스템 규칙을 본다.
이 시험은 프레임워크 시험이다(2026-11-23 결정): 모델이 낸 결과(실패 신호, 확인·되묻기 반복, 문진 미완료, 대본 기대 값과 다른 저장)는 '모델 관찰'로 기록하고
단계를 실패시키지 않는다. 시스템이 계약대로 처리했는지(호출·상태·실패 처리 규칙·결과·FHIR·알림)만 합격 기준이다.
성공을 바라고 실패한 호출을 다시 시도하지 않는다(재전송 시험은 계약 규칙을 보려는 한 번의 의도된 호출이다). 기다림은 상태를 보는 것(적재 상태 조회)뿐이고 상한 안에서만 한다.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import script
from .contract import Contract, StepFailure
from .ingress import Ingress
from .questionnaire import QUESTIONNAIRE_ID, RUNTIME_CONTRACT_VERSION, Questionnaire
from .report import StepResult
from .sandbox import ADAPTERS_IN_CONTAINER, DEVICE_ID, HOSPITAL, INPUTS_IN_CONTAINER, OUT_IN_CONTAINER, Sandbox
from .sse import StreamOutcome, read_stream

DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
# 왜 계약에서 읽나: 모델 적재 완료의 상한은 계약 9.1.0 의 TimeBudgetTable.model_load(ModelLoadLimitSeconds)다. 복사하지 않는다
LOAD_LIMIT_SCHEMA = "ModelLoadLimitSeconds"
POLL_INTERVAL = 2  # 계약 SessionStatePollSeconds(2초)와 같은 간격으로 상태를 본다
# 왜 6: 어댑터가 학습되지 않아 문진이 끝까지 가지 않으므로 상한을 둔다(대본의 앞 문항들). 연속 실패 한도(TurnFailureLimit, 계약 9.3.0)가 3 이므로
# 건너뛰기가 두 번 일어나 '건너뛴 뒤 수가 0 으로 돌아가 같은 모양이 되풀이됨'까지 본다. 한도는 계약에서 읽고(session), 이 수가 한도의 두 배보다 작으면 단계가 실패한다
PIPELINE_TURNS = 6
FAILURE_LIMIT_SCHEMA = "TurnFailureLimit"
BLANK_REASON = "FAILURE_LIMIT"  # 계약 BlankReason
FHIR_ABSENT_ERROR = "error"  # 계약 FhirAbsentReason: FAILURE_LIMIT 칸의 FHIR 빈칸 사유(FhirMapping.absent_map)
PRODUCT_TURN_GUARD = len(script.SCRIPT) + 5  # product 모드: 순서표가 대본보다 길게 이어지면 멈춘다(대본에 없는 문항에서 막힌다)
# 왜 3: 대본은 문항마다 발화가 하나라, 모델이 확인·되묻기로 같은 문항을 되돌리면 같은 발화가 되풀이된다. 같은 문항에 세 번째로 보내는 턴은 이미 같은 입력을
# 두 번 본 뒤라 새로 알 것이 없다. 그때 세션을 끝내 GPU 시간을 아끼고 뒤 단계(결과·FHIR·알림)를 본다(측정값이 아니라 대본의 성질에서 나온 값)
PRODUCT_REPEAT_LIMIT = 3
SUBJECT = "e2e-subject-001"
SUBJECT_CALL = "e2e-subject-002"
# 학습 데이터 이름 자리에 쓰는 고정 UUID(RFC 9562 의 이름 기반 v5). 어댑터를 평가한 데이터셋·학습 실행의 식별자가 필요한 게시 인자이고 이 시험에는 실제 대응이 없다
NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


@dataclass
class Context:
    sandbox: Sandbox
    ingress: Ingress
    contract: Contract
    questionnaire: Questionnaire
    mode: str
    base_model: str
    system_prompts: tuple[str, str]
    clients: dict[str, httpx.Client] = field(default_factory=lambda: dict[str, httpx.Client]())
    package_digest: str = ""
    start_code: str = ""
    session_id: str = ""
    turn_failures: int = 0
    turn_successes: int = 0
    turn_skips: int = 0
    skipped: list[tuple[str, str | None]] = field(default_factory=lambda: list[tuple[str, str | None]]())  # (건너뛴 문항, 다음 문항)
    last_status: str = ""
    streams: list[StreamOutcome] = field(default_factory=lambda: list[StreamOutcome]())
    result: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())
    model_notes: list[str] = field(default_factory=lambda: list[str]())  # 모델 관찰(판정 밖, product)
    model_io_version: str = "model-io-v2"  # 게시할 패키지의 모델 입출력 버전(계약 9.4.0)

    def human(self, user: str) -> httpx.Client:
        if user not in self.clients:
            self.clients[user] = self.ingress.login(user, self.sandbox.password)
        return self.clients[user]

    def kiosk(self) -> httpx.Client:
        if "kiosk" not in self.clients:
            if self.sandbox.device_files is None:
                raise StepFailure("기기 인증서가 준비되지 않았다")
            self.clients["kiosk"] = self.ingress.client(device=self.sandbox.device_files)
        return self.clients["kiosk"]

    def hospital(self) -> httpx.Client:
        if "hospital" not in self.clients:
            self.clients["hospital"] = self.ingress.machine_client(HOSPITAL, self.sandbox.machine_secret(HOSPITAL))
        return self.clients["hospital"]

    def call(self, client: httpx.Client, service: str, operation: str, **kwargs: Any) -> Any:
        return self.contract.call(client, service, operation, **kwargs)


# 단계 함수: (맥락, 확인한 것 목록, 발견 목록). 발견은 계약을 어겼지만 뒤 단계를 막지 않는 것이다(E2E 한 번이 수십 분이라 한 번에 가능한 만큼 본다). 막는 실패는 StepFailure 를 던진다
Step = Callable[[Context, list[str], list[str]], None]


# ---------------------------------------------------------------- ① 게시
def publish(ctx: Context, checks: list[str], findings: list[str]) -> None:
    sandbox = ctx.sandbox
    inputs = sandbox.state / "inputs"
    (inputs / "bank.json").write_text(json.dumps(ctx.questionnaire.bank(), ensure_ascii=False), encoding="utf-8")
    (inputs / "prompt-a.txt").write_text(ctx.system_prompts[0], encoding="utf-8")
    (inputs / "prompt-b.txt").write_text(ctx.system_prompts[1], encoding="utf-8")
    eval_a, eval_b = script.evaluation_rows(ctx.questionnaire, *ctx.system_prompts)
    (inputs / "eval-a.jsonl").write_text(eval_a, encoding="utf-8")
    (inputs / "eval-b.jsonl").write_text(eval_b, encoding="utf-8")
    arguments = [
        "publish",
        "--adapter-a", f"{ADAPTERS_IN_CONTAINER}/a", "--adapter-b", f"{ADAPTERS_IN_CONTAINER}/b",
        "--system-prompt-a", f"{INPUTS_IN_CONTAINER}/prompt-a.txt", "--system-prompt-b", f"{INPUTS_IN_CONTAINER}/prompt-b.txt",
        "--question-bank", f"{INPUTS_IN_CONTAINER}/bank.json",
        "--eval-a", f"{INPUTS_IN_CONTAINER}/eval-a.jsonl", "--eval-b", f"{INPUTS_IN_CONTAINER}/eval-b.jsonl",
        "--engine-url", "http://inference-engine:8000",
        "--registry-url", "https://registry", "--repository", sandbox.install_value("OPENIT_MODEL_REGISTRY_REPOSITORY"),
        "--credentials-file", "/run/secrets/registry_credentials", "--root-certificate-file", "/etc/openit/trust-list.pem",
        "--base-model", ctx.base_model,
        "--dataset-version-id", str(uuid.uuid5(NAMESPACE, "openit-e2e-dataset")),
        "--training-run-a", str(uuid.uuid5(NAMESPACE, "openit-e2e-run-a")), "--training-run-b", str(uuid.uuid5(NAMESPACE, "openit-e2e-run-b")),
        "--runtime-contract-version", str(RUNTIME_CONTRACT_VERSION),
        "--model-io-version", ctx.model_io_version,
        "--workdir", "/work", "--report-out", f"{OUT_IN_CONTAINER}/report.json",
        # 왜 pipeline 만 제약 디코딩: 학습하지 않은 기반 모델의 추출 출력도 계약 스키마(ActionExtraction)를 따르게 해 엔진의 response_format(json_schema) 경로까지 지나가게 한다.
        # product 는 학습된 어댑터가 낸 출력을 그대로 본다(게시 도구의 기본값)
        *(["--constrained-decoding"] if ctx.mode == "pipeline" else []),
    ]  # fmt: skip
    result = sandbox.publish(arguments)
    if result.returncode != 0:
        raise StepFailure(f"package-publish rc={result.returncode}: {(result.stderr or result.stdout).strip()[-1200:]}")
    digest = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if not DIGEST.fullmatch(digest):
        raise StepFailure(f"package-publish 의 마지막 줄이 패키지 digest 가 아니다: {digest[:80]!r}")
    ctx.package_digest = digest
    report = json.loads((sandbox.state / "out" / "report.json").read_text(encoding="utf-8"))
    checks.append(f"패키지 digest {digest[:19]}…가 레지스트리에 올라감")
    counts: dict[str, int] = {}
    for metric in report["metrics"]:
        counts[metric["name"]] = counts.get(metric["name"], 0) + 1
    checks.append(
        "평가 보고서 지표 "
        + ", ".join(f"{name} {count}개" if count > 1 else name for name, count in counts.items())
        + f"(총 {len(report['metrics'])}개, 점검용 작은 평가 집합)"
    )


# ---------------------------------------------------------------- ② 활성화
def activate(ctx: Context, checks: list[str], findings: list[str]) -> None:
    approver = ctx.human("approver-e2e")
    manifest = ctx.call(approver, "model-runtime", "getModelPackage", expect=(200,), path={"package_digest": ctx.package_digest}).body
    if manifest["base_model"] != ctx.base_model:
        raise StepFailure(f"패키지의 기반 모델 {manifest['base_model']} 이 프로파일의 {ctx.base_model} 과 다르다")
    roles = sorted(entry["role"] for entry in manifest["adapters"])
    if roles != ["LORA_A", "LORA_B"] or manifest["runtime_contract_version"] != RUNTIME_CONTRACT_VERSION:
        raise StepFailure(f"패키지 목록표가 기대와 다르다: 역할 {roles}, 문항 은행 버전 {manifest['runtime_contract_version']}")
    if manifest["model_io_version"] != ctx.model_io_version:
        raise StepFailure(f"패키지의 모델 입출력 {manifest['model_io_version']} 이 게시한 {ctx.model_io_version} 과 다르다")
    checks.append(
        f"getModelPackage 200(기반 모델 {manifest['base_model']}, 어댑터 {len(roles)}개, 모델 입출력 {manifest['model_io_version']})"
    )
    listing = ctx.call(approver, "model-runtime", "listModelPackages", expect=(200,)).body
    if ctx.package_digest in {item["package_digest"] for item in listing["items"]}:
        checks.append("listModelPackages 에 게시한 패키지가 있다")
    else:
        findings.append(
            f"listModelPackages 가 방금 게시한 패키지를 주지 않았다(목록 {len(listing['items'])}개). getModelPackage 는 같은 digest 를 준다"
        )
    accepted = ctx.call(
        approver,
        "model-runtime",
        "activateModelPackage",
        expect=(200, 202),
        body={"package_digest": ctx.package_digest, "reason": "E2E: 게시한 패키지의 적재·추론 경로 확인"},
    )
    checks.append(f"activateModelPackage {accepted.status}")
    load_limit = ctx.contract.integer_constant(LOAD_LIMIT_SCHEMA)
    deadline = time.monotonic() + load_limit
    status: dict[str, Any] = accepted.body
    while status["state"] != "READY":
        if status["state"] == "FAILED":
            raise StepFailure(f"적재가 실패했다(FAILED): {json.dumps(status, ensure_ascii=False)[:300]}")
        if time.monotonic() > deadline:
            raise StepFailure(f"{load_limit}초 안에 READY 가 되지 않았다(마지막 상태 {status['state']})")
        time.sleep(POLL_INTERVAL)
        status = ctx.call(approver, "model-runtime", "getModelStatus", expect=(200,)).body
    if status.get("package_digest") != ctx.package_digest or status.get("runtime_contract_version") != RUNTIME_CONTRACT_VERSION:
        raise StepFailure(f"READY 인데 활성 패키지·문항 은행 버전이 기대와 다르다: {json.dumps(status, ensure_ascii=False)[:300]}")
    checks.append(f"getModelStatus READY(계약 적재 상한 {load_limit}초 안), 활성 패키지가 게시한 것이다")


# ---------------------------------------------------------------- ③ 문항 세트
def question_set(ctx: Context, checks: list[str], findings: list[str]) -> None:
    author = ctx.human("author-e2e")
    uploaded = ctx.call(author, "survey-service", "uploadQuestionSet", expect=(201,), body=ctx.questionnaire.upload(), idempotent=True).body
    if uploaded["is_active"] or uploaded["runtime_contract_version"] != RUNTIME_CONTRACT_VERSION:
        raise StepFailure("올린 직후 버전은 비활성이고 문항 은행 버전이 올린 값이어야 한다")
    checks.append(
        f"uploadQuestionSet 201(문항 {len(ctx.questionnaire.items)}개, 칸 {len(ctx.questionnaire.fields)}개, 버전 {uploaded['version_number']})"
    )
    active = ctx.call(
        author,
        "survey-service",
        "activateQuestionSet",
        expect=(200,),
        path={"question_set_version_id": uploaded["question_set_version_id"]},
    ).body
    if active["questionnaire_id"] != QUESTIONNAIRE_ID or active["question_set_version_id"] != uploaded["question_set_version_id"]:
        raise StepFailure("활성화 응답이 올린 버전이 아니다")
    listed = ctx.call(ctx.human("staff-e2e"), "survey-service", "listActiveQuestionnaires", expect=(200,)).body
    if QUESTIONNAIRE_ID not in {item["questionnaire_id"] for item in listed["questionnaires"]}:
        raise StepFailure("활성 문진표 목록에 올린 문진표가 없다")
    checks.append("activateQuestionSet 200, listActiveQuestionnaires 에 문진표가 있다")


# ---------------------------------------------------------------- ④ 시작 코드
def start_code(ctx: Context, checks: list[str], findings: list[str]) -> None:
    issued = ctx.call(
        ctx.human("staff-e2e"),
        "survey-service",
        "issueStartCode",
        expect=(201,),
        body={"subject_ref": SUBJECT, "questionnaire_id": QUESTIONNAIRE_ID},
        idempotent=True,
    ).body
    ctx.start_code = issued["code"]
    checks.append("issueStartCode 201(6자리 코드, 만료 시각 있음)")


# ---------------------------------------------------------------- ⑤ 세션
@dataclass
class TurnLedger:
    """연속 실패 수의 기대치. 서비스가 세는 방식(계약 TurnFailureLimit)을 이 시험이 따로 세어 서비스의 응답과 맞춘다."""

    limit: int
    streak: int = 0


def _check_skip(ctx: Context, previous_item: str | None, reply: dict[str, Any], ledger: TurnLedger) -> None:
    """한도에 닿은 턴: 실패 신호 없이 문장과 다음 자리를 준다(계약 필드만 본다. 고정 문장의 글은 계약이 정하지 않아 비교하지 않는다)."""
    sentence = reply.get("response_text")
    if not isinstance(sentence, str) or not sentence.strip():
        raise StepFailure(
            f"연속 실패 {ledger.limit}번째 턴인데 response_text 가 없거나 비어 있다(건너뛴 결과는 안내 문장과 다음 질문을 준다)"
        )
    if errors := ctx.contract.schema_errors(ctx.contract.named("ResponseSentence"), sentence):
        raise StepFailure(f"건너뛴 턴의 response_text 가 ResponseSentence 를 어겼다: {errors}")
    next_item = reply.get("current_item_id")
    if reply["status"] == "ACTIVE":
        if next_item is None or next_item == previous_item:
            raise StepFailure(f"연속 실패 {ledger.limit}번째 턴이 문항 {previous_item} 을 건너뛰어야 하는데 지금 문항이 {next_item} 이다")
    elif reply["status"] != "ENDED_COMPLETE" or next_item is not None:
        raise StepFailure(f"건너뛴 턴 뒤 세션 상태가 ACTIVE 도 ENDED_COMPLETE(끝)도 아니다: {reply['status']}, 지금 문항 {next_item}")
    ctx.skipped.append((previous_item or "?", next_item))


def _check_turn(
    ctx: Context,
    previous_item: str | None,
    reply: dict[str, Any],
    turn_checks: dict[str, int],
    ledger: TurnLedger,
    *,
    resend: bool = False,
) -> None:
    """한 턴의 응답 판정: 계약 검증은 호출이 했다.

    실패 신호이면 저장된 답과 지금 문항이 바뀌지 않았는지 본다(D75, 9.3.0 에서 연속 실패 수만 예외). 연속 실패 수가 한도에 닿는 턴은 실패 신호를 내면 안 되고
    건너뛴 결과를 줘야 한다. 같은 turn_id 의 재전송(resend)은 실패 신호가 다시 와야 하고 수를 올리지 않는다.
    """
    if "failure_signal" not in reply:
        if resend:
            raise StepFailure("실패한 turn_id 의 재전송이 실패 신호 없이 끝났다(모델이 바뀐 것이 아니면 같은 실패여야 한다)")
        if ledger.streak == ledger.limit - 1 and ledger.streak > 0:
            _check_skip(ctx, previous_item, reply, ledger)
            ctx.turn_skips += 1
        else:
            ctx.turn_successes += 1
        ledger.streak = 0
        return
    if not resend and ledger.streak + 1 >= ledger.limit:
        raise StepFailure(
            f"연속 {ledger.limit}번째 실패인데 실패 신호({reply['failure_signal']})를 냈다(문항 {previous_item}). 한도에 닿으면 그 문항을 건너뛴 결과여야 한다"
        )
    ctx.turn_failures += 1
    if reply["status"] != "ACTIVE":
        raise StepFailure(f"실패 신호({reply['failure_signal']})인데 세션 상태가 {reply['status']} 로 바뀌었다")
    if previous_item is not None and reply.get("current_item_id", previous_item) != previous_item:
        raise StepFailure(
            f"실패 신호({reply['failure_signal']})인데 지금 문항이 {previous_item} 에서 {reply['current_item_id']} 로 바뀌었다"
        )
    turn_checks[reply["failure_signal"]] = turn_checks.get(reply["failure_signal"], 0) + 1
    if not resend:
        ledger.streak += 1


def _stream_result(
    ctx: Context,
    client: httpx.Client,
    operation: str,
    label: str,
    checks: list[str],
    *,
    path: dict[str, str] | None = None,
    body: Any = None,
) -> dict[str, Any]:
    """스트림 작업 하나를 부르고 result 의 본문(짝인 JSON 작업의 성공 본문, 스키마 검증은 이벤트 점검이 했다)을 돌려준다. error 로 끝나면 JSON 작업의 4xx·5xx 와 같게 단계가 실패한다."""
    outcome = read_stream(client, ctx.contract, "survey-service", operation, path=path, body=body)
    ctx.streams.append(outcome)
    checks.append(f"{operation} {label}: {outcome.describe()}")
    if outcome.error is not None:
        problem = outcome.error["problem"]
        raise StepFailure(f"{operation}: error 이벤트로 끝났다(상태 {problem.get('status')}, {problem.get('title')}). 다시 보내지 않는다")
    return outcome.result  # type: ignore[no-any-return]


def _check_streaming(ctx: Context, checks: list[str]) -> None:
    """모드별 합격: 공통은 프로토콜 규칙(건마다 점검했다). product 는 더해 delta 가 result 앞에 한 번이라도 와야 한다(실제 토큰 스트리밍). 시간은 보고용이다."""
    total = sum(outcome.deltas for outcome in ctx.streams)
    firsts = [outcome.first_delta_seconds for outcome in ctx.streams if outcome.first_delta_seconds is not None]
    checks.append(
        f"스트림 {len(ctx.streams)}건 합계: delta {total}개, 첫 delta 가장 빠른 값 {min(firsts):.2f}초"
        if firsts
        else f"스트림 {len(ctx.streams)}건 합계: delta 0개"
    )
    if ctx.mode == "product" and total == 0:
        raise StepFailure("product 모드인데 delta 이벤트가 하나도 없었다(토큰 스트리밍이 입구까지 이어지지 않았다)")


def session(ctx: Context, checks: list[str], findings: list[str]) -> None:
    kiosk = ctx.kiosk()
    started = _stream_result(ctx, kiosk, "startSessionStream", "세션 시작", checks, body={"start_code": ctx.start_code})
    ctx.session_id = started["session_id"]
    if started["status"] != "ACTIVE" or started["questionnaire_id"] != QUESTIONNAIRE_ID or not started["response_text"].strip():
        raise StepFailure(f"세션 시작 응답이 기대와 다르다: {json.dumps(started, ensure_ascii=False)[:300]}")
    item = started.get("current_item_id") or ctx.questionnaire.flow["start_item"]
    checks.append(
        f"startSessionStream 200·SSE(결과는 SessionStarted, ACTIVE, 모델이 만든 첫 문장 {len(started['response_text'])}자, 지금 문항 {item})"
    )
    failures: dict[str, int] = {}
    ledger = TurnLedger(limit=ctx.contract.integer_constant(FAILURE_LIMIT_SCHEMA))
    if ctx.mode == "pipeline" and 2 * ledger.limit > PIPELINE_TURNS:
        raise StepFailure(
            f"pipeline 의 턴 수 {PIPELINE_TURNS} 가 연속 실패 한도 {ledger.limit} 의 두 배보다 작아 건너뛰기 되풀이를 볼 수 없다"
        )
    limit = PIPELINE_TURNS if ctx.mode == "pipeline" else PRODUCT_TURN_GUARD
    sent = 0
    resent = False
    status = "ACTIVE"
    per_item: dict[str, int] = {}
    while status == "ACTIVE" and sent < limit:
        turn = script.BY_ITEM.get(item)
        if turn is None:
            if ctx.mode == "product":
                ctx.model_notes.append(f"지금 문항 {item} 의 발화가 대본에 없어 {sent}턴에서 멈췄다")
                break
            turn = script.SCRIPT[sent % len(script.SCRIPT)]
        if ctx.mode == "product":
            per_item[item] = per_item.get(item, 0) + 1
            if per_item[item] > PRODUCT_REPEAT_LIMIT:
                ctx.model_notes.append(f"문항 {item} 이 {PRODUCT_REPEAT_LIMIT}번 되돌아와(확인·되묻기 반복) {sent}턴에서 멈췄다")
                break
        turn_body = {"turn_id": str(uuid.uuid4()), "utterance": turn.utterance}
        reply = _stream_result(
            ctx, kiosk, "submitTurnStream", f"{sent + 1}번째 턴", checks, path={"session_id": ctx.session_id}, body=turn_body
        )
        sent += 1
        _check_turn(ctx, item, reply, failures, ledger)
        if ctx.mode == "pipeline" and "failure_signal" in reply and ledger.streak == 1 and not resent:
            # 같은 turn_id 의 재전송은 연속 실패 수를 올리지 않는다(계약 TurnFailureLimit (1)). 다음 새 turn_id 가 3번째가 아니라 2번째 실패로 세어지는지가 그 증거다
            again = _stream_result(
                ctx,
                kiosk,
                "submitTurnStream",
                f"{sent}번째 턴 같은 turn_id 재전송",
                checks,
                path={"session_id": ctx.session_id},
                body=turn_body,
            )
            _check_turn(ctx, item, again, failures, ledger, resend=True)
            resent = True
            checks.append(
                f"실패한 turn_id 를 다시 보내도 연속 실패 수는 {ledger.streak} 그대로다(다음 새 턴이 {ledger.limit - 1}번째 실패로 세어져야 한다)"
            )
        if "failure_signal" in reply and ctx.mode == "product":
            # 시스템 규칙(상태·지금 문항 불변, 연속 실패 한도)은 _check_turn 이 봤다. 실패 신호 자체는 모델의 출력 결과다
            ctx.model_notes.append(f"{sent}번째 턴(문항 {item}) 실패 신호 {reply['failure_signal']}")
        status = reply["status"]
        item = reply.get("current_item_id", item)
        state = ctx.call(kiosk, "survey-service", "getSessionState", expect=(200,), path={"session_id": ctx.session_id}).body
        if state["status"] != status:
            raise StepFailure(f"턴 응답의 상태 {status} 와 getSessionState 의 {state['status']} 가 다르다")
    ctx.last_status = status
    checks.append(
        f"submitTurnStream {sent}번 모두 200·SSE·계약 일치(성공 {ctx.turn_successes}, 실패 신호 {ctx.turn_failures}, 한도 {ledger.limit}에 닿아 건너뜀 {ctx.turn_skips})"
    )
    if failures:
        checks.append(
            "실패 신호 " + ", ".join(f"{name} {count}" for name, count in sorted(failures.items())) + "건 모두 세션 상태·지금 문항 불변"
        )
    if ctx.skipped:
        checks.append(
            "연속 실패 한도로 건너뜀(실패 신호 없이 안내 문장 ResponseSentence 와 다음 문항): "
            + ", ".join(f"{src} -> {dst or '끝'}" for src, dst in ctx.skipped)
        )
    elif ctx.mode == "pipeline":
        checks.append("실패 신호는 관측되지 않았다(실패 경로는 이 실행에서 시험되지 않았다)")
    ended = ctx.call(kiosk, "survey-service", "endSession", expect=(200,), path={"session_id": ctx.session_id}).body
    if ended["status"] not in ("ENDED_COMPLETE", "ENDED_PARTIAL"):
        raise StepFailure(f"endSession 의 상태가 끝난 상태가 아니다: {ended['status']}")
    ctx.last_status = ended["status"]
    checks.append(f"endSession 200({ended['status']})")
    _check_streaming(ctx, checks)
    if ctx.mode == "product" and ended["status"] != "ENDED_COMPLETE":
        ctx.model_notes.append(f"문진이 끝까지 가지 않았다({ended['status']}, {sent}턴)")
    if ctx.model_notes:
        checks.append("모델 관찰(판정 밖): " + "; ".join(ctx.model_notes))


# ---------------------------------------------------------------- ⑥ 의사
def _same(value: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(value, bool):
        return value is expected
    if isinstance(expected, (int, float)):
        return isinstance(value, (int, float)) and float(value) == float(expected)
    return bool(value == expected)


def check_limit_blanks(ctx: Context, result: dict[str, Any], checks: list[str]) -> None:
    """연속 실패 한도로 건너뛴 문항(⑤가 본 것)과 결과의 FAILURE_LIMIT 빈칸이 맞는지 본다.

    pipeline 은 실패가 결정적이라 두 쪽이 같아야 한다: 건너뛰었다고 본 문항에 빈칸이 없으면 안 되고, 건너뜀으로 보지 않은 문항에 있어도 안 된다(예: 재전송을 세는 서비스는
    우리가 센 것보다 먼저 건너뛴다). product 는 실패 신호를 바로 실패로 다루므로 건너뛴 문항이 없는 것이 정상이지만, 결과에 있으면 실패로 보지 않고 적는다.
    """
    limit_items = sorted({blank["item_id"] for blank in result["blanks"] if blank["reason"] == BLANK_REASON})
    skipped = [source for source, _ in ctx.skipped]
    reasons = sorted({blank["reason"] for blank in result["blanks"]})
    if missing := [item for item in skipped if item not in limit_items]:
        raise StepFailure(f"연속 실패 한도로 건너뛴 문항 {missing} 의 빈칸 원인에 {BLANK_REASON} 가 없다(빈칸 원인 {reasons})")
    if ctx.mode == "pipeline" and (extra := [item for item in limit_items if item not in skipped]):
        raise StepFailure(
            f"결과에 {BLANK_REASON} 빈칸이 있는 문항 {extra} 을 이 시험은 건너뛴 턴으로 세지 않았다(서비스의 연속 실패 수가 시험이 센 것과 다르다)"
        )
    if skipped:
        checks.append(f"건너뛴 문항 {len(skipped)}개 모두 결과의 빈칸 원인이 {BLANK_REASON} 다(문항 {', '.join(skipped)})")
    elif limit_items:
        checks.append(f"연속 실패 한도로 건너뛴 문항 {len(limit_items)}개가 결과에 있다(실패로 보지 않음): {', '.join(limit_items)}")


def doctor(ctx: Context, checks: list[str], findings: list[str]) -> None:
    clinician = ctx.human("clinician-e2e")
    listing = ctx.call(clinician, "survey-service", "listResults", expect=(200,), query={"subject_ref": SUBJECT}).body
    if ctx.session_id not in {item["session_id"] for item in listing["items"]}:
        raise StepFailure("결과 목록(대상자 참조값으로 거름)에 세션이 없다")
    result = ctx.call(clinician, "survey-service", "getResult", expect=(200,), path={"session_id": ctx.session_id}).body
    if result["subject_ref"] != SUBJECT or result["status"] != ctx.last_status or result.get("device_id") not in (None, DEVICE_ID):
        raise StepFailure(
            f"결과의 대상자·상태·기기가 기대와 다르다: {json.dumps({k: result.get(k) for k in ('subject_ref', 'status', 'device_id')}, ensure_ascii=False)}"
        )
    checks.append(
        f"listResults·getResult 200(상태 {result['status']}, 저장된 답 {len(result['answers'])}개, 빈칸 {len(result['blanks'])}개)"
    )
    check_limit_blanks(ctx, result, checks)
    if ctx.mode == "product":
        stored = {answer["key"]: answer["value"] for answer in result["answers"]}
        expected = {key: value for turn in script.SCRIPT for key, value in turn.expected.items()}
        wrong = {
            key: (stored.get(key, "(없음)"), value) for key, value in expected.items() if key not in stored or not _same(stored[key], value)
        }
        if wrong:
            note = f"대본의 기대 값 중 {len(wrong)}/{len(expected)}개가 결과와 다르다: " + "; ".join(
                f"{k}: 결과 {got} 기대 {want}" for k, (got, want) in sorted(wrong.items())[:8]
            )
            ctx.model_notes.append(note)
            checks.append(f"모델 관찰(판정 밖): {note}")
        else:
            checks.append(f"대본의 기대 값 {len(expected)}개가 모두 결과에 저장되었다")
    ack = ctx.call(clinician, "survey-service", "acknowledgeResult", expect=(200,), path={"session_id": ctx.session_id}).body
    after = ctx.call(clinician, "survey-service", "getResult", expect=(200,), path={"session_id": ctx.session_id}).body
    if after.get("acknowledged_by") != ack["acknowledged_by"]:
        raise StepFailure("확인 표시 뒤 결과의 acknowledged_by 가 확인한 의사가 아니다")
    ctx.result = after
    checks.append("acknowledgeResult 200, 결과에 확인한 의사와 시각이 남았다")


# ---------------------------------------------------------------- ⑦ 병원 시스템
ABSENT_REASON_URL = "http://hl7.org/fhir/StructureDefinition/data-absent-reason"  # HL7 FHIR R4 표준 확장. 계약 FhirMapping 은 '빈칸은 answer 없이 data-absent-reason 확장'이라고만 적는다


def fhir_absent_codes(fhir: dict[str, Any]) -> dict[str, list[str]]:
    """FHIR QuestionnaireResponse 에서 linkId 마다 data-absent-reason 확장의 valueCode 를 모은다(item 은 중첩될 수 있다)."""
    found: dict[str, list[str]] = {}

    def walk(items: list[dict[str, Any]]) -> None:
        for entry in items:
            for extension in entry.get("extension", []):
                if extension.get("url") == ABSENT_REASON_URL and "valueCode" in extension:
                    found.setdefault(entry.get("linkId", ""), []).append(extension["valueCode"])
            walk(entry.get("item", []))

    walk(fhir.get("item", []))
    return found


def check_fhir_blanks(result: dict[str, Any], fhir: dict[str, Any]) -> str | None:
    """결과의 FAILURE_LIMIT 빈칸이 FHIR 에서 data-absent-reason `error` 인지 본다. 해당 빈칸이 없으면 None, 있으면 확인한 내용을 돌려준다."""
    blanks = [blank for blank in result["blanks"] if blank["reason"] == BLANK_REASON]
    if not blanks:
        return None
    codes = fhir_absent_codes(fhir)
    wrong: list[str] = []
    for blank in blanks:
        link_id = blank.get("key") or blank["item_id"]  # 계약 FhirMapping: item.linkId 는 문항이면 문항 식별자, 칸이면 칸 식별자
        if codes.get(link_id) != [FHIR_ABSENT_ERROR]:
            wrong.append(f"{link_id}: {codes.get(link_id, '(data-absent-reason 없음)')}")
    if wrong:
        raise StepFailure(
            f"{BLANK_REASON} 빈칸이 FHIR 에서 data-absent-reason {FHIR_ABSENT_ERROR} 가 아니다({len(wrong)}/{len(blanks)}): "
            + "; ".join(wrong[:8])
        )
    return f"결과의 {BLANK_REASON} 빈칸 {len(blanks)}개가 FHIR 에서 모두 data-absent-reason {FHIR_ABSENT_ERROR} 다"


def hospital(ctx: Context, checks: list[str], findings: list[str]) -> None:
    client = ctx.hospital()
    listing = ctx.call(client, "survey-service", "listResults", expect=(200,), query={"subject_ref": SUBJECT}).body
    if ctx.session_id not in {item["session_id"] for item in listing["items"]}:
        raise StepFailure("병원 시스템의 결과 목록에 세션이 없다")
    result = ctx.call(client, "survey-service", "getResult", expect=(200,), path={"session_id": ctx.session_id}).body
    if result != ctx.result:
        raise StepFailure("병원 시스템이 받은 결과가 의사가 본 결과와 다르다")
    fhir = ctx.call(client, "survey-service", "getResultFhir", expect=(200,), path={"session_id": ctx.session_id}).body
    if fhir.get("resourceType") != "QuestionnaireResponse":
        raise StepFailure(f"FHIR 결과의 resourceType 이 QuestionnaireResponse 가 아니다: {fhir.get('resourceType')}")
    checks.append(
        f"기계 토큰(result-reader)으로 listResults·getResult 200, 의사가 본 결과와 같다. getResultFhir 200(QuestionnaireResponse, status {fhir.get('status')})"
    )
    if note := check_fhir_blanks(result, fhir):
        checks.append(note)
    elif ctx.skipped:
        raise StepFailure("건너뛴 문항이 있는데 결과에 FAILURE_LIMIT 빈칸이 없다")


# ---------------------------------------------------------------- ⑧ 직원 호출
def staff_call(ctx: Context, checks: list[str], findings: list[str]) -> None:
    staff = ctx.human("staff-e2e")
    kiosk = ctx.kiosk()
    code = ctx.call(
        staff,
        "survey-service",
        "issueStartCode",
        expect=(201,),
        body={"subject_ref": SUBJECT_CALL, "questionnaire_id": QUESTIONNAIRE_ID},
        idempotent=True,
    ).body["code"]
    session_id = ctx.call(kiosk, "survey-service", "startSession", expect=(201,), body={"start_code": code}).body["session_id"]
    alert = ctx.call(kiosk, "survey-service", "requestStaffCall", expect=(201,), path={"session_id": session_id}).body
    if alert["kind"] != "CALL_STAFF" or alert["session_id"] != session_id:
        raise StepFailure(f"직원 호출이 만든 알림이 CALL_STAFF·그 세션이 아니다: {alert['kind']}")
    alerts = ctx.call(staff, "survey-service", "listStaffAlerts", expect=(200,)).body
    if alert["alert_id"] not in {item["alert_id"] for item in alerts["items"]}:
        raise StepFailure("직원의 알림 목록에 직원 호출 알림이 없다")
    state = ctx.call(kiosk, "survey-service", "getSessionState", expect=(200,), path={"session_id": session_id}).body
    if state["status"] != "PAUSED" or state.get("pause_reason") != "STAFF_CALL":
        raise StepFailure(f"직원 호출 뒤 세션이 PAUSED·STAFF_CALL 이 아니다: {state['status']} {state.get('pause_reason')}")
    checks.append("requestStaffCall 201(CALL_STAFF), 직원의 listStaffAlerts 에 알림이 있고 세션이 PAUSED(STAFF_CALL)다")


STEPS: list[tuple[str, Step]] = [
    ("① 어댑터 게시(package-publish)", publish),
    ("② 패키지 조회·활성화·적재(승인자)", activate),
    ("③ 문항 세트 올리기·활성화(작성자)", question_set),
    ("④ 시작 코드 발급(직원)", start_code),
    ("⑤ 키오스크 세션(기기 인증서)", session),
    ("⑥ 결과 조회·확인 표시(의사)", doctor),
    ("⑦ 결과·FHIR 당겨 가기(병원 시스템)", hospital),
    ("⑧ 직원 호출 알림", staff_call),
]


def run(ctx: Context, progress: Callable[[str], None]) -> list[StepResult]:
    """단계를 순서대로 돌린다. 한 단계가 실패하면 뒤 단계는 건너뛴다(앞 단계의 결과에 기대므로)."""
    results: list[StepResult] = []
    blocked = False
    for name, step in STEPS:
        if blocked:
            results.append(StepResult(name, "건너뜀", detail="앞 단계가 실패했다"))
            continue
        checks: list[str] = []
        findings: list[str] = []
        started = time.monotonic()
        try:
            step(ctx, checks, findings)
            results.append(StepResult(name, "실패" if findings else "통과", time.monotonic() - started, checks, findings=findings))
        except (StepFailure, httpx.HTTPError, KeyError, ValueError) as error:
            blocked = True
            results.append(StepResult(name, "실패", time.monotonic() - started, checks, f"{type(error).__name__}: {error}"[:900], findings))
        progress(f"{name}: {results[-1].status}")
    return results
