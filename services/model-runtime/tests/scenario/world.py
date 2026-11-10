"""시나리오 시험의 세계: 시험용 레지스트리(TLS), 추론 엔진, 신원 공급자, 평가 집합, 게시한 모델 패키지."""

import json
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from model_io import compose_response_from_request, serialize_extraction_input, serialize_response_input

from fakes.engine import FakeEngine, dump
from fakes.pki import Pki, make_pki
from fakes.registry import FakeRegistry
from fakes.servers import Running, run_server
from model_runtime.publish import main as publish_main
from support import REGISTRY_PASSWORD, REGISTRY_USER, adapter_folder

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SYSTEM_A = "시스템 프롬프트 A: 환자 발화 1턴을 읽고 JSON 으로 출력하세요."
SYSTEM_B = "시스템 프롬프트 B: 응답 문장만 출력하세요."


def bank() -> dict[str, Any]:
    return json.loads((FIXTURES / "question_bank_v1.json").read_text(encoding="utf-8"))


def _value(
    key: str, value: object, status: str = "ANSWERED", precision: str = "exact", save: bool = True
) -> dict[str, Any]:
    return {"key": key, "value": value, "precision": precision, "status": status, "save": save}


# 평가 집합과 요청에 쓰는 A 입력 셋. 정답 출력은 학습 파일과 같은 모양이다
A_NEXT: dict[str, Any] = {
    "question_id": "Q1.D01",
    "current_question": "뇌졸중 진단을 받으셨거나 약을 드시나요?",
    "state": {},
    "user_utterance": "네 오년 전에 진단받고 지금 약 먹어요",
}
A_NEXT_GOLD: dict[str, Any] = {
    "action": "NEXT",
    "next_item": "Q1.D02",
    "values": [_value("Q1.D01.diagnosed", True), _value("Q1.D01.on_medication", True)],
}
A_SKIP: dict[str, Any] = {
    "question_id": "Q4",
    "current_question": "담배를 피우신 적 있나요?",
    "state": {},
    "user_utterance": "담배는 평생 안 피웠어요",
}
A_SKIP_GOLD: dict[str, Any] = {"action": "NEXT", "next_item": "Q5", "values": [_value("Q4.answer", False)]}
A_BAD: dict[str, Any] = {
    "question_id": "Q8_1",
    "current_question": "일주일에 며칠 운동하세요?",
    "state": {},
    "user_utterance": "일주일에 사흘이요",
}
A_BAD_GOLD: dict[str, Any] = {"action": "NEXT", "next_item": "Q8_2", "values": [_value("Q8_1.days", 3)]}
B_ROWS: list[dict[str, Any]] = [
    {
        "action": "NEXT",
        "known": "진단 받음",
        "next": {"question_id": "Q1.D02", "text": "심근경색 진단을 받으셨나요?", "type": "NEXT"},
        "topic": "뇌졸중",
        "user_utterance": "네 진단받았어요",
    },
    {
        "action": "NEXT",
        "known": "하루 15분",
        "next": {"type": "END"},
        "topic": "근력 운동",
        "user_utterance": "열다섯 분이요",
    },
]


def a_key(payload: dict[str, Any]) -> str:
    return serialize_extraction_input(payload, list(payload["state"]))


def ask(payload: dict[str, Any]) -> dict[str, Any]:
    """학습 형식의 A 입력(state 가 비어 있다)에서 구조화된 요청 칸을 만든다."""
    return {k: payload[k] for k in ("question_id", "current_question", "user_utterance")} | {"slots": []}


# 응답 생성 요청(구조화된 값). 모델 입력의 글 조각은 서버가 만든다
B_REQUEST: dict[str, Any] = {
    "action": "NEXT",
    "question_id": "Q1.D01",
    "user_utterance": "네 진단받았어요",
    "slots": [],
    "values": [_value("Q1.D01.diagnosed", True)],
    "next": {"type": "NEXT", "question_id": "Q1.D02", "text": "심근경색 진단을 받으셨나요?"},
}
B_START: dict[str, Any] = {
    "action": "START",
    "next": {"type": "NEXT", "question_id": "Q1.D01", "text": "뇌졸중 진단을 받으셨나요?"},
}


def line(system: str, user: str, assistant: str) -> str:
    return json.dumps(
        {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ]
        },
        ensure_ascii=False,
    )


