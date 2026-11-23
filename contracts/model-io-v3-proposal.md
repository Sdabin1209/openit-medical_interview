# 모델 입출력 v3 명세 (실측, 계약 반영 전)

v3 는 데이터셋 `dataset1118`(2026-11-17, 데이터셋 담당)과 그것으로 학습한 어댑터 `a_8b_1118`·`b_8b_1118` 의 입출력이다. v2(`model-io-v2`)는 `dataset/final`(2026-11-03)과 그 어댑터(`a_8b_1029`, `b_8b_1103`)다. 이 문서는 두 데이터를 행 단위로 비교해 다른 점만 적는다. 계약 값은 이 문서가 아니라 `components.yaml` 이며, 아래가 반영되면 `ModelIoVersion` 에 `model-io-v3` 가 더해진다.

- **근거 자료(학습 서버, 읽기 전용):** `~/taehyeon/data/dataset1118/README.md`(4·8·9장), `~/WS/dataset/docs/fix1.md`(명세 v3)·`fix2.md`(검토)·`fix3.md`(LoRA-B 답변)·`fix4.md`, `~/WS/dataset/scripts/fixaug_rules.py`(`b_input`, `reask_all`, `redirect`, `keep_and_next`), `fixaug.py`(P22).
- **바뀌지 않은 것:** 정본 `labels.py`·`IO_SPEC.md`(이 리포의 `contracts/inputs/` 사본과 바이트까지 같다), 시스템 프롬프트(두 어댑터 모두 v2 와 같다), 기반 모델(Qwen3-8B), LoRA 설정(rank 16, alpha 16, 대상 층 7개), A 입력의 키 네 개(`current_question`, `question_id`, `state`, `user_utterance`), B 입력의 키 이름.
- **측정:** v2 LoRA-A 44,563행·LoRA-B 44,682행, v3 LoRA-A 68,817행·LoRA-B 66,763행(train+val+test). 측정 도구는 리포 밖(`e2e-prep/scripts/shapes.py`, `bcompose_v3.py`, `nim.py`)이고 model-io 의 v2 코드로 v3 데이터를 돌려 다른 곳을 셌다.

## 1. 직렬화: 모든 수준 키 정렬

| | v2 | v3 |
|---|---|---|
| A 입력 | 최상위 키 정렬, `state` 는 서비스가 준 순서, `state` 항목 안은 `{"value", "status"}` 순서 | **모든 수준 키 정렬**(`state` 의 칸 키도, 항목 안도 `{"status", "value"}`) |
| B 입력 | 모든 수준 정렬(정렬되지 않은 학습 행 10개) | 모든 수준 정렬 |
| A 출력 | 모든 수준 정렬 | 같음 |

v3 의 A·B 입력은 `json.dumps(값, ensure_ascii=False, sort_keys=True)` 와 바이트까지 같다(A 68,817/68,817, B 66,763/66,763). 그래서 v2 의 `state` 묶음 순서 규칙(재현율 98.48%)은 v3 에서 필요 없다.

## 2. LoRA-A 출력: 새 사유 3개

| action | reason | 행 | 값 | 대상(targets) | next_item |
|---|---|---:|---|---|---|
| REASK | `UNCLEAR_TARGET` | 7,491 | 지금 문항의 모든 칸을 `MISSING`, `save` false, `value` null | 지금 문항의 모든 칸 | 지금 문항 |
| REDIRECT | `ASK_MEANING` | 3,036 | 없음 | 없음 | 지금 문항 |
| REDIRECT | `ASK_HOW` | 1,571 | 없음 | 없음 | 지금 문항 |

- 뜻(데이터셋 README 4장): `UNCLEAR_TARGET` 은 말이 어느 문항을 가리키는지 모호하거나 지금 문항이 아닌 문항을 가리킴, `ASK_MEANING` 은 무엇을 묻는 질문인지 되물음, `ASK_HOW` 는 어떻게 답하면 되는지 되물음.
- 위 세 모양은 v2 의 같은 action 규칙(REASK 는 대상 칸이 values 에 있고 저장 안 함, REDIRECT 는 values 없음·같은 문항)을 그대로 지킨다. 새 값은 reason 의 값 목록뿐이다.
- v2 의 `ASK_PURPOSE`(왜 묻는지)와 `ASK_MEANING`·`ASK_HOW` 는 다른 사유로 남는다.

