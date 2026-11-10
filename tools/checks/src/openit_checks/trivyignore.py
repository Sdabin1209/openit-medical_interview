"""`.trivyignore` 점검(ADR 0016): 항목마다 사유 주석과 만료일(`exp:YYYY-MM-DD`)이 있어야 하고, 만료되지 않아야 한다."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .common import Violation

CHECK = "trivyignore"
ENTRY = re.compile(r"^(\S+)\s+exp:(\d{4}-\d{2}-\d{2})$")


def run(root: Path, today: date | None = None) -> list[Violation]:
    path = root / ".trivyignore"
    if not path.is_file():
        return [Violation(CHECK, ".trivyignore", "파일이 없다(항목이 없어도 헤더 주석만 있는 파일을 둔다)")]
    now = today or date.today()
    violations: list[Violation] = []
    reason_seen = False
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        where = f".trivyignore:{number}"
        if not line:
            reason_seen = False
        elif line.startswith("#"):
            reason_seen = reason_seen or ("사유" in line and not line.startswith("# 예:") and not line.startswith("#  "))
        else:
            match = ENTRY.match(line)
            if not match:
                violations.append(Violation(CHECK, where, f"'<ID> exp:<YYYY-MM-DD>' 형식이 아니다: {line}"))
            elif date.fromisoformat(match.group(2)) < now:
                violations.append(
                    Violation(CHECK, where, f"{match.group(1)} 의 만료일 {match.group(2)} 이 지났다. 고치거나 사유를 다시 검토해 연장한다")
                )
            if not reason_seen:
                violations.append(Violation(CHECK, where, "바로 위에 '# 사유: ...' 주석이 없다"))
            reason_seen = False
    return violations
