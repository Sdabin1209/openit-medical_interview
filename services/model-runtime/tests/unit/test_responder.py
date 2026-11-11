import pytest

from model_runtime.components.responder import SentenceStream, validate_sentence
from model_runtime.contract.models import ProblemReason
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


def test_stream_accepts_fragments_unchanged_up_to_the_limit() -> None:
    sentence = SentenceStream()
    assert [sentence.accept(" 가"), sentence.accept(""), sentence.accept("나" * 342)] == [" 가", None, "나" * 342]
    assert len(sentence.finish()) == 344


def test_stream_rejects_the_fragment_that_passes_the_limit_and_empty_end() -> None:
    sentence = SentenceStream()
    sentence.accept("가" * 344)
    with pytest.raises(ServiceFault) as over:
        sentence.accept("나")
    assert (over.value.status, over.value.reason) == (503, ProblemReason.OUTPUT_INVALID)
    with pytest.raises(ServiceFault) as empty:
        SentenceStream().finish()
    assert empty.value.reason is ProblemReason.OUTPUT_INVALID
