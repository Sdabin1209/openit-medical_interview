"""영역 안 컴포넌트 사이를 오가는 값(ADR 0003). 칸마다 description 과 제약을 둔다."""

from pydantic import BaseModel, ConfigDict, Field


class GreetingRequest(BaseModel):
    """인사 요청(템플릿 예시. 실제 영역에서는 자기 값으로 바꾼다)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64, description="인사할 대상의 이름. 1~64자.")


class Greeting(BaseModel):
    """인사 결과(템플릿 예시)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str = Field(min_length=1, max_length=128, description="완성된 인사말.")
