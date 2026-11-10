"""항목 세기 컴포넌트(템플릿 예시). 자기 입력(StepInput)과 출력(StepOutput)과 할 일만 안다."""

from example_job.types import StepInput, StepOutput


def count_items(step: StepInput) -> StepOutput:
    """항목 수를 센다(실제 영역에서는 자기 단계의 일로 바꾼다)."""
    return StepOutput(processed_count=len(step.items))
