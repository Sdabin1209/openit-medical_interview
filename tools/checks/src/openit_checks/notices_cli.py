"""openit-notices {generate|image}: 제3자 고지 생성과 이미지 점검(ADR 0018).

- generate [영역 폴더...]: 잠금 파일에서 THIRD_PARTY_NOTICES 를 만들어 영역 폴더에 쓴다(폴더를 안 주면 services/·web/ 의 모든 영역).
- image <영역 폴더> --image <이미지>: 이미지 안의 고지가 잠금 파일에서 만든 것과 같은지 본다. 위반이 있으면 종료 코드 1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import notices


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openit-notices", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="THIRD_PARTY_NOTICES 를 만든다")
    gen.add_argument("areas", nargs="*", type=Path)
    image = sub.add_parser("image", help="이미지의 고지를 점검한다")
    image.add_argument("area", type=Path)
    image.add_argument("--image", required=True)
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()
    if args.command == "generate":
        folders = [a.resolve() for a in args.areas] or [p for _, p in notices.area_folders(root)]
        if not folders:
            print("대상 영역이 없다", file=sys.stderr)
            return 2
        for folder in folders:
            try:
                text = notices.generate(folder)
            except notices.NoticesError as error:
                print(f"[{notices.CHECK}] {folder}: {error}", file=sys.stderr)
                return 1
            (folder / notices.NOTICES_FILE).write_text(text, encoding="utf-8")
            print(f"만들었다: {folder / notices.NOTICES_FILE}")
        return 0
    violations = notices.verify_image(root, args.area.resolve(), args.image)
    for violation in violations:
        print(violation, file=sys.stderr)
    print(f"{'FAIL' if violations else 'OK  '} notices-image (위반 {len(violations)})")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
