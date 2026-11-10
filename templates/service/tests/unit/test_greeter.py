import pytest
from pydantic import ValidationError

from __PKG__.components.greeter import greet
from __PKG__.types import GreetingRequest


def test_greet_uses_name() -> None:
    assert greet(GreetingRequest(name="다빈")).message == "안녕하세요, 다빈님"


def test_request_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        GreetingRequest(name="")


def test_request_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        GreetingRequest.model_validate({"name": "a", "extra": 1})
