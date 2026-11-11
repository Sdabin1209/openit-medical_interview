import pytest

from model_runtime.components.responder import SentenceStream, validate_sentence
from model_runtime.contract.models import ProblemReason, ResponseSentence
from model_runtime.types import ServiceFault


def test_valid_sentence_is_trimmed() -> None:
    assert validate_sentence("  진단 받으셨군요.\n") == "진단 받으셨군요."


@pytest.mark.parametrize(
    "raw", ["", "   ", "가" * 345, '{"text": "안녕"}', '["안녕"]', "안녕\x00하세요", "안녕\x1c", "\x1b안녕"]
)
def test_unusable_output_is_503(raw: str) -> None:
    with pytest.raises(ServiceFault) as info:
        validate_sentence(raw)
    assert info.value.status == 503 and info.value.retry_after


def test_boundary_length_is_accepted() -> None:
    assert len(validate_sentence("가" * 344)) == 344


def test_stream_holds_leading_whitespace_and_sends_held_trailing_whitespace_with_the_next_letter() -> None:
    sentence = SentenceStream()
    got = [sentence.accept(piece) for piece in ["  ", "\n안", "녕 ", " ", "하\n", "세요. \n"]]
    assert got == [None, "안", "녕", None, "  하", "\n세요."]
    assert sentence.finish() == "안녕  하\n세요."  # 끝의 공백은 버린다


def test_stream_result_validates_as_response_sentence() -> None:
    sentence = SentenceStream()
    sentence.accept(" 가 ")
    sentence.accept("나 ")
    assert ResponseSentence.model_validate(sentence.finish()).root == "가 나"


def test_stream_counts_only_sent_characters_toward_344() -> None:
    sentence = SentenceStream()
    assert sentence.accept("가" * 344 + "  ") == "가" * 344  # 쥔 끝 공백은 길이에 넣지 않는다
    assert sentence.finish() == "가" * 344
    with pytest.raises(ServiceFault) as over:
        sentence.accept("나")
    assert (over.value.status, over.value.reason) == (503, ProblemReason.OUTPUT_INVALID)


@pytest.mark.parametrize("first", ["{", "[", '  {"a": 1}', "\n[1]"])
def test_stream_rejects_a_sentence_starting_with_brace_or_bracket(first: str) -> None:
    with pytest.raises(ServiceFault) as info:
        SentenceStream().accept(first)
    assert info.value.reason is ProblemReason.OUTPUT_INVALID


@pytest.mark.parametrize("fragment", ["안\x00녕", "\x1b", " \x1c", "안\x7f"])
def test_stream_rejects_control_characters_but_not_newline_or_tab(fragment: str) -> None:
    with pytest.raises(ServiceFault) as info:
        SentenceStream().accept(fragment)
    assert info.value.reason is ProblemReason.OUTPUT_INVALID
    assert SentenceStream().accept("안\n\t녕") == "안\n\t녕"


def test_stream_rejects_when_the_end_is_only_whitespace() -> None:
    sentence = SentenceStream()
    assert sentence.accept(" \n ") is None
    with pytest.raises(ServiceFault) as empty:
        sentence.finish()
    assert empty.value.reason is ProblemReason.OUTPUT_INVALID
