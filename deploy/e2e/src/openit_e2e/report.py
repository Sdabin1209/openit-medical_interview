"""실행 결과 기록(`deploy/docs/E2E_RESULTS.md`): 실행 시각·모드·환경(GPU 이름)·단계별 결과. 실행 기록 한 곳이다(새 실행이 맨 위에 쌓인다)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

HEADER = """# E2E 결과

`./deploy e2e` 가 쓰는 **E2E 실행 기록 한 곳**이다. 새 실행이 맨 위에 쌓인다. 영역의 시험 상태는 각 영역 README 5절, 배포 통합 확인은 [INTEGRATION.md](INTEGRATION.md)다.
실행 규약(샌드박스, 두 모드, 시나리오 여덟 단계, 판정)은 [ADR 0025](../../docs/adr/0025-E2E-실행-규약과-두-모드.md)다.
"""
ENTRY_MARK = "\n## 실행 "


@dataclass
class StepResult:
    name: str
    status: str  # 통과 | 실패 | 건너뜀
    seconds: float = 0.0
    checks: list[str] = field(default_factory=lambda: list[str]())
    detail: str = ""
    findings: list[str] = field(default_factory=lambda: list[str]())  # 계약을 어겼지만 뒤 단계를 막지 않는 발견. 있으면 단계는 실패다


@dataclass
class RunRecord:
    started_at: str
    mode: str
    verdict: str  # 통과 | 실패
    environment: dict[str, str]
    steps: list[StepResult]
    leftovers: list[str]
    elapsed_seconds: float
    note: str = ""


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render(record: RunRecord) -> str:
    lines = [f"## 실행 {record.started_at} · {record.mode} · {record.verdict}", ""]
    if record.note:
        lines += [f"비고: {record.note}", ""]
    lines += [f"- 모드: {record.mode}", f"- 걸린 시간: {record.elapsed_seconds:.0f}초"]
    lines += [f"- {key}: {value}" for key, value in record.environment.items()]
    lines += [
        f"- 정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): {len(record.leftovers)}개"
        + (f" ({', '.join(record.leftovers)})" if record.leftovers else ""),
        "",
    ]
    lines += ["| 단계 | 결과 | 시간(초) | 확인한 것 |", "|---|---|---:|---|"]
    for step in record.steps:
        shown = (
            "; ".join(step.checks)
            + "".join(f" **[발견] {finding}**" for finding in step.findings)
            + (f" [{step.detail}]" if step.detail else "")
        )
        lines.append(f"| {_cell(step.name)} | {step.status} | {step.seconds:.1f} | {_cell(shown)} |")
    return "\n".join(lines) + "\n"


def update(path: Path, record: RunRecord) -> None:
    """기록 파일의 맨 위(머리글 바로 아래)에 이 실행을 넣는다. 이전 기록은 그대로 둔다."""
    previous = path.read_text(encoding="utf-8") if path.is_file() else HEADER
    body = previous.split(ENTRY_MARK, 1)[1] if ENTRY_MARK in previous else ""
    entries = (ENTRY_MARK.lstrip("\n") + body) if body else ""
    path.write_text(HEADER + "\n" + render(record) + ("\n" + entries if entries else ""), encoding="utf-8")
