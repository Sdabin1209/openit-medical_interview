"""openit-check <이름|all> [--root 경로]. 위반이 있으면 종료 코드 1."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from . import area_isolation, bake_targets, docker_isolation, dockerfile_lint, image_pins, licenses, trivyignore
from .common import Violation

CHECKS: dict[str, Callable[[Path], list[Violation]]] = {
    "licenses": licenses.run,
    "docker-isolation": docker_isolation.run,
    "image-pins": image_pins.run,
    "bake-targets": bake_targets.run,
    "area-isolation": area_isolation.run,
    "dockerfile-lint": dockerfile_lint.run,
    "trivyignore": trivyignore.run,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openit-check", description=__doc__)
    parser.add_argument("name", choices=[*CHECKS, "all"])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args(argv)
    names = list(CHECKS) if args.name == "all" else [args.name]
    failed = 0
    for name in names:
        violations = CHECKS[name](args.root)
        for violation in violations:
            print(violation, file=sys.stderr)
        print(f"{'FAIL' if violations else 'OK  '} {name} (위반 {len(violations)})")
        failed += bool(violations)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
