"""제3자 고지 생성·점검 시험(ADR 0018): 잠금 파일 -> 고지 내용, 누락·불일치 시 실패, 개발 의존 제외."""

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

from openit_checks import notices
from openit_checks.cli import main
from openit_checks.notices_cli import main as notices_main

from .conftest_helpers import write

MIT = "MIT License\n\nCopyright (c) 2020 Alice\n\nPermission is hereby granted...\n"
APACHE = "Apache License\nVersion 2.0\n\n   copyright license to reproduce,\n\n   Copyright [yyyy] [name of copyright owner]\n"
NOTICE = "Example NOTICE\nThis product includes software developed by Bob.\n"


# ---- 순수 함수: 렌더링

def _entry(name: str, version: str = "1.0.0", license_id: str = "MIT", text: str = MIT, notice: str = "") -> notices.Entry:
    lic = (notices.SourceFile("LICENSE", text),)
    note = (notices.SourceFile("NOTICE", notice),) if notice else ()
    return notices.Entry(name, version, license_id, "https://example.test/" + name, "Alice", lic, note)


def test_render_has_name_version_license_copyright_and_full_text() -> None:
    text = notices.render("python", "uv.lock", [_entry("alpha")])
    assert "- alpha 1.0.0 (MIT)" in text
    assert "라이선스: MIT" in text
    assert "주소: https://example.test/alpha" in text
    assert "저작권:\n  Copyright (c) 2020 Alice" in text
    assert "--- 라이선스 전문 (LICENSE) ---" in text
    assert "Permission is hereby granted..." in text


def test_render_includes_apache_notice_file() -> None:
    text = notices.render("python", "uv.lock", [_entry("beta", license_id="Apache-2.0", text=APACHE, notice=NOTICE)])
    assert "--- NOTICE (NOTICE) ---" in text
    assert "This product includes software developed by Bob." in text


def test_apache_boilerplate_is_not_a_copyright_notice() -> None:
    entry = _entry("beta", license_id="Apache-2.0", text=APACHE)
    assert notices.copyright_lines(entry) == []
    text = notices.render("python", "uv.lock", [entry])
    assert "저작권: 라이선스 파일에 연도가 있는 저작권 표시가 없다. 저자(패키지 메타데이터): Alice" in text


def test_copyright_without_year_is_kept() -> None:
    entry = _entry("gamma", text="Copyright (c) Meta Platforms, Inc. and affiliates.\n\nPermission...\n")
    assert notices.copyright_lines(entry) == ["Copyright (c) Meta Platforms, Inc. and affiliates."]


def test_render_is_sorted_and_independent_of_input_order() -> None:
    one = [_entry("Zeta"), _entry("alpha"), _entry("alpha", "0.9.0")]
    two = list(reversed(one))
    first = notices.render("npm", "package-lock.json", one)
    assert first == notices.render("npm", "package-lock.json", two)
    assert first.index("- alpha 0.9.0") < first.index("- alpha 1.0.0") < first.index("- Zeta 1.0.0")


def test_collect_files_splits_notice_dedups_and_normalizes_newlines(tmp_path: Path) -> None:
    a = write(tmp_path, "a/LICENSE", "text\r\nline\r\n\r\n")
    b = write(tmp_path, "b/COPYING", "text\nline\n")  # 같은 내용: 한 번만
    n = write(tmp_path, "c/NOTICE.txt", "notice body\n")
    licenses, found = notices.collect_files([("LICENSE", a), ("COPYING", b), ("NOTICE.txt", n)])
    assert [s.name for s in licenses] == ["COPYING"]  # 이름순으로 먼저 온 것만 남는다
    assert licenses[0].text == "text\nline\n"
    assert [s.name for s in found] == ["NOTICE.txt"]


# ---- 잠금 파일 -> 제품 의존 선별

