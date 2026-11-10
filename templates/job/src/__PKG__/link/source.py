"""이 잡이 일감을 가져오는 곳(템플릿 예시). 영역 밖과 통신하는 일은 link 만 한다(ADR 0003).

실제 영역에서는 이웃 영역의 SDK·클라이언트나 저장소에서 읽는다. 이 예시는 통신 없이 고정 값을 낸다.
"""

from __PKG__.types import StepInput


def fetch_step_input() -> StepInput:
    """이번 실행의 입력을 가져온다."""
    return StepInput(items=("a", "b", "c"))
