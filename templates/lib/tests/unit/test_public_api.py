import importlib

import __PKG__


def test_all_names_resolve() -> None:
    for name in __PKG__.__all__:
        assert hasattr(__PKG__, name), name


def test_all_is_sorted_and_unique() -> None:
    assert sorted(set(__PKG__.__all__)) == __PKG__.__all__


def test_public_names_have_docstrings() -> None:
    for name in __PKG__.__all__:
        assert getattr(__PKG__, name).__doc__, f"{name} 에 설명이 없다"


def test_contract_module_imports() -> None:
    assert importlib.import_module("__PKG__.contract.models") is not None