- 모양 규칙(계약 9.4.0 `ActionExtraction`, model-io 출력 검증): `UNCLEAR_TARGET` 은 REASK 이고 지금 문항의 **모든** 칸을 MISSING·저장 안 함으로 values·targets 에 둔다. `ASK_MEANING`·`ASK_HOW` 는 values 가 빈 REDIRECT 다. 어기면 출력 불가다(설명해 달라는 말로 답이 저장되지 않게). 활성 패키지가 v2 인데 v3 의 사유가 나오면 출력 불가다.

## 2a. LoRA-A 입력: 확인 다음 턴의 state

환자가 확인(CONFIRM) 화면에 답하는 턴의 `state` 는 **확인하는 문항의 저장 값만** 담는다(`fixaug.py` `confirm_state`, 실측 P17 4,050/4,050행). v2 의 규칙(지금·직전·참조 원천 문항)과 다르다. 서비스가 직전 화면의 절차를 `previous_screen_action` 으로 알려 주고 model-runtime 이 CONFIRM 이면 지금 문항의 칸만 고른다(계약 9.4.0 `ExtractionRequest`·`ResponseGenerationRequest`).

## 3. LoRA-A 출력: 값 없는 NEXT 의 다음 문항

확인(CONFIRM)에 "아까 값이 맞다"고 답한 턴의 정답은 `{"action": "NEXT", "values": []}` 이다(v3 772행, v2 0행; 유형 P17). 이때 `next_item` 은 **`state` 에 저장된 그 문항의 값**으로 건너뛰기를 계산한다(`fixaug_rules.keep_and_next`: `labels.next_after(문항, state 의 그 문항 ANSWERED 값)`).

- v2 의 규칙(`IO_SPEC` 2.1 "건너뛰기는 이번 턴에 저장되는 값만 보고 정한다")으로 계산하면 41행이 다르다(예: Q4 가 '아니요'로 저장된 상태에서 Q4 확인에 '맞다' → 정답 Q5, v2 규칙 Q4_1).
- 계약 `NextItemRule` 에 "values 가 비어 있는 NEXT 는 state 의 그 문항 저장 값으로 건너뛰기"를 더한다.

## 4. LoRA-B 입력

v2 의 B 입력 만들기(`compose_response_input`, `compose_start_input`)는 v3 의 66,763행 중 아래 세 경우만 다르고 나머지는 모두 같다(START 119/119 같음).

| 경우 | 행 | v3 규칙 | 근거 |
|---|---:|---|---|
| REASK / `UNCLEAR_TARGET` | 7,491 | `ask` 는 빠진 칸을 묻는 문장 틀(`labels.ask_text("MISSING", targets, 저장된 값)`)로 만든다. 예: "고혈압 진단을 받은 적이 있는지, 지금 고혈압 약을 먹는지" | `fixaug_rules.b_input` |
| REDIRECT / `ASK_MEANING`·`ASK_HOW` | 1,499(모두 ASK_MEANING) | 직전 턴의 B 입력이 REASK 였으면 그 `ask`, CONFIRM 이었으면 그 `ask`·`previous`·`current`, 이 조건의 REDIRECT 였으면 그 턴에 넣은 것을 그대로 넣는다. 그 밖(START·NEXT·CORRECT·HOLD·SKIP·다른 REDIRECT)은 넣지 않는다. `next.type` 은 SAME | `fix3.md` 1장, `fixaug_rules.b_input`. `ASK_HOW` 에 직전 내용이 붙은 행은 데이터에 없지만 규칙은 두 사유에 같다 |
| SKIP / `LIMIT_REACHED` | 827(B 에만) | 되묻기 한도에 닿아 서비스가 문항을 넘길 때의 문장. A 출력이 없다. `known` 은 빈 문자열, `hold` 는 `labels.hold_text(지금 문항의 칸, 지금 문항)`, `next` 는 `labels.next_after(지금 문항, [])` 와 그 질문(`type` NEXT) | `fixaug.py` P22 |

- v2 계약은 REDIRECT 의 B 입력에 `ask`·`previous`·`current` 를 금지한다. v3 는 위 조건에서 허용한다(`ask` 선택, `previous`·`current` 는 둘 다 있거나 둘 다 없음).
- 직전 턴의 B 입력은 서비스와 model-runtime 이 만든 것이다. 그래서 REDIRECT 의 응답 생성 요청이 직전 턴의 요청(구조 값)을 함께 실어야 model-runtime 이 같은 규칙으로 다시 만들 수 있다(설계는 계약 변경에서 정한다).

