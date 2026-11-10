"""프로파일 표(OPENIT_MODEL_PROFILE 이 고르는 이름 -> 기반 모델)를 읽는다(ADR 0007).

표는 이 영역의 값이라 영역이 소유한다(계약 ModelProfileName 설명, 구조 규칙 5). 파일 `profiles.json` 이 패키지와
함께 배포된다.
"""

from __future__ import annotations

from importlib import resources

from pydantic import BaseModel, ConfigDict

from model_runtime.contract.models import BaseModelName


class ModelProfile(BaseModel):
    """프로파일 하나. 지금은 기반 모델뿐이다(서빙 크기는 GPU 에서 잰 값이 생기면 칸을 더한다, ADR 0007)."""

    model_config = ConfigDict(extra="forbid")
    base_model: BaseModelName


class ProfileTable(BaseModel):
    """프로파일 표 파일의 모양."""

    model_config = ConfigDict(extra="forbid")
    profiles: dict[str, ModelProfile]


class UnknownProfileError(LookupError):
    """프로파일 표에 없는 이름이다(설정 오류. 서버가 시작하지 않는다)."""


def load_profile(name: str, table_text: str | None = None) -> ModelProfile:
    """name 의 프로파일. table_text 가 없으면 패키지에 든 표를 읽는다."""
    text = (
        table_text
        if table_text is not None
        else resources.files("model_runtime").joinpath("profiles.json").read_text("utf-8")
    )
    table = ProfileTable.model_validate_json(text)
    try:
        return table.profiles[name]
    except KeyError as error:
        raise UnknownProfileError(
            f"프로파일 {name} 이 표에 없다. 있는 이름: {', '.join(sorted(table.profiles))}"
        ) from error
