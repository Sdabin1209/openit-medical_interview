"""__AREA__ 공유 라이브러리의 공개 API. 여기 `__all__` 에 적은 것만 밖에서 쓴다(ADR 0020).

구현은 `core/`, 계약에서 생성한 타입은 `contract/` 에 있다. 밖(영역)은 `core`·`contract` 를 직접 import 하지 않는다.
"""

__all__: list[str] = []
