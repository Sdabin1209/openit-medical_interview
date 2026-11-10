import pytest
from pydantic import ValidationError

from __PKG__.components.counter import count_items
from __PKG__.types import StepInput


def test_count_items() -> None:
    assert count_items(StepInput(items=("a", "b"))).processed_count == 2


def test_input_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        StepInput.model_validate({"items": [], "extra": 1})
