# 변경 요청 model-runtime-001: 계약 문구와 데이터셋 정본의 차이 두 가지

> **처리됨(contracts-v8.0.0).** 계약 쪽 반영: 1절(next_item 규칙은 labels.py a_target·next_after 대로), 2절(ModelInputSerialization 에 state 항목 키 순서 value, status), 4절(빈 반복 키는 저장하지 않는 값에만). 3절은 알림이다. 평가 파일 finaltest 의 키 순서는 데이터셋 변경 요청 DC-09 로 넘어갔다.

- 영역: model-runtime(libs/model-io)
- 대상 계약: `contracts/components.yaml` 의 `NextItemRuleKind`, `ModelInputSerialization`
- 상태: 헤드 결정 대기. 그동안 코드는 데이터셋 정본을 따른다(ADR libs/model-io 0002).

## 1. `SEQUENCE_AFTER_SAVED` 의 설명이 정본과 다르다
- 계약: "저장한 칸 중 순서표에서 가장 뒤 문항의 다음 문항(건너뛰기 적용, 끝이면 END)".
- 정본(`contracts/inputs/labels.py` `a_target`, `next_after`): 기준 문항은 `values` 의 **첫 값의 문항**(없으면 `targets` 의 첫 문항, 없으면 묻던 문항)이다. 그 문항 다음으로 가되 (a) 이번에 저장한 값으로 조건이 맞은 건너뛰기 분기가 뛰어넘는 문항과 (b) 이번 턴에 **칸이 모두** 저장된 뒤 문항은 건너뛴다. 칸 일부만 저장된 문항은 남은 칸을 물어야 하므로 건너뛰지 않는다.
- 측정(학습 서버 final·finaltest A 정답 46655건, 순서표와 칸 규격은 `question_items`, `question_fields`, 건너뛰기는 labels.py 규칙):
  - 정본 방식: 불일치 0건.
  - 계약 문구 방식(저장한 칸 중 가장 뒤 문항): 불일치 168건. 예: `Q5.answer` 와 `Q5_1.status` 를 함께 저장한 NEXT 의 정답은 `Q5_1`(칸 일부만 저장)인데 계약 문구는 `Q6` 을 낸다.
- 요청: 설명을 정본 규칙으로 고친다. 구현은 정본대로 되어 있다.

## 2. `ModelInputSerialization` 이 state 항목 안의 키 순서를 정하지 않는다
- 계약은 최상위 키(알파벳 순)와 state 의 칸 순서(요청의 `state_key_order`)만 정한다. state 항목(`{value, status}`)의 두 키 순서는 없다.
- 측정:
  - 학습 파일 `final`(학습·검증·시험) A 입력 44563행: 항목 90,416개 모두 `value`, `status` 순서이고 정본 `labels.py a_state` 와 같다.
  - 평가 파일 `finaltest` 2092행 중 2000행: 항목 4,215개가 `status`, `value` 순서(정렬된 키). 나머지 92행은 state 가 비어 있다.
  - 서빙이 어느 쪽을 쓰느냐에 따라 모델 입력 글자가 달라진다. 어댑터는 `final` 형식으로 학습했다고 보고 `value`, `status` 순서로 구현했다(확인하지 못함: 어댑터 학습에 쓴 파일은 GPU 서버에서 본 것이 아니다).
- 요청: `ModelInputSerialization` 에 항목 안 키 순서를 명시하고 평가 집합(finaltest)의 형식을 데이터셋 담당과 맞춘다.

## 3. 참고: 정렬되지 않은 B 입력 10행
학습 파일 B 입력 46774행 중 10행(학습 4·3행과 시험 3행. 모두 action NEXT 이고 `known` 이 "1년 기준", "일주일 기준", "한 달 기준" 인 Q7 기준 기간 행)은 계약의 "B 는 모든 수준 정렬"을 따르지 않고 `action, topic, user_utterance, known, next` 순서로 들어 있다. 서빙은 계약대로 정렬한다. 요청이 아니라 알림이다.

## 4. `RepeatKey` 가 빈 반복 키를 받지 않는다(데이터셋은 빈 키를 쓴다)
- 계약 `RepeatKey` 의 패턴은 `^[a-z]+$` 라 `QuestionFieldSpec.repeat_keys` 에 빈 키를 쓸 수 없다. 데이터셋 참조 DB(2026-10-28 판)는 Q7_1·Q7_2 의 반복 키에 `""`(술 종류 미정)를 더했고, SQL.md 5.2 는 술 종류 다섯만 적는다.
- 측정: 학습 파일 정답 46655행의 Q7_1·Q7_2 칸 값 중 키에 `[술 종류]` 가 없는 것이 6842개(값 3842, 대상 포함)이고 모두 `save` 가 거짓이다. 저장하는 키 없는 값은 0개다. SQL.md 6장도 키 없는 값은 저장하지 않는다고 적는다.
- 구현: 검증기는 칸 규격의 반복 키(술 종류 다섯)에 더해 **저장하지 않는 값의 빈 키**를 허용한다. 저장하는 값에 키가 없으면 UNKNOWN_SLOT 이다. 이 규칙이 계약 `QuestionFieldSpec` 설명에 없다.
- 요청: `QuestionFieldSpec.repeat_keys` 설명에 위 규칙(빈 키는 저장하지 않는 값에만)을 적는다.
