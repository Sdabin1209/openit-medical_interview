import pytest

from model_runtime.components.responder import validate_sentence
from model_runtime.types import ServiceFault


def test_valid_sentence_is_trimmed() -> None:
    assert validate_sentence("  진단 받으셨군요.\n") == "진단 받으셨군요."


@pytest.mark.parametrize("raw", ["", "   ", "가" * 345, '{"text": "안녕"}', '["안녕"]', "안녕\x00하세요"])
def test_unusable_output_is_503(raw: str) -> None:
    with pytest.raises(ServiceFault) as info:
        validate_sentence(raw)
    assert info.value.status == 503 and info.value.retry_after


def test_boundary_length_is_accepted() -> None:
    assert len(validate_sentence("가" * 344)) == 344
