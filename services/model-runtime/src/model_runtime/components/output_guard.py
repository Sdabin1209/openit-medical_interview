"""output_guard: LoRA-A 출력을 검증하고 값을 고쳐 쓴다(D115). 검증된 출력 또는 출력 불가를 낸다.

규칙은 `libs/model-io` 에 있고 model-lab 의 평가와 같은 것이다(D97). 이 컴포넌트가 한 번 검사하고 받는 쪽은 다시
검증하지 않는다(R7).
"""

from __future__ import annotations

from model_io import GuardContext, build_field_index, build_flow_index, check_extraction_output

from model_runtime.types import GuardedExtraction, GuardRequest


def guard(request: GuardRequest) -> GuardedExtraction:
    """모델 출력 글자를 검증한다. 출력 불가이면 output 이 None 이다. 위반 코드는 고쳐 쓰기 전 출력으로 센 것이다."""
    context = GuardContext(
        request.asked_item,
        build_flow_index(request.flow),
        build_field_index(request.fields),
        request.state,
        model_io_version=request.model_io_version,
    )
    outcome = check_extraction_output(request.raw, context)
    return GuardedExtraction(
        output=outcome.output,
        violation_codes=[violation.code.value for violation in outcome.violations],
        rewrites=[rewrite.value for rewrite in outcome.rewrites],
    )
