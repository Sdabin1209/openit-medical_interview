from pathlib import Path

import pytest

from __PKG__.main import SecretError, read_secret


def test_reads_value_from_file(tmp_path: Path) -> None:
    file = tmp_path / "s"
    file.write_text("값-1234\n", encoding="utf-8")
    assert read_secret("DB", {"DB_FILE": str(file)}) == "값-1234"


def test_does_not_read_plain_env_var() -> None:
    # 환경 변수 DB 에 값이 있어도 읽지 않는다(비밀은 파일만, D84)
    with pytest.raises(SecretError):
        read_secret("DB", {"DB": "leak"})


def test_missing_file_error_has_no_path_or_value(tmp_path: Path) -> None:
    missing = tmp_path / "nope-secret-path"
    with pytest.raises(SecretError) as info:
        read_secret("DB", {"DB_FILE": str(missing)})
    assert "nope-secret-path" not in str(info.value)
    assert "DB" in str(info.value)


def test_empty_file_is_error(tmp_path: Path) -> None:
    file = tmp_path / "s"
    file.write_text("\n", encoding="utf-8")
    with pytest.raises(SecretError):
        read_secret("DB", {"DB_FILE": str(file)})
