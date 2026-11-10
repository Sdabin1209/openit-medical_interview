"""deploy/docs/INSTALL.md 의 `./deploy` 명령이 실제 명령과 옵션에 맞는지 대조한다(문서가 없는 명령을 가리키지 않게)."""

import re
import subprocess
from pathlib import Path

import pytest

from .conftest import REPO

DOC = REPO / "deploy" / "docs" / "INSTALL.md"


def doc_commands() -> list[list[str]]:
    found: list[list[str]] = []
    for block in re.findall(r"```\n(.*?)```", DOC.read_text(encoding="utf-8"), re.S):
        for line in block.splitlines():
            line = line.split("#", 1)[0].strip()
            if line.startswith("./deploy "):
                found.append(line.split()[1:])
    return found


def split(tokens: list[str]) -> tuple[list[str], list[str]]:
    """명령 단어(하위 명령)와 옵션(`--x`) 으로 나눈다. 인자(<…>, 경로)는 뺀다."""
    words: list[str] = []
    for token in tokens:
        if token.startswith(("-", "<")) or "/" in token:
            break
        words.append(token)
    return words, [t for t in tokens if t.startswith("--")]


def test_doc_has_commands() -> None:
    assert len(doc_commands()) >= 12


@pytest.mark.parametrize("tokens", doc_commands(), ids=lambda t: " ".join(t))
def test_command_and_options_exist(tokens: list[str]) -> None:
    words, options = split(tokens)
    result = subprocess.run([str(REPO / "deploy" / "deploy"), *words, "--help"], capture_output=True, text=True, check=False, cwd=REPO)  # noqa: S603
    assert result.returncode == 0, result.stderr[-300:]
    for option in options:
        assert option in result.stdout, f"{option} 이 `{' '.join(words)} --help` 에 없다"


def test_every_doc_section_listed_in_toc_exists() -> None:
    text = DOC.read_text(encoding="utf-8")
    for number in range(1, 13):
        assert re.search(rf"^## {number}\. ", text, re.M), number


def test_layout_example_is_referenced_and_exists() -> None:
    assert (Path(REPO) / "deploy" / "layout.example.json").is_file()
    assert "layout.example.json" in DOC.read_text(encoding="utf-8")