def test_npm_product_paths_excludes_dev_and_devoptional(tmp_path: Path) -> None:
    lock = {
        "packages": {
            "": {"name": "root"},
            "node_modules/prod": {"version": "1.0.0", "license": "MIT"},
            "node_modules/tool": {"version": "1.0.0", "license": "MIT", "dev": True},
            "node_modules/both": {"version": "1.0.0", "license": "MIT", "devOptional": True},
            "node_modules/a/node_modules/nested": {"version": "2.0.0", "license": "MIT"},
        }
    }
    path = write(tmp_path, "package-lock.json", json.dumps(lock))
    assert sorted(notices.npm_product_paths(path)) == ["node_modules/a/node_modules/nested", "node_modules/prod"]


def _npm_tree(root: Path, name: str, files: dict[str, str], meta: dict[str, object] | None = None) -> None:
    write(root, f"node_modules/{name}/package.json", json.dumps(meta or {"name": name, "author": {"name": "Alice"}}))
    for file_name, body in files.items():
        write(root, f"node_modules/{name}/{file_name}", body)


def test_npm_entries_read_license_and_notice_files(tmp_path: Path) -> None:
    _npm_tree(tmp_path, "prod", {"LICENSE": MIT, "NOTICE": NOTICE, "README.md": "ignored"})
    product = {"node_modules/prod": {"version": "1.0.0", "license": "Apache-2.0"}}
    [entry] = notices.npm_entries_from(tmp_path, product, {})
    assert (entry.name, entry.version, entry.license, entry.authors) == ("prod", "1.0.0", "Apache-2.0", "Alice")
    assert [s.name for s in entry.licenses] == ["LICENSE"]
    assert [s.name for s in entry.notices] == ["NOTICE"]


def test_npm_missing_license_file_fails_and_override_fixes(tmp_path: Path) -> None:
    _npm_tree(tmp_path, "bare", {"README.md": "x"})
    product = {"node_modules/bare": {"version": "1.0.0", "license": "MIT"}}
    with pytest.raises(notices.NoticesError, match=re.escape("npm bare 1.0.0: 라이선스 전문 파일이 패키지에 없다")):
        notices.npm_entries_from(tmp_path, product, {})
    [entry] = notices.npm_entries_from(tmp_path, product, {("npm", "bare", "MIT"): MIT})
    assert entry.licenses[0].text == MIT
    # 라이선스 식별자가 바뀌면 대체 전문은 적용되지 않는다
    with pytest.raises(notices.NoticesError):
        notices.npm_entries_from(tmp_path, {"node_modules/bare": {"version": "1.0.0", "license": "ISC"}}, {("npm", "bare", "MIT"): MIT})


def test_npm_package_not_installed_fails(tmp_path: Path) -> None:
    with pytest.raises(notices.NoticesError, match="설치된 폴더가 없다"):
        notices.npm_entries_from(tmp_path, {"node_modules/ghost": {"version": "1.0.0", "license": "MIT"}}, {})


def _site(root: Path, name: str, version: str, files: dict[str, str]) -> Path:
    site = root / "site-packages"
    site.mkdir(exist_ok=True)
    for file_name, body in files.items():
        write(site, f"{name}-{version}.dist-info/{file_name}", body)
    return site


def test_python_entries_read_all_pep639_files_and_skip_own_packages(tmp_path: Path) -> None:
    _site(tmp_path, "dep_one", "1.2.3", {"licenses/LICENSE": MIT, "licenses/LICENSE.PSF": "PSF text\n", "licenses/NOTICE": NOTICE})
    site = _site(tmp_path, "openit_example", "0.1.0", {"licenses/LICENSE": "ours"})
    rows = [
        {"Name": "dep-one", "Version": "1.2.3", "License": "MIT AND PSF-2.0", "Author": "Alice", "URL": "UNKNOWN"},
        {"Name": "openit-example", "Version": "0.1.0", "License": "MIT", "Author": "x", "URL": "x"},
    ]
    [entry] = notices.python_entries_from(rows, site, {"openit-example"}, {})
    assert entry.name == "dep-one"
    assert [s.name for s in entry.licenses] == ["LICENSE", "LICENSE.PSF"]  # pip-licenses 가 하나만 주는 것을 모두 담는다
    assert [s.name for s in entry.notices] == ["NOTICE"]
    assert entry.url == ""


