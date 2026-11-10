# 변경 요청 model-runtime-004: 구조화된 요청으로 바꿀 때 서빙이 더 필요로 하는 값(survey-service 변경 요청 002 의 헤드 결정에 대한 답)

> **처리됨(contracts-v8.0.0).** 계약 쪽 반영: ExtractionRequest·ResponseGenerationRequest 가 구조화된 값(질문 문항, 직전 문항, 발화, 저장된 칸 slots, A 출력의 값·대상, next.text)을 싣는다. 서버 쪽 구현: libs/model-io 의 compose_extraction_input·compose_response_from_request, taxonomy.py REF_SOURCE 와 prev_state.py 규칙(재현율은 README 5절).

- 영역: model-runtime(libs/model-io)
- 상태: 계약 개정 대기. B 쪽은 구현을 마쳤고 A 쪽은 아래 값이 정해져야 한다.

## 구현한 것(LoRA-B)
`compose_response_input(a_output, asked_item, utterance, state, next_text)` 이 labels.py 의 표와 문장 틀로 topic·known·ask·previous·current·hold 와 next.type 을 만든다. 학습 파일 B 입력 46655건이 같은 A 정답 출력·입력과 다음 질문 문장에서 내용까지 같고 직렬화는 46645건이 바이트까지 같다(나머지 10건은 학습 파일이 정렬되어 있지 않다, 요청 001 3절). START 110건도 같다.

## 요청이 실어야 하는 구조화된 값
- generateResponse: `asked_item`, 환자 발화, 행동·사유·값·대상·note(LoRA-A 검증을 마친 출력 그대로), 직전 state, **다음 문항의 질문 문장**.
- extractAction: 문항 식별자, 환자 발화, **상담원이 방금 한 말(직전 LoRA-B 출력 그대로)**, 저장된 값들, 순서표, 칸 규격.

## 정본에 없어서 만들지 못한 것
1. **next.text**: 문항 은행의 문장이다(SQL.md 7.3, 데이터셋은 `data/question_bank.json` 의 바꿔 말한 질문). 표가 `contracts/inputs` 에 없고 survey-service 가 문항 세트로 올리므로 요청이 싣는다.
2. **LoRA-A state 의 선택**: SQL.md 7.1 은 '지금 문항, 직전에 물은 문항(대화 순서, 건너뛰기 반영), 참조 원천 문항(taxonomy.REF_SOURCE)'의 값만 넣는다고 적는다. REF_SOURCE 표(예: Q10 → Q9_1)와 학습 데이터의 묶음 순서(scripts/prev_state.py, OPEN_GAPS G13: 서비스 규칙과 97.6% 일치, 나머지는 순서만 다름)가 정본에 없다. 서빙이 선택하려면 이 표와 순서 규칙이 `contracts/inputs` 에 있어야 한다. 그때까지 요청이 선택을 마친 `state` 와 `state_key_order` 를 싣는다(현재 계약).
