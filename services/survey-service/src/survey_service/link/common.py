"""링크 컴포넌트가 함께 쓰는 작은 도구: JSON 응답, 쪽 나누기 질의, 문항 세트 읽기."""

from typing import Annotated
from uuid import UUID

from fastapi import Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from survey_service.contract.models import QuestionSetContent
from survey_service.link.problem import ApiError
from survey_service.types import InvalidCursorError, StoredQuestionSet

LimitQuery = Annotated[int, Query(ge=1, le=100, description="한 번에 받을 항목의 최대 개수(계약 PageLimit)")]
CursorQuery = Annotated[str | None, Query(max_length=96, description="다음 쪽 커서(계약 PageCursor)")]


def reply(model: BaseModel, status: int = 200) -> JSONResponse:
    """계약 값을 JSON 응답으로. 값이 없는 칸은 싣지 않는다."""
    return JSONResponse(model.model_dump(mode="json", exclude_none=True), status_code=status)


def content_of(stored: StoredQuestionSet) -> QuestionSetContent:
    """저장한 문항 세트의 내용(저장 전에 계약 검증을 마친 값이라 형식만 옮긴다)."""
    return QuestionSetContent.model_validate(stored.content)


def invalid_cursor() -> ApiError:
    """서버가 만들지 않은 커서(400)."""
    return ApiError(400, errors=[("/cursor", "서버가 만든 커서가 아니다")])


def parse_uuid(value: str) -> UUID | None:
    """UUID 글. 틀리면 None."""
    try:
        return UUID(value)
    except ValueError:
        return None


__all__ = ["ApiError", "InvalidCursorError", "content_of", "invalid_cursor", "parse_uuid", "reply"]
