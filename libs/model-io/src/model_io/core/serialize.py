"""모델 입력 직렬화(D77): 학습 데이터의 user 메시지와 글자(바이트)까지 같은 JSON 글자를 만든다.

규칙(계약 ModelInputSerialization): `json.dumps(obj, ensure_ascii=False)` 와 같은 글자(기본 구분자, 비 ASCII 그대로).
모델 입출력 v2: A 는 최상위 키를 코드 포인트 순으로 정렬하고 state 안은 요청이 정한 순서, B 는 모든 수준을 정렬한다.
모델 입출력 v3(계약 ModelInputSerializationV3): A·B 모두 모든 수준을 정렬한다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from model_io.core.jsonvalue import as_map

# 왜 value 가 앞인가: 정본 labels.py a_state 가 {"value": ..., "status": ...} 순서로 만들고 계약 StateEntryKeyOrder 가
# 이 순서를 정한다. 학습 파일 final 의 state 항목 90,416개가 이 순서다(평가 파일 finaltest 의 status, value 는 DC-09)
_STATE_ENTRY_ORDER = ("value", "status")
_SAFE_INTEGER = 2**53
MODEL_IO_V2 = "model-io-v2"
MODEL_IO_V3 = "model-io-v3"
# 왜 두 버전만: 계약 ModelIoVersion 의 값이다. 모르는 버전은 글자를 정할 수 없어 거부한다
# (서버는 그 패키지를 적재하지 않는다)
MODEL_IO_VERSIONS = (MODEL_IO_V2, MODEL_IO_V3)


def _plain_number(value: object) -> object:
    """정수로 읽힌 수(15.0)는 정수 글자로 쓴다. 계약 값은 수를 실수로 읽어 15 가 15.0 이 되므로 원래 글자를 되찾는다.

    왜 안전한가: 학습 파일 46655행의 입력과 출력 어디에도 `15.0` 같은 글자가 없다(실측). 정수 수와 소수 수만 있다.
    """
    if isinstance(value, float) and value.is_integer() and abs(value) < _SAFE_INTEGER:
        return int(value)
    return value


def _entry(raw: object) -> dict[str, object]:
    entry = as_map(raw) or {}
    return {name: _plain_number(entry[name]) for name in _STATE_ENTRY_ORDER if name in entry}


def serialize_extraction_input(
    payload: Mapping[str, object], state_key_order: Sequence[str], *, model_io_version: str = MODEL_IO_V2
) -> str:
    """LoRA-A 입력(ActionExtractionInput 을 JSON 으로 푼 모양)의 모델 입력 글자.

    v2: state 의 칸 순서는 `state_key_order` 가 정한다(JSON 객체에는 순서가 없다, RFC 8259 4).
    순서에 없는 칸은 뒤에 사전 순으로 붙는다. v3: 모든 수준을 정렬하므로 `state_key_order` 를 쓰지 않는다.
    """
    if model_io_version not in MODEL_IO_VERSIONS:
        raise ValueError(f"모르는 모델 입출력 버전: {model_io_version}")
    state = as_map(payload.get("state")) or {}
    if model_io_version == MODEL_IO_V3:
        # 왜 정렬: dataset1118 의 A 입력 68,817행이 모두 sort_keys 직렬화와 바이트까지 같다
        # (계약 ModelInputSerializationV3)
        body3: dict[str, object] = {name: payload[name] for name in payload if name != "state"}
        body3["state"] = {key: _entry(state[key]) for key in state}
        return json.dumps(body3, ensure_ascii=False, sort_keys=True)
    ordered = [key for key in state_key_order if key in state]
    ordered += sorted(key for key in state if key not in ordered)
    body: dict[str, object] = {name: payload[name] for name in sorted(payload) if name != "state"}
    body["state"] = {key: _entry(state[key]) for key in ordered}
    return json.dumps(dict(sorted(body.items())), ensure_ascii=False)


def serialize_response_input(payload: Mapping[str, object]) -> str:
    """LoRA-B 입력(ResponseRequest 를 JSON 으로 푼 모양)의 모델 입력 글자. 모든 수준의 키를 정렬한다."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