@dataclass
class World:
    tmp: Path
    pki: Pki
    registry: FakeRegistry
    registry_url: str
    engine: FakeEngine
    engine_url: str
    answers: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    published: int = 0

    def answer(self, _adapter: str, user: str) -> str:
        return self.answers.get(user, "")

    def publish(
        self, label: str, *, prompt_suffix: str = "", report_name: str = "report.json", limit: int | None = None
    ) -> str:
        """어댑터 두 개를 평가하고 모델 패키지로 올린 뒤 digest 를 돌려준다(package_publish 도구)."""
        root = self.tmp / f"publish-{label}"
        root.mkdir()
        (root / "bank.json").write_text(json.dumps(bank()), encoding="utf-8")
        (root / "prompt-a.txt").write_text(SYSTEM_A + prompt_suffix, encoding="utf-8")
        (root / "prompt-b.txt").write_text(SYSTEM_B + prompt_suffix, encoding="utf-8")
        a_rows: list[tuple[dict[str, Any], dict[str, Any]]] = [
            (A_NEXT, A_NEXT_GOLD),
            (A_SKIP, A_SKIP_GOLD),
            (A_BAD, A_BAD_GOLD),
        ]
        (root / "eval-a.jsonl").write_text(
            "\n".join(line(SYSTEM_A, a_key(p), dump(g)) for p, g in a_rows) + "\n", encoding="utf-8"
        )
        (root / "eval-b.jsonl").write_text(
            "\n".join(line(SYSTEM_B, serialize_response_input(p), "정답 문장") for p in B_ROWS) + "\n", encoding="utf-8"
        )
        folder_a = adapter_folder(root, "adapter-a", weights=f"a-{label}".encode())
        folder_b = adapter_folder(root, "adapter-b", weights=f"b-{label}".encode())
        import io
        from contextlib import redirect_stdout

        out = io.StringIO()
        with redirect_stdout(out):
            code = publish_main(
                [
                    "publish",
                    "--adapter-a",
                    str(folder_a),
                    "--adapter-b",
                    str(folder_b),
                    "--system-prompt-a",
                    str(root / "prompt-a.txt"),
                    "--system-prompt-b",
                    str(root / "prompt-b.txt"),
                    "--question-bank",
                    str(root / "bank.json"),
                    "--eval-a",
                    str(root / "eval-a.jsonl"),
                    "--eval-b",
                    str(root / "eval-b.jsonl"),
                    "--engine-url",
                    self.engine_url,
                    "--registry-url",
                    self.registry_url,
                    "--repository",
                    "openit/model-package",
                    "--credentials-file",
                    str(self.tmp / "publisher.credentials"),
                    "--root-certificate-file",
                    str(self.pki.root),
                    "--base-model",
                    "Qwen/Qwen3-8B",
                    "--dataset-version-id",
                    str(uuid.uuid4()),
                    "--training-run-a",
                    str(uuid.uuid4()),
                    "--training-run-b",
                    str(uuid.uuid4()),
                    "--runtime-contract-version",
                    "1",
                    "--workdir",
                    str(root / "work"),
                    "--report-out",
                    str(root / report_name),
                    *(["--limit", str(limit)] if limit else []),
                ]
            )
        assert code == 0
        return out.getvalue().strip().splitlines()[-1]


@contextmanager
def world(tmp: Path) -> Generator[World]:
    pki = make_pki(tmp / "pki")
    (tmp / "publisher.credentials").write_text(f"{REGISTRY_USER}:{REGISTRY_PASSWORD}\n", encoding="utf-8")
    registry = FakeRegistry(REGISTRY_USER, REGISTRY_PASSWORD)
    engine = FakeEngine()
    with run_server(registry.app(), pki) as reg, run_server(engine.app()) as eng:
        value = World(tmp, pki, registry, reg.url, engine, eng.url)
        engine.answer = value.answer
        value.answers[a_key(A_NEXT)] = dump(A_NEXT_GOLD)
        value.answers[a_key(A_SKIP)] = dump(A_SKIP_GOLD)
        # 일부러 틀린 출력: 다음 문항이 순서표와 다르다(고쳐 쓰기 전 위반으로 센다)
        value.answers[a_key(A_BAD)] = dump({**A_BAD_GOLD, "next_item": "Q9_1"})
        for payload in B_ROWS:
            value.answers[serialize_response_input(payload)] = "진단 받으셨군요. 다음 질문입니다."
        for request in (B_REQUEST, B_START):
            value.answers[serialize_response_input(compose_response_from_request(request))] = (
                "진단 받으셨군요. 다음 질문입니다."
            )
        yield value


__all__ = ["Running", "World", "world"]
