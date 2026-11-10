"""실행 기록 파일: 새 실행이 맨 위에 쌓이고 이전 기록이 남는다."""

from __future__ import annotations

from pathlib import Path

from openit_e2e import report


def record(mode: str, verdict: str, started: str) -> report.RunRecord:
    steps = [
        report.StepResult("① 어댑터 게시", "통과", 12.34, ["패키지 | 올림"]),
        report.StepResult("② 활성화", "실패" if verdict == "실패" else "통과", 1.0, [], "오류\n줄바꿈"),
    ]
    return report.RunRecord(started, mode, verdict, {"GPU": "NVIDIA GeForce RTX 4070 SUPER, 12282 MiB"}, steps, [], 99.0, "비고")


def test_new_run_goes_on_top_and_old_runs_stay(tmp_path: Path) -> None:
    path = tmp_path / "E2E_RESULTS.md"
    report.update(path, record("pipeline", "실패", "2026-11-11T01:00:00+00:00"))
    report.update(path, record("product", "통과", "2026-11-11T02:00:00+00:00"))
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# E2E 결과")
    first, second = (
        text.index("## 실행 2026-11-11T02:00:00+00:00 · product · 통과"),
        text.index("## 실행 2026-11-11T01:00:00+00:00 · pipeline · 실패"),
    )
    assert first < second
    assert text.count("## 실행 ") == 2
    assert "NVIDIA GeForce RTX 4070 SUPER" in text


def test_table_cells_do_not_break_the_table() -> None:
    rendered = report.render(record("pipeline", "실패", "2026-11-11T01:00:00+00:00"))
    assert "패키지 \\| 올림" in rendered
    assert "오류 줄바꿈" in rendered
    assert "정리 뒤 남은 컨테이너·볼륨·네트워크(이 실행의 프로젝트): 0개" in rendered


def test_leftovers_are_listed() -> None:
    value = record("pipeline", "실패", "2026-11-11T01:00:00+00:00")
    value.leftovers = ["network:abc"]
    assert "1개 (network:abc)" in report.render(value)
