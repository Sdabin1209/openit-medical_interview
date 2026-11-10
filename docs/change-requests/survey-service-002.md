# survey-service-002: 모델 입력의 글 조각(topic, known, ask, previous, current, hold)과 state 의 참조 문항을 만들 정본이 계약에 없다

## 상태
요청(2026-11-10, survey-service 작업자). 대상: 헤드.

## 무엇이 어긋나나(읽어서 확인한 것)
- `ResponseRequest` 는 topic(TopicText), known, ask, previous, current, hold 를 사람 말 글로 요구한다. 데이터셋 정본 `labels.py` 는 이것을 31문항에 고정된 표(`DISEASE`, `TOBACCO`, `ask_text`, `previous_text` 등)로 만든다. `IO_SPEC.md` 3장은 서비스가 '표 찾기'로 붙인다고 쓰고 7장 2번은 칸 설명표와 ask 문장 틀 표를 '확인 후' 만든다고 남겼다.
- 계약 `QuestionSetContent`(문항 세트 업로드)는 질문 문장과 칸 규격만 갖고 칸 설명이나 문장 틀이 없다. `design.md` 2절은 `labels.py` 의 규칙이 model-runtime 에만 닿는다고 정한다.
- `IO_SPEC.md` 2.1 의 `state` 는 '참조 원천 문항(REF_SOURCE)'의 저장 값도 싣는다. 이 목록(어느 문항이 어느 문항을 참조하나)은 계약 문항 세트에 없다.

## 영역이 지금 한 것
영역은 올라온 문항 세트의 질문 문장과 칸 규격에서만 글 조각을 만들고(영역 ADR 0003), state 는 지금 문항과 직전 문항의 값만 싣는다. 모델이 학습한 분포와 다르므로 응답 품질은 측정하지 않았고 보증하지 않는다.

## 요청
둘 중 하나를 정해 달라.
1. 칸 설명표·ask 문장 틀 표·참조 문항 목록을 문항 세트 업로드 값(`QuestionSetContent`)에 싣게 계약을 바꾼다. 그러면 서비스가 문항 세트에서 정확한 글을 만든다.
2. 글 조각 만들기를 model-runtime 의 책임으로 옮긴다(요청에는 문항 식별자와 값만 보낸다). 그러면 `ResponseRequest` 의 해당 칸이 계약에서 사라진다.

## 하지 않은 것
계약과 생성물을 영역에서 고치지 않았다(계약은 동결이고 계약 타입은 생성 명령으로만 만든다).
