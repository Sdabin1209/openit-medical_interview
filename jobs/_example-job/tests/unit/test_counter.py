import pytest
from pydantic import ValidationError

from example_job.components.counter import count_items
from example_job.types import StepInput


def test_count_items() -> None:
    assert count_items(StepInput(items=("a", "b"))).processed_count == 2


def test_input_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        StepInput.model_validate({"items": [], "extra": 1})
