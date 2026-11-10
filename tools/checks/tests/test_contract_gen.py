"""계약 타입 생성(openit-gen-contract)과 contract-drift 점검의 시험(ADR 0020)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from openit_checks import contract_gen
from openit_checks.contract_gen import Config, ContractGenError

CONTRACTS = """\
components:
  schemas:
    Name: {type: string, maxLength: 5, description: 이름, x-owner: head}
    Mode:
      type: string
      enum: [a, b]
      x-enum-descriptions: {a: 에이, b: 비}
      description: 모드
    Item:
      type: object
      additionalProperties: false
      required: [name]
      properties:
        name: {$ref: "#/components/schemas/Name", description: 이름}
        mode: {$ref: "#/components/schemas/Mode", description: 모드}
    Unused: {type: integer, description: 어디서도 안 쓴다}
    Other: {type: boolean, description: 다른 것}
  responses:
    Found:
      description: 찾음
      content: {application/json: {schema: {$ref: "#/components/schemas/Item"}}}
"""
OPENAPI = """\
openapi: 3.1.0
info: {title: t, version: "1"}
paths:
  /x:
    get:
      responses:
        "200": {$ref: "../components.yaml#/components/responses/Found"}
"""


def _repo(tmp: Path, pyproject: str = '[tool.openit.contract]\nopenapi = ["svc"]\n') -> Path:
    (tmp / "contracts/openapi").mkdir(parents=True)
    (tmp / "contracts/components.yaml").write_text(CONTRACTS, encoding="utf-8")
    (tmp / "contracts/openapi/svc.yaml").write_text(OPENAPI, encoding="utf-8")
    area = tmp / "services/svc"
    (area / "src/svc").mkdir(parents=True)
    (area / "src/svc/__init__.py").write_text("", encoding="utf-8")
    (area / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return area


def _generate(root: Path, area: Path) -> None:
    config = contract_gen.read_config(area)
    assert config is not None
    path = contract_gen.target_path(area)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contract_gen.generate_models(root / "contracts", config), encoding="utf-8")


def test_closure_follows_refs_through_responses_and_skips_unused(tmp_path: Path) -> None:
    _repo(tmp_path)
    names = contract_gen.collect_schema_names(tmp_path / "contracts", Config(("svc",), ()))
    assert names == ["Item", "Mode", "Name"]


def test_schema_names_add_to_openapi_closure(tmp_path: Path) -> None:
    _repo(tmp_path)
    names = contract_gen.collect_schema_names(tmp_path / "contracts", Config(("svc",), ("Other",)))
    assert names == ["Item", "Mode", "Name", "Other"]


def test_unknown_schema_name_is_an_error(tmp_path: Path) -> None:
    _repo(tmp_path)
    with pytest.raises(ContractGenError):
        contract_gen.collect_schema_names(tmp_path / "contracts", Config((), ("Nope",)))


def test_generated_models_are_pydantic_v2_with_constraints(tmp_path: Path) -> None:
    area = _repo(tmp_path)
    _generate(tmp_path, area)
    text = contract_gen.target_path(area).read_text(encoding="utf-8")
    assert "class Item(BaseModel)" in text and "max_length=5" in text and "extra='forbid'" in text
    assert "Unused" not in text and "x-owner" not in text


def test_same_contract_gives_same_output(tmp_path: Path) -> None:
    area = _repo(tmp_path)
    config = contract_gen.read_config(area)
    assert config is not None
    first = contract_gen.generate_models(tmp_path / "contracts", config)
    assert first == contract_gen.generate_models(tmp_path / "contracts", config)


def test_drift_is_clean_after_generation_and_fails_after_edit_or_contract_change(tmp_path: Path) -> None:
    area = _repo(tmp_path)
    assert len(contract_gen.python_drift(tmp_path)) == 1  # 생성물이 없다
    _generate(tmp_path, area)
    assert contract_gen.python_drift(tmp_path) == []
    target = contract_gen.target_path(area)
    target.write_text(target.read_text(encoding="utf-8") + "# 손으로 고침\n", encoding="utf-8")
    assert "다시 만든 결과와 다르다" in contract_gen.python_drift(tmp_path)[0].message
    _generate(tmp_path, area)
    components = tmp_path / "contracts/components.yaml"
    components.write_text(components.read_text(encoding="utf-8").replace("maxLength: 5", "maxLength: 6"), encoding="utf-8")
    assert len(contract_gen.python_drift(tmp_path)) == 1  # 계약이 바뀌었는데 다시 만들지 않았다


def test_empty_schema_list_gives_an_empty_models_file(tmp_path: Path) -> None:
    area = _repo(tmp_path, "[tool.openit.contract]\nschemas = []\n")
    _generate(tmp_path, area)
    assert contract_gen.python_drift(tmp_path) == []
    assert "class " not in contract_gen.target_path(area).read_text(encoding="utf-8")


def test_unknown_config_key_is_rejected(tmp_path: Path) -> None:
    area = _repo(tmp_path, '[tool.openit.contract]\nopenap = ["svc"]\n')
    with pytest.raises(ContractGenError):
        contract_gen.read_config(area)


def test_area_without_config_is_ignored(tmp_path: Path) -> None:
    area = _repo(tmp_path, "[project]\nname = 'x'\n")
    assert contract_gen.read_config(area) is None
    assert contract_gen.python_drift(tmp_path) == []


def test_real_repo_generated_files_are_current(repo: Path) -> None:
    """리포의 서비스·잡·라이브러리·템플릿 생성물이 지금 계약에서 다시 만든 결과와 같다(화면은 npm 이 필요해 openit-check 가 본다)."""
    assert contract_gen.python_drift(repo) == []


def test_cli_writes_models_file(tmp_path: Path) -> None:
    area = _repo(tmp_path)
    assert contract_gen.main([str(area), "--root", str(tmp_path)]) == 0
    assert (area / "src/svc/contract/models.py").is_file()


def test_gen_contract_entry_point_exists(repo: Path) -> None:
    assert shutil.which("uv")
    result = subprocess.run(
        ["uv", "run", "--project", str(repo / "tools/checks"), "--frozen", "openit-gen-contract", "--help"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 0


@pytest.mark.parametrize("area", sorted(p.stem for p in (Path(__file__).resolve().parents[3] / "contracts" / "openapi").glob("*.yaml")))
def test_every_real_area_openapi_closes_and_generates(area: str) -> None:
    """실제 계약의 영역 파일마다 참조 닫힘과 모델 생성이 된다(securitySchemes 등 스키마가 아닌 참조 포함)."""
    contracts = Path(__file__).resolve().parents[3] / "contracts"
    config = Config(openapi=(area,), schemas=())
    names = contract_gen.collect_schema_names(contracts, config)
    assert names, f"{area}: 닿는 스키마가 없다"
    assert "class " in contract_gen.generate_models(contracts, config)
