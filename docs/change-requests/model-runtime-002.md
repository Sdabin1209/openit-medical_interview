# 변경 요청 model-runtime-002: D115 값 고쳐 쓰기 R1·R3 의 규칙 데이터가 없다

처리됨(계약 9.0.0(5f3c616, 848dbcb), 영역 55b6689): 정본(contracts/inputs)에 술 환산표·R1 규칙이 없어 R1·R3 은 명시적으로 비활성(DISABLED_RULES, DC-11), R2 날수는 달력 최댓값 7·31·366.

- 영역: model-runtime(libs/model-io `core/guard.py`)
- 대상: `ActionExtractionRules`(규칙 명세), `contracts/inputs`(데이터셋 정본)
- 상태: 처리됨(맨 위 처리 기록 참고). 아래는 요청 당시의 상태다. R1·R3 은 만들지 않았다(값을 지어내지 않기 위해).

## 구현한 것
- 다음 문항 채우기(U74, `NEXT_ITEM_FILLED`), 칸 규격 최댓값 초과 → `REASK/OUT_OF_RANGE`(값 null, UNCLEAR, save 거짓), 횟수 > 날수(R2) → `REASK/COUNT_EXCEEDS_DAYS`.
- 정답 모양은 학습 파일 정답에서 확인했다(OUT_OF_RANGE: `targets` 는 그 칸 하나, `next_item` 은 그 문항. COUNT_EXCEEDS_DAYS: `Q7.does_not_drink=false`(저장), `Q7.frequency`·`Q7.unit` 은 null/UNCLEAR, `targets` 는 둘).

## 부족한 것
1. **R3**(최대 음주량 < 평소 음주량 → `CONFIRM/CONFLICT_MAX_BELOW_USUAL`)는 술 종류별 mL 환산표(정규화기 `alcohol.py`)가 필요하다. 이 저장소의 `contracts/inputs` 에도 계약에도 없다.
2. **R1**(횟수가 있으면 '마심'으로 고친다)은 정규화기 코드가 정본이고 데이터셋 정답에 사례가 0건이라 모양을 확인하지 못했다(OPEN_GAPS U33).
3. **R2 의 날수**: 정규화기에서 기간별 날수(주·달·해)를 확인하지 못했다. 달력의 가장 긴 값(7, 31, 366)을 썼다. 정답에서 받아들인 최대 횟수는 주 7, 월 30, 년 15 이고 모두 위반 0 이다(측정).
4. 자료형·최솟값 위반은 데이터셋에 정답 모양이 없어 D115 대로 고쳐 쓰지 않고 출력 불가로 낸다.

## 요청
R1·R3 과 R2 의 규칙 데이터(환산표, 기간별 날수)를 `ActionExtractionRules` 에 싣거나 `contracts/inputs` 에 정본으로 둔다. 그러면 `DEFAULT_RULES` 와 검증기에 반영하고 학습 파일 정답으로 위반 0·고쳐 쓰기 0 을 다시 잰다.