def test_python_missing_license_file_fails(tmp_path: Path) -> None:
    site = _site(tmp_path, "nolic", "1.0", {"METADATA": "Name: nolic\n"})
    rows = [{"Name": "nolic", "Version": "1.0", "License": "MIT", "Author": "UNKNOWN", "URL": "UNKNOWN"}]
    with pytest.raises(notices.NoticesError, match=re.escape("python nolic 1.0: 라이선스 전문 파일이 패키지에 없다")):
        notices.python_entries_from(rows, site, set(), {})


def test_own_python_packages_come_from_uv_lock_sources(tmp_path: Path) -> None:
    lock = write(
        tmp_path, "uv.lock",
        '[[package]]\nname = "Mine_Pkg"\nsource = { editable = "." }\n\n[[package]]\nname = "dep"\nsource = { registry = "https://pypi.org/simple" }\n',
    )  # fmt: skip
    assert notices._own_python_packages(lock) == {"mine-pkg"}  # pyright: ignore[reportPrivateUsage]


def test_text_overrides_need_reason_and_text(tmp_path: Path) -> None:
    ok = write(tmp_path, "ok.toml", '[[text]]\necosystem="npm"\nname="x"\nlicense="MIT"\nreason="r"\ntext="body"\n')
    assert notices.load_text_overrides(ok) == {("npm", "x", "MIT"): "body\n"}
    bad = write(tmp_path, "bad.toml", '[[text]]\necosystem="npm"\nname="x"\nlicense="MIT"\nreason=""\ntext="body"\n')
    with pytest.raises(ValueError, match="reason"):
        notices.load_text_overrides(bad)


# ---- 영역 점검: 누락·불일치

DOCKERFILE_SERVICE = f"FROM base AS build\nRUN true\nFROM base AS runtime\nCOPY {notices.NOTICES_FILE} {notices.DOC_PATH}\n"
DOCKERFILE_WEB = DOCKERFILE_SERVICE + f"COPY {notices.NOTICES_FILE} {notices.WEB_PUBLIC_PATH}\n"


def _area(root: Path, kind: str = "service", notices_text: str | None = "BODY\n", dockerfile: str | None = None) -> Path:
    folder = "services" if kind == "service" else "web"
    area = root / folder / "demo"
    write(area, "Dockerfile", dockerfile or (DOCKERFILE_SERVICE if kind == "service" else DOCKERFILE_WEB))
    write(area, "uv.lock" if kind == "service" else "package-lock.json", "")
    if notices_text is not None:
        write(area, notices.NOTICES_FILE, notices_text)
    return area


def _generate_returning(text: str) -> Callable[..., str]:
    def generate(area: Path, overrides: object = None) -> str:
        return text

    return generate


@pytest.fixture
def fake_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notices, "generate", _generate_returning("BODY\n"))


@pytest.mark.usefixtures("fake_generate")
@pytest.mark.parametrize("kind", ["service", "web"])
def test_area_ok(tmp_path: Path, kind: str) -> None:
    area = _area(tmp_path, kind)
    assert notices.verify_area(tmp_path, kind, area) == []


@pytest.mark.usefixtures("fake_generate")
def test_missing_notices_file_fails(tmp_path: Path) -> None:
    area = _area(tmp_path, notices_text=None)
    [violation] = notices.verify_area(tmp_path, "service", area)
    assert "THIRD_PARTY_NOTICES 가 없다" in violation.message


@pytest.mark.usefixtures("fake_generate")
def test_stale_notices_fail(tmp_path: Path) -> None:
    area = _area(tmp_path, notices_text="- old 1.0 (MIT)\n")
    [violation] = notices.verify_area(tmp_path, "service", area)
    assert "잠금 파일과 어긋난다" in violation.message


