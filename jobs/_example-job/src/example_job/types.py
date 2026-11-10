"""영역 안 컴포넌트 사이를 오가는 값(ADR 0003). 칸마다 description 과 제약을 둔다."""

from pydantic import BaseModel, ConfigDict, Field


class StepInput(BaseModel):
    """잡 단계의 입력(템플릿 예시. 실제 영역에서는 자기 값으로 바꾼다)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[str, ...] = Field(max_length=10_000, description="이번 실행이 처리할 항목들.")


class StepOutput(BaseModel):
    """잡 단계의 출력(템플릿 예시)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    processed_count: int = Field(ge=0, le=10_000, description="처리한 항목 수. JobRunResult.processed_count 가 된다.")
