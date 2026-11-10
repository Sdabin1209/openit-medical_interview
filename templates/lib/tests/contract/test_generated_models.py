"""생성된 계약 타입이 쓸 수 있는 모양인지 본다. `schemas` 에 스키마를 더하면 그 모델을 여기서 시험한다."""

import enum
import importlib
import inspect


def test_generated_types_are_pydantic_models_or_enums() -> None:
    models = importlib.import_module("__PKG__.contract.models")
    for name, cls in inspect.getmembers(models, inspect.isclass):
        if cls.__module__ == models.__name__:
            assert hasattr(cls, "model_validate") or issubclass(cls, enum.Enum), name
