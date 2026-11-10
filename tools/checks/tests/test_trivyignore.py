"""`.trivyignore` 점검이 사유·만료일 규칙을 잡는지 본다."""

from datetime import date
from pathlib import Path

from openit_checks import trivyignore

from .conftest_helpers import write

TODAY = date(2026, 11, 10)


def test_header_only_file_passes(tmp_path: Path) -> None:
    write(tmp_path, ".trivyignore", "# 설명만 있다\n")
    assert trivyignore.run(tmp_path, TODAY) == []


def test_entry_with_reason_and_future_expiry_passes(tmp_path: Path) -> None:
    write(tmp_path, ".trivyignore", "# 사유: 도달할 수 없는 경로다. 검토: 2026-11-10\nCVE-2026-1 exp:2027-01-31\n")
    assert trivyignore.run(tmp_path, TODAY) == []


def test_missing_reason_missing_expiry_and_expired_fail(tmp_path: Path) -> None:
    text = "CVE-1 exp:2027-01-31\n\n# 사유: x\nCVE-2\n\n# 사유: y\nCVE-3 exp:2026-01-01\n"
    write(tmp_path, ".trivyignore", text)
    messages = [v.message for v in trivyignore.run(tmp_path, TODAY)]
    assert any("사유" in m for m in messages)
    assert any("형식" in m for m in messages)
    assert any("지났다" in m for m in messages)


def test_missing_file_fails(tmp_path: Path) -> None:
    assert len(trivyignore.run(tmp_path, TODAY)) == 1