def test_package_lines_ignore_list_items_inside_license_text() -> None:
    text = notices.render("python", "uv.lock", [_entry("alpha", text="MIT\n- Alice\n- Bob\nCopyright (c) 2020 A\n")])
    assert notices._package_lines(text) == {"- alpha 1.0.0 (MIT)"}  # pyright: ignore[reportPrivateUsage]


def test_stale_notices_report_package_difference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notices, "generate", _generate_returning(notices.render("python", "uv.lock", [_entry("new", "2.0")])))
    area = _area(tmp_path, notices_text=notices.render("python", "uv.lock", [_entry("old", "1.0")]))
    [violation] = notices.verify_area(tmp_path, "service", area)
    assert "잠금 파일에만 있음 1개, 고지에만 있음 1개" in violation.message


def test_generation_error_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(area: Path, overrides: object = None) -> str:
        raise notices.NoticesError("python x 1.0: 라이선스 전문 파일이 패키지에 없다")

    monkeypatch.setattr(notices, "generate", boom)
    area = _area(tmp_path)
    [violation] = notices.verify_area(tmp_path, "service", area)
    assert "라이선스 전문 파일이 패키지에 없다" in violation.message


@pytest.mark.usefixtures("fake_generate")
def test_missing_lock_fails(tmp_path: Path) -> None:
    area = _area(tmp_path)
    (area / "uv.lock").unlink()
    assert any("잠금 파일" in v.message for v in notices.verify_area(tmp_path, "service", area))


@pytest.mark.usefixtures("fake_generate")
def test_dockerfile_without_copy_fails(tmp_path: Path) -> None:
    area = _area(tmp_path, dockerfile="FROM base AS runtime\nRUN true\n")
    [violation] = notices.verify_area(tmp_path, "service", area)
    assert "COPY THIRD_PARTY_NOTICES" in violation.message


@pytest.mark.usefixtures("fake_generate")
def test_copy_in_build_stage_only_fails(tmp_path: Path) -> None:
    area = _area(tmp_path, dockerfile=f"FROM base AS build\nCOPY {notices.NOTICES_FILE} /x\nFROM base AS runtime\nRUN true\n")
    assert notices.verify_area(tmp_path, "service", area)  # 마지막 단계(이미지에 남는 단계)에 있어야 한다


@pytest.mark.usefixtures("fake_generate")
def test_web_needs_both_paths(tmp_path: Path) -> None:
    area = _area(tmp_path, "web", dockerfile=DOCKERFILE_SERVICE)
    [violation] = notices.verify_area(tmp_path, "web", area)
    assert notices.WEB_PUBLIC_PATH in violation.message


@pytest.mark.usefixtures("fake_generate")
def test_dockerignore_excluding_notices_fails(tmp_path: Path) -> None:
    area = _area(tmp_path)
    write(area, ".dockerignore", "tests\nTHIRD_*\n")
    [violation] = notices.verify_area(tmp_path, "service", area)
    assert ".dockerignore" in violation.message


@pytest.mark.usefixtures("fake_generate")
def test_run_covers_every_area_and_templates(tmp_path: Path) -> None:
    _area(tmp_path, "service")
    _area(tmp_path, "web")
    write(tmp_path, "templates/service/Dockerfile", "FROM base AS runtime\n")
    violations = notices.run(tmp_path)
    assert [v.where for v in violations] == ["templates/service/Dockerfile"]


# ---- 이 리포의 영역과 템플릿

def test_repo_examples_and_templates_are_consistent(repo: Path) -> None:
    for kind, area in notices.area_folders(repo):
        assert notices.dockerfile_violations(area / "Dockerfile", kind, str(area)) == []
        assert (area / notices.NOTICES_FILE).is_file()
    for kind in notices.KIND_FOLDERS:
        assert notices.dockerfile_violations(repo / "templates" / kind / "Dockerfile", kind, kind) == []


