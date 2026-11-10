"""시나리오: 한 건의 문진을 입구(Envoy)를 지나는 실제 HTTP 로 끝까지(ADR 0025).

① 어댑터 게시(package-publish) ② 승인자가 패키지 조회·활성화·적재 대기 ③ 문항 세트 올리기·활성화 ④ 시작 코드 발급
⑤ 키오스크 세션(시작, 턴 여러 번, 종료) ⑥ 의사가 결과 조회·확인 표시 ⑦ 병원 시스템이 결과·FHIR 로 당겨 감 ⑧ 직원 호출 알림.

모든 호출은 계약 검증을 거친다(contract.Contract.call): 상태 코드가 계약에 있고 기대한 것인지, 응답이 그 상태의 스키마를 지키는지.
pipeline 모드는 계약대로 응답하는지와 실패 처리(출력 불가 -> 실패 신호, 세션 상태 불변)를 본다. product 모드는 더해 대본의 기대 값이 결과에 저장되는지와 문진이 끝까지 가는지를 본다.
실패한 호출을 다시 시도하지 않는다. 기다림은 상태를 보는 것(적재 상태 조회)뿐이고 상한 안에서만 한다.
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

DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
# 왜 190초: 계약에 모델 적재 완료의 상한이 없다(확인함). 계약 D125 가 사람 화면에 준 가장 긴 상한(release-gate 화면 190초)을 빌려 쓴다. 측정한 값이 아니다(ADR 0025)
LOAD_LIMIT = 190
POLL_INTERVAL = 2  # 계약 SessionStatePollSeconds(2초)와 같은 간격으로 상태를 본다
PIPELINE_TURNS = 6  # pipeline 모드가 보내는 턴 수. 어댑터가 학습되지 않아 문진이 끝까지 가지 않으므로 상한을 둔다(대본의 앞 문항들)
PRODUCT_TURN_GUARD = len(script.SCRIPT) + 5  # product 모드: 순서표가 대본보다 길게 이어지면 멈춘다(대본에 없는 문항에서 막힌다)
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
    last_status: str = ""
    result: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())

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
    deadline = time.monotonic() + LOAD_LIMIT
    status: dict[str, Any] = accepted.body
    while status["state"] != "READY":
        if status["state"] == "FAILED":
            raise StepFailure(f"적재가 실패했다(FAILED): {json.dumps(status, ensure_ascii=False)[:300]}")
        if time.monotonic() > deadline:
            raise StepFailure(f"{LOAD_LIMIT}초 안에 READY 가 되지 않았다(마지막 상태 {status['state']})")
        time.sleep(POLL_INTERVAL)
        status = ctx.call(approver, "model-runtime", "getModelStatus", expect=(200,)).body
    if status.get("package_digest") != ctx.package_digest or status.get("runtime_contract_version") != RUNTIME_CONTRACT_VERSION:
        raise StepFailure(f"READY 인데 활성 패키지·문항 은행 버전이 기대와 다르다: {json.dumps(status, ensure_ascii=False)[:300]}")
    checks.append(f"getModelStatus READY(적재 상한 {LOAD_LIMIT}초 안), 활성 패키지가 게시한 것이다")


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
def _check_turn(ctx: Context, previous_item: str | None, reply: dict[str, Any], turn_checks: dict[str, int]) -> None:
    """한 턴의 응답 판정: 계약 검증은 호출이 했다. 실패 신호이면 세션 상태가 바뀌지 않았는지 본다(D75)."""
    if "failure_signal" not in reply:
        ctx.turn_successes += 1
        return
    ctx.turn_failures += 1
    if reply["status"] != "ACTIVE":
        raise StepFailure(f"실패 신호({reply['failure_signal']})인데 세션 상태가 {reply['status']} 로 바뀌었다")
    if previous_item is not None and reply.get("current_item_id", previous_item) != previous_item:
        raise StepFailure(
            f"실패 신호({reply['failure_signal']})인데 지금 문항이 {previous_item} 에서 {reply['current_item_id']} 로 바뀌었다"
        )
    turn_checks[reply["failure_signal"]] = turn_checks.get(reply["failure_signal"], 0) + 1


def session(ctx: Context, checks: list[str], findings: list[str]) -> None:
    kiosk = ctx.kiosk()
    started = ctx.call(kiosk, "survey-service", "startSession", expect=(201,), body={"start_code": ctx.start_code}).body
    ctx.session_id = started["session_id"]
    if started["status"] != "ACTIVE" or started["questionnaire_id"] != QUESTIONNAIRE_ID or not started["response_text"].strip():
        raise StepFailure(f"세션 시작 응답이 기대와 다르다: {json.dumps(started, ensure_ascii=False)[:300]}")
    item = started.get("current_item_id") or ctx.questionnaire.flow["start_item"]
    checks.append(f"startSession 201(ACTIVE, 모델이 만든 첫 문장 {len(started['response_text'])}자, 지금 문항 {item})")
    failures: dict[str, int] = {}
    limit = PIPELINE_TURNS if ctx.mode == "pipeline" else PRODUCT_TURN_GUARD
    sent = 0
    status = "ACTIVE"
    while status == "ACTIVE" and sent < limit:
        turn = script.BY_ITEM.get(item)
        if turn is None:
            if ctx.mode == "product":
                raise StepFailure(f"서비스가 알려 준 지금 문항 {item} 의 발화가 대본에 없다")
            turn = script.SCRIPT[sent % len(script.SCRIPT)]
        reply = ctx.call(
            kiosk,
            "survey-service",
            "submitTurn",
            expect=(200,),
            path={"session_id": ctx.session_id},
            body={"turn_id": str(uuid.uuid4()), "utterance": turn.utterance},
        ).body
        sent += 1
        _check_turn(ctx, item, reply, failures)
        if "failure_signal" in reply and ctx.mode == "product":
            raise StepFailure(
                f"product 모드에서 턴이 실패 신호({reply['failure_signal']})를 냈다(문항 {item}, {sent}번째 턴). 실패한 턴을 다시 보내지 않는다"
            )
        status = reply["status"]
        item = reply.get("current_item_id", item)
        state = ctx.call(kiosk, "survey-service", "getSessionState", expect=(200,), path={"session_id": ctx.session_id}).body
        if state["status"] != status:
            raise StepFailure(f"턴 응답의 상태 {status} 와 getSessionState 의 {state['status']} 가 다르다")
    ctx.last_status = status
    checks.append(f"submitTurn {sent}번 모두 200·계약 일치(성공 {ctx.turn_successes}, 실패 신호 {ctx.turn_failures})")
    if failures:
        checks.append(
            "실패 신호 " + ", ".join(f"{name} {count}" for name, count in sorted(failures.items())) + "건 모두 세션 상태·지금 문항 불변"
        )
    elif ctx.mode == "pipeline":
        checks.append("실패 신호는 관측되지 않았다(실패 경로는 이 실행에서 시험되지 않았다)")
    ended = ctx.call(kiosk, "survey-service", "endSession", expect=(200,), path={"session_id": ctx.session_id}).body
    if ended["status"] not in ("ENDED_COMPLETE", "ENDED_PARTIAL"):
        raise StepFailure(f"endSession 의 상태가 끝난 상태가 아니다: {ended['status']}")
    ctx.last_status = ended["status"]
    checks.append(f"endSession 200({ended['status']})")
    if ctx.mode == "product" and ended["status"] != "ENDED_COMPLETE":
        raise StepFailure(f"product 모드는 문진이 끝까지 가야 한다(ENDED_COMPLETE). 실제 {ended['status']}")


# ---------------------------------------------------------------- ⑥ 의사
def _same(value: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(value, bool):
        return value is expected
    if isinstance(expected, (int, float)):
        return isinstance(value, (int, float)) and float(value) == float(expected)
    return bool(value == expected)


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
    if ctx.mode == "product":
        stored = {answer["key"]: answer["value"] for answer in result["answers"]}
        expected = {key: value for turn in script.SCRIPT for key, value in turn.expected.items()}
        wrong = {
            key: (stored.get(key, "(없음)"), value) for key, value in expected.items() if key not in stored or not _same(stored[key], value)
        }
        if wrong:
            raise StepFailure(
                f"대본의 기대 값이 결과에 저장되지 않았다({len(wrong)}/{len(expected)}): "
                + "; ".join(f"{k}: 결과 {got} 기대 {want}" for k, (got, want) in sorted(wrong.items())[:8])
            )
        checks.append(f"대본의 기대 값 {len(expected)}개가 모두 결과에 저장되었다")
    ack = ctx.call(clinician, "survey-service", "acknowledgeResult", expect=(200,), path={"session_id": ctx.session_id}).body
    after = ctx.call(clinician, "survey-service", "getResult", expect=(200,), path={"session_id": ctx.session_id}).body
    if after.get("acknowledged_by") != ack["acknowledged_by"]:
        raise StepFailure("확인 표시 뒤 결과의 acknowledged_by 가 확인한 의사가 아니다")
    ctx.result = after
    checks.append("acknowledgeResult 200, 결과에 확인한 의사와 시각이 남았다")


# ---------------------------------------------------------------- ⑦ 병원 시스템
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
