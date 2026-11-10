import importlib

import model_io


def test_all_names_resolve() -> None:
    for name in model_io.__all__:
        assert hasattr(model_io, name), name


def test_all_is_sorted_and_unique() -> None:
    assert sorted(set(model_io.__all__)) == model_io.__all__


def test_public_names_have_docstrings() -> None:
    for name in model_io.__all__:
        assert getattr(model_io, name).__doc__, f"{name} 에 설명이 없다"


def test_contract_module_imports() -> None:
    assert importlib.import_module("model_io.contract.models") is not None