## 5. 서비스 규칙(프레임워크 몫, 데이터셋 README 9장)

| 항목 | 정할 것 | 지금 근거 |
|---|---|---|
| 되묻기 한도(`ReaskLimit`)에 세는 것 | `ASK_MEANING`·`ASK_HOW` 는 세지 않는다. `UNCLEAR_TARGET` 은 REASK 이므로 센다 | 사용자 결정 2026-11-10(설명 요청은 한도 밖·별도 3회). `UNCLEAR_TARGET` 은 v2 의 REASK 규칙을 따른다 |
| 설명 요청 연속 한도(`ExplainStreakLimit`) | `ASK_MEANING`·`ASK_HOW` 가 한 문항에서 3번 이어지면 서비스의 고정 문장으로 직원 도움을 안내한다(`StaffHelpNotice`) | 사용자 결정 2026-11-10 |
| 되묻기 한도에 닿을 때의 문장 | v2 는 서비스 고정 문장. v3 는 LoRA-B 에 SKIP/`LIMIT_REACHED` 를 보내 문장을 만든다. 결과의 빈칸 원인은 그대로 `REASK_LIMIT` | v3 데이터 P22(827행). v2 에서 고정 문장을 쓴 이유("모델에 거짓 사유를 보내지 않는다")는 학습된 사유가 생겨 없어진다 |
| 연속 실패 한도(`TurnFailureLimit`, 계약 9.3.0) | 바꾸지 않는다(모델 출력 불가에 대한 서비스의 고정 문장) | `LIMIT_REACHED` 는 되묻기 한도용이다 |

## 5a. 서비스가 새로 들고 있어야 할 것(독립 검토 2026-11-23)

- 직전 턴의 응답 생성 요청(되묻기·확인)을 반영 **전** 값으로 보존해 설명 요청 때 `ask_back_source` 로 싣는다. 설명 요청이 이어지면 처음 원본을 그대로 싣고, 다른 화면으로 넘어가면 지운다.
- 직전 화면의 절차(`previous_screen_action`).
- 한 문항의 설명 요청 연속 횟수(ASK_MEANING·ASK_HOW 합산, `ExplainStreakLimit`).
- 확인(CONFIRM)이 지금 문항이 아닌 문항을 가리키면 B 요청의 `next`(SAME)는 확인하는 문항(A 출력의 next_item)과 그 질문 문장이어야 한다(정본 `labels.py` b_input 은 next_item 으로 만든다, v3 실측 2,754행이 이 경우). v2 에도 해당한다.

## 5b. 이 비교가 증명하지 않는 것

B 입력의 바이트 비교는 학습 데이터의 질문 문장(`next.text`)을 넣어 한 것이다. 학습 데이터는 한 문항에 여러 질문 문장을 쓰고(31개 문항 모두), 서비스는 문항 세트의 문장 하나를 쓴다. 그래서 운영의 B 입력은 질문 문장만큼 학습 행과 다를 수 있고, 그것은 정상 입력이다(독립 검토 8번).

## 6. 이전 v3 후보에서 바뀐 것

이 파일의 이전 판(2026-11-10)은 데이터가 나오기 전의 후보였다.

- `reason` 의 `MEANING_ASKED` 하나 → 실제는 `ASK_MEANING`·`ASK_HOW` 둘(그리고 `UNCLEAR_TARGET`, `LIMIT_REACHED`).
- LoRA-A 입력의 선택 칸 `confirming` → 데이터에 없다. 확인 다음 턴의 `state` 에는 확인하는 문항의 값만 있다(데이터셋 README 8장). 넣지 않는다.

## 7. 이 문서 밖

- **병합·양자화 모델:** 학습 서버에 1029/1103 을 Qwen3-8B 에 병합하고 GPTQ W4A16 으로 양자화한 모델이 있다(`~/myungchan/merged_A_w4a16`, `merged_B_w4a16`, 2026-11-08, 각 5.7GB). v7 의 모델 패키지는 '기반 모델 하나 + 어댑터 둘'이라 이것을 쓰려면 패키지 형식과 엔진 구성이 바뀐다. 1118 로는 아직 만들어지지 않았다. 따로 정한다.
- **모델이 이슈를 고쳤는지:** 데이터셋 README 8장대로 확인되지 않았다. v3 지원 뒤 E2E 와 대화 시나리오 평가로 본다.