def test_repo_notices_cover_product_dependencies_only(repo: Path) -> None:
    python = (repo / "services" / "_example" / notices.NOTICES_FILE).read_text(encoding="utf-8")
    assert "- fastapi " in python
    assert "- pytest " not in python  # 개발 의존(dev 그룹)은 이미지에 없다
    assert "- ruff " not in python
    web = (repo / "web" / "_example" / notices.NOTICES_FILE).read_text(encoding="utf-8")
    assert "- react " in web
    assert "- vite " not in web  # devDependencies
    assert "- vitest " not in web


# ---- 이미지

def _fake_extract(content: dict[str, bytes | None]) -> Callable[..., dict[str, Path]]:
    def extract(root: Path, image: str, paths: Iterable[str], into: Path) -> dict[str, Path]:
        out: dict[str, Path] = {}
        for index, path in enumerate(paths):
            body = content.get(path)
            if body is None:
                raise notices.NoticesError(f"이미지 {image} 에 {path} 가 없다")
            target = into / str(index)
            target.write_bytes(body)
            out[path] = target
        return out

    return extract


@pytest.mark.usefixtures("fake_generate")
def test_image_ok_missing_and_different(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    area = _area(tmp_path)
    monkeypatch.setattr(notices, "extract_from_image", _fake_extract({notices.DOC_PATH: b"BODY\n"}))
    assert notices.verify_image(tmp_path, area, "img") == []
    monkeypatch.setattr(notices, "extract_from_image", _fake_extract({}))
    [missing] = notices.verify_image(tmp_path, area, "img")
    assert "가 없다" in missing.message
    monkeypatch.setattr(notices, "extract_from_image", _fake_extract({notices.DOC_PATH: b"OTHER\n"}))
    [different] = notices.verify_image(tmp_path, area, "img")
    assert "다르다" in different.message


@pytest.mark.usefixtures("fake_generate")
def test_image_check_fails_when_area_notices_are_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    area = _area(tmp_path, notices_text="STALE\n")
    monkeypatch.setattr(notices, "extract_from_image", _fake_extract({notices.DOC_PATH: b"STALE\n"}))
    [violation] = notices.verify_image(tmp_path, area, "img")  # 이미지가 영역 파일과 같아도 영역 파일이 잠금 파일과 다르면 실패
    assert "잠금 파일과 어긋난다" in violation.message


@pytest.mark.usefixtures("fake_generate")
def test_web_image_needs_public_copy_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    area = _area(tmp_path, "web")
    monkeypatch.setattr(notices, "extract_from_image", _fake_extract({notices.DOC_PATH: b"BODY\n"}))
    [violation] = notices.verify_image(tmp_path, area, "img")
    assert notices.WEB_PUBLIC_PATH in violation.message


# ---- 명령

@pytest.mark.usefixtures("fake_generate")
def test_cli_generate_writes_file(tmp_path: Path) -> None:
    area = _area(tmp_path, notices_text=None)
    assert notices_main(["--root", str(tmp_path), "generate", str(area)]) == 0
    assert (area / notices.NOTICES_FILE).read_text(encoding="utf-8") == "BODY\n"


def test_cli_generate_failure_is_rc1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(area: Path, overrides: object = None) -> str:
        raise notices.NoticesError("x")

    monkeypatch.setattr(notices, "generate", boom)
    area = _area(tmp_path, notices_text=None)
    assert notices_main(["--root", str(tmp_path), "generate", str(area)]) == 1
    assert not (area / notices.NOTICES_FILE).exists()


@pytest.mark.usefixtures("fake_generate")
def test_openit_check_notices_rc(tmp_path: Path) -> None:
    _area(tmp_path)
    assert main(["notices", "--root", str(tmp_path)]) == 0
    (tmp_path / "services" / "demo" / notices.NOTICES_FILE).unlink()
    assert main(["notices", "--root", str(tmp_path)]) == 1
