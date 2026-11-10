# 데이터 증강·검증 로직

건강검진 문진 상담 데이터셋 v2를 어떻게 만들고(증강) 어떻게 걸러 내는지(검증) 설명한다.
코드는 핵심만 줄여 옮겼다. 전체는 적어 둔 파일·함수에 있다.

---

## 0. 원칙

> **정답(라벨)은 코드(정규화기)가 정하고, LLM은 문장만 쓴다.**
> **검증은 "그 문장이 정말 그 정답을 말하는가"를 확인한다.**

- 정답은 정규화기 코드가 계산하므로 같은 입력에는 늘 같은 정답이 나온다.
- 틀릴 수 있는 것은 LLM이 쓴 **문장**이다(정답은 "약 안 먹음"인데 문장은 "약 먹어요").
- 그래서 검증은 모두 문장과 정답이 맞는지를, **정답을 모르는 쪽에서 다시 읽어** 확인한다.
- 사람 검수는 하지 않는다. 대신 LLM 검사를 3번씩 돌려 모두 통과해야 채택한다.

### 학습 데이터 한 건

설문 전체가 아니라 **대화 한 번 주고받기(한 턴)**다.

```
상담원: "숨이 많이 찰 정도의 운동은 하루에 얼마나 하세요?"
환자:   "사십 분쯤 해요"
→ LoRA-A 정답: Q8_2 = 40분(어림), 다음 행동 NEXT, 다음 문항 Q9_1
→ LoRA-B 정답: "40분 정도 하시는군요. 그럼 숨이 약간 찰 정도의 운동은 일주일에 며칠 하세요?"
```

| 모델 | 입력 | 출력 |
|---|---|---|
| LoRA-A (판단) | 현재 문항, 상담원 질문, 환자 말, 지금까지 저장된 값 | 저장할 값, 다음 행동, 다음 문항 |
| LoRA-B (말하기) | LoRA-A 결과(받은 값, 행동, 다음 질문) | 상담원 응답 문장 |

---

# 1부. 데이터 증강

## 전체 흐름

```
① 부족한 조합 고르기   (코드)  조합마다 목표 건수에 못 미친 것만
② 정답 만들기         (코드)  샘플러가 값을 뽑고 → 정규화기가 저장 값·다음 행동 계산
③ 환자 발화 쓰기       (LLM)  정답 메모를 보고 말투 4가지로 작성 (숫자는 아라비아 숫자로만)
④ 숫자 표기 바꾸기     (코드)  숫자 50 / 한글 25 / 섞기 25
   ─── 검증 (2부) ───
⑤ 상담원 응답 쓰기     (LLM)  LoRA-A 결과를 보고 응답 작성
⑥ 레코드 저장          (코드)
```

## ① 조합: 무엇을 덮어야 하나

한 턴의 내용은 `문항 | 상황 | 세부 유형 | 답의 종류 | 정규화기 처리`로 나눈다. 이것을 **조합**이라 부른다.

| 구성 | 예 |
|---|---|
| 문항 (31) | Q1.D04 당뇨, Q7_1 음주량, Q10 근력 운동 … |
| 상황 (11) | 정상, 범위·어림·단위, 부분 응답, 재질문 뒤 보완, 정정, 충돌, 앞 답 참조, 모름·거절·보류, 문진과 무관한 말, 경계값, 정규화 규칙 사례 |
| 세부 유형 | 정정 / 범위 / 단위 환산 … |
| 답의 종류 | 진단O·약X, 소주병+맥주캔, 3일 … |
| 정규화기 처리 | NEXT, REASK, CONFIRM, HOLD, SKIP, CORRECT, REDIRECT |

- 조합이 다르면 모델이 해야 할 판단이 달라지므로 하나도 빠지면 안 된다.
- 가능한 조합은 샘플러를 칸마다 1,500번 돌려 **실제로 나오는 것만** 모았다(`patterns/combos.json`).
- 말투·숫자 표기는 조합에 넣지 않고, 조합 안에서 비율로 섞는다.

`scripts/combos.py` — `combo_key`
```python
def combo_key(item, pattern, subtype, out):
    """조합 키: '문항|상황|세부 유형|답의 종류|정규화기 처리'. out은 정규화기 결과."""
    return "|".join((item, pattern, subtype, answer_class(item, out), out["transition_plan"]["action"]))
```

생성은 조합마다 이미 통과한 건수를 세어 목표(`COMBO_TARGET` + 여유 1)에 못 미친 조합만 만든다.
시도를 많이 해도 거의 통과하지 않는 조합은 멈추고 부족분으로 보고한다.

`scripts/pipeline.py` — `run_combo_stage`
```python
have = accepted_by_combo(stages, excluded)        # 조합별 통과 건수 (재검사 탈락은 뺌)
for k, g in goal.items():
    if have[k] >= g: continue                     # 다 찬 조합은 건너뜀
    if tried[k] >= EARLY_MIN_TRIES and rate < EARLY_MIN_YIELD:
        stopped[k] = ...; continue                # 통과율 3% 미만이면 멈추고 부족분으로 보고
    deficit[k] = g - have[k]
slots = run.combo_slots(deficit, ...)             # 샘플러만 돌려 그 조합이 나오는 번호를 찾음 (LLM 없음)
```

## ② 정답 만들기 (LLM 없음)

샘플러가 상황별 규칙으로 값을 뽑고, 정규화기가 저장 값·다음 행동을 계산한다. 이것이 LoRA-A 정답이다.
시드가 고정되어 있어 같은 번호는 언제 다시 만들어도 같은 정답이다.

`scripts/sampler.py` — `build_canonical`
```python
def build_canonical(item, pattern, index, seed=..., required_plan=None):
    cid = f"c_{item}_{pattern}_{index:04d}"
    for t in range(max_tries):
        rng = random.Random(sha256(f"{seed}|{cid}|{t}"))       # 시드 고정 → 재현 가능
        sc = PATTERN_FUNCS[pattern](item, rng)                # 상황별 값 뽑기 (예: 정정 30년 → 60년)
        exp = expected_output(sc["target"], sc["previous"])   # 정규화기가 정답 계산
        ...
```

## ③ 환자 발화 쓰기 (LLM)

LLM은 정답을 **메모**로 받는다("진단 받음", "약 안 먹음"). 메모대로 말투 4가지의 환자 말을 쓴다.
정정·충돌처럼 앞 대화가 필요한 상황은 앞 대화의 환자·상담원 턴도 함께 쓴다.

`scripts/prompts.py` — `utterance_messages`
```python
payload = {
    "상담원_현재_질문": current_question,
    "이전_대화_설명": prior,                       # 정정·충돌 등은 앞 대화도 함께 씀
    "환자가_이번에_말할_내용_메모": say,           # ← 정답에서 만든 메모
    "말하지_말_것": silent,
    "변형별_스타일": [{"style": t, ...} for t in styles],   # 말투 8종 중 4개
}
# 규칙 2: "메모의 사실을 하나도 빠짐없이 ... 값 숫자는 모두 아라비아 숫자 + 단위로 쓴다"
# 규칙 3: "다른 문항 정보(다른 질병, 담배, 술, 운동 수치)도 새로 넣지 않는다"
```

말투 8종과 비율:

| 말투 | 비율 | 말투 | 비율 |
|---|---|---|---|
| 존댓말 완결문 | 18% | 머뭇거림·필러 | 12% |
| 짧은 구어 | 16% | STT 오류형 | 12% |
| 한글 숫자 | 14% | 반말 | 8% |
| 장황·부연 | 12% | 사투리 | 8% |

## ④ 숫자 표기 바꾸기 (코드)

LLM에게 한글 숫자를 쓰게 하면 "사십한 분", "스물오 분" 같은 섞인 수사가 나온다. 그래서 LLM은 아라비아 숫자로만 쓰고 표기는 코드가 바꾼다.

- 비율: 숫자 50% / 한글 25% / 섞기 25%. 실제 입력이 음성 인식(STT) 결과라 여러 표기가 섞여 들어온다.
- 단위에 맞는 수사를 고른다. 분·년·개월·일은 한자어("사십 분"), 개비·병·잔·번·시간은 고유어("열두 개비")다.
- 1~2일은 늘 "하루·이틀"로 쓰고, 3~5일은 절반을 "사흘·나흘·닷새"로 쓴다.
- "일주일", "한 달", "한 번" 같은 고정 표현은 숫자로 보지 않는다.
- '한글 숫자' 말투는 늘 한글로 쓰고, STT 오류형은 붙여 쓴다("사십분").
- 상담원 응답은 늘 아라비아 숫자로 쓴다.

`scripts/pipeline.py` — `localize_utterance`
```python
def localize_utterance(c, raw, style, key):
    rng = random.Random(h32(SEED, "num", key))
    mode = numerals.pick_mode(style, rng)            # digit / korean / mixed
    digits = numerals.to_digits(raw, allowed=...)    # LLM이 한글로 쓴 정답 값은 먼저 숫자로 정리
    text, n = numerals.localize(digits, mode, rng, nospace=(style == "stt_noise"))
```

## ⑤ 상담원 응답 쓰기 (LLM)

검증을 통과한 발화만 LoRA-B 입력(받은 값, 행동, 다음 질문)을 만들어 LLM이 응답을 쓴다.
응답에 남은 한글 숫자는 아라비아 숫자로 바꾼다. 실패하면 응답만 말투·시드를 바꿔 최대 3번 다시 만든다(`generate_b`).

---

# 2부. 데이터 검증

후보 하나가 아래 관문을 **순서대로** 모두 통과해야 저장된다. 하나라도 실패하면 버리고 사유를 남긴다(`data/generated/rejects/`).
앞 관문에서 떨어진 후보는 뒤 관문을 돌리지 않는다. 각 관문의 판정 기준은 같으므로 결과는 같고 LLM 호출만 줄어든다.

```
[규칙]   발화 검사 → 다른 질환 → 중복
[LLM×3]  이전 턴 대조 → 자연스러움 → 블라인드 역추출
[코드]   정규화기 재실행 → 상태 논리
[응답]   응답 규칙 → 응답 판정 ×3
[코드]   DB 왕복
```

## 관문 1. 규칙 검사 (코드)

`scripts/checks.py` — `check_utterance`
```python
def check_utterance(canonical, utterance, current_question):
    if numerals.malformed(utterance):                    raise Reject("u_mixed_numeral")   # '사십한 분'
    if any(p in utterance for p in COUNSELOR_PHRASES):   raise Reject("speaker_confusion") # 환자가 상담원 말투
    if lcs_len(utterance, current_question) >= 14:       raise Reject("copies_question")   # 질문 베끼기
    if not approx_ok and re.search(r"쯤|정도|대략...", utterance):
        raise Reject("unexpected_approx")                # 정답은 정확한 값인데 '3일쯤'
    extra = {n for n in numbers_in(utterance) if n not in allowed}
    if extra:                                            raise Reject("new_number")        # 정답에 없는 숫자
```

| 검사 | 걸리는 예 |
|---|---|
| 정답에 없는 숫자 | "**10년 전에** 당뇨 진단 받았어요" |
| 섞인 수사 | "하루 **사십한** 분" |
| 다른 질환 이름 (`check_wrong_disease`) | 당뇨 질문에 "**고혈압** 진단 받았어요" |
| 상담원 말투, 메모·질문 베끼기 | "말씀드리면 진단 여부는 예입니다" |
| 정답에 없는 어림 표현 | 정답은 정확히 3일인데 "3일**쯤**" |
| 글말 종결, 자기 존칭 | "진단을 받았다.", "약을 드십니다" |

**중복**은 같은 문항·같은 상황 안에서 같은 문장일 때만 본다. 다른 문항에 같은 문장("약은 안 먹어요")이 쓰이면 질문·상태·정답이 달라 다른 학습 예다.

`scripts/pipeline.py` — `dup_key`
```python
def dup_key(item, pattern, text):
    return f"{item}|{pattern}|{checks.surface(text)}"    # surface: 공백·문장부호를 뺀 문자열
```

## 관문 2. 이전 턴 대조 (LLM 3번)

정정·충돌·재질문 상황에서는 앞 대화의 환자 말도 LLM이 쓴다. 그 문장을 정답을 모르는 LLM에게 다시 읽혀 값을 뽑고, 그 턴의 정답과 **모순**이 있는지 본다.

- 모순(양쪽 다 값이 있는데 다름)이면 탈락시킨다.
- 문장에서 말하지 않은 값은 탈락시키지 않는다(예: "25년 피웠어요"인데 저장값에는 하루 개비 수도 있음).

`scripts/checks.py` — `prior_contradictions`
```python
def prior_contradictions(pc, extraction, text):
    out = run_turn(ext, CATALOG, {}, utterance=text, ...)          # 뽑은 값을 정규화기에 넣음
    gold, got = saved(pc["expected"]), saved(out)
    bad = [k for k in gold if k in got and got[k] != gold[k]]      # 양쪽 다 값이 있는데 다르면 모순
    # 예/아니요 칸은 정규화 전 값도 비교한다 ('진단 없는데 약 먹어요'를 정규화기가 진단=예로 추론하기 때문)
    bad += [k for k in rg if k in re_ and re_[k] != rg[k]]
    return bad
```

걸리는 예: 문장은 "진단은 받은 적 없는데"인데 저장은 진단=예. 문장은 "소주 한 병"인데 저장은 2병.

## 관문 3. 자연스러움 판정 (LLM 3번)

LLM이 "실제 환자가 할 법한 말인가"를 1~5점으로 매긴다. 3번 모두 3점 이상이어야 한다.

`scripts/pipeline.py` — `check_utterance_votes`
```python
def check_utterance_votes(judges):
    for k, uj in enumerate(judges):
        if uj.get("failure") is not False or uj.get("natural", 0) < 3:
            raise Reject("utterance_unnatural" if k == 0 else "utterance_vote_fail")
```

## 관문 4. 블라인드 역추출 (LLM 3번), 가장 중요한 검사

**정답을 보여 주지 않은** LLM에게 발화만 주고 값을 뽑게 한다. 뽑은 값을 정규화기에 넣은 결과가 원래 정답과 같아야 한다.

```
발화: "당뇨병 진단은 받았어요. 약은 지금 안 먹어요."
LLM이 뽑은 값: 진단=예, 약=아니요 → 정규화기 → 원래 정답과 같음 ✓

잘못 쓴 발화: "당뇨병 진단 받았고 약도 먹어요"
LLM이 뽑은 값: 진단=예, 약=예 → 원래 정답(약=아니요)과 다름 ✗
```

`scripts/checks.py` — `check_extraction`
```python
def check_extraction(canonical, extraction, utterance):
    out = run_turn(ext, CATALOG, previous_dict(canonical), utterance=utterance, ...)
    if core(out) != core(canonical["expected"]):     # 저장 값·행동·다음 문항이 정답과 다르면
        raise Reject("blind_extraction_mismatch")
```

## 3번 투표 방식

같은 LLM 검사를 다시 돌리면 결과가 바뀌는 경우가 있다(측정해 보니 A 7%, B 16%). 그래서 이전 턴 대조, 자연스러움, 역추출, 응답 판정은 3번씩 돌린다.

- 1번째: 온도 0
- 2·3번째: 다른 시드 + 온도 0.5
- 3번 모두 통과해야 채택한다. 문장이 애매하면 돌릴 때마다 다르게 읽히므로 "누가 읽어도 그 뜻인 문장"만 남는다.
- 앞 투표에서 실패한 후보는 다음 투표를 돌리지 않는다.

`scripts/pipeline.py` — `Runner.vote_json`
```python
VOTE_TEMPS = (0.0, 0.5, 0.5)

def vote_json(self, kind, reqs, schema, max_tokens, keep=None):
    for k, temp in enumerate(VOTE_TEMPS):
        if keep is not None and k > 0:
            reqs = [r for r in reqs if keep(r[0], out[r[0]][-1][0])]   # 앞 투표를 통과한 것만
        rs = [(cid, m, seed if k == 0 else h32(seed, "vote", k)) for cid, m, seed in reqs]
        ...
```

## 관문 5. 정규화기 재실행·상태 논리 (코드)

- **재실행** (`checks.normalized`): 역추출로 조립한 정답을 정규화기에 다시 돌려도 같은 결과가 나와야 한다. 두 번 돌려도 같아야 한다.
- **상태 논리** (`checks.state_logic_errors`): 저장될 값끼리 말이 되는지 본다.

```python
def state_logic_errors(values):
    # 진단 없음 + 약 복용
    # 흡연 경험 없음 + 흡연 기간·개비 수
    # 술 안 마심 + 음주량·횟수
    # 운동 0일 + 운동 시간
    # 날 수가 0~7일 밖
```

## 관문 6. 상담원 응답 검사

| 검사 | 걸리는 예 |
|---|---|
| 응답 규칙 (`checks.check_response`) | 입력에 없는 숫자, 다른 질환 이름, 의료 조언("병원 가 보세요"), 질문으로 안 끝남, 다음 질문이 틀림, 존댓말 활용 오류("드시는다고"), 남은 한글 숫자 |
| 응답 판정 (LLM 3번) | 해야 할 행동(다음 문항 / 다시 묻기 / 확인 …)과 맞는지, 자연스러운지 |

응답이 실패하면 응답만 최대 3번 다시 만든다.

## 관문 7. DB 왕복 (코드)

`checks.RoundTrip`은 정답을 실제 문진 DB에 저장하고 다시 읽어 값이 같은지 확인한다.

---

# 3부. 기존 데이터와 최종 빌드

## 기존 데이터 재검사

검사 기준을 바꾸거나 더하면 이전에 만든 데이터도 같은 기준으로 다시 검사한다(`Runner.recheck_existing`).

- 결과는 `data/generated/recheck/C1.jsonl`에 쌓는다. 레코드 파일은 고치지 않고, 빌드가 이 결과를 보고 탈락분을 뺀다.
- 재검사는 모든 LLM 검사를 함께 돌려 결과를 호출 기록(`data/generated/calls/`)에 남긴다. 그래서 판정 기준만 바뀐 경우에는 LLM을 다시 돌리지 않고 저장된 출력으로 다시 판정한다(`rejudge_recheck`).

## 버린 후보 다시 검사 (R1)

기준을 바꿔서 전에 버린 후보가 통과할 수 있게 되면, 발화를 새로 만들지 않고 이미 만든 문장을 바뀐 기준으로 처음부터 다시 검사한다(`run_rescue_stage`).

- 대상 사유: `RESCUE_REASONS`(중복, 이전 턴 대조)
- 발화는 호출 기록에 저장된 생성 결과를 그대로 쓰고, 검사와 응답 생성은 일반 생성과 같은 `run_batch`로 한다.

## 최종 빌드 (`scripts/build_final.py --upto C1`)

1. 재검사 탈락분 제외, 응답의 숫자 표기 정리
2. 같은 문항·상황 안의 정확 중복, 근접 중복(MinHash, Jaccard 0.85 이상) 제거
3. 조합별 할당량까지 쓰고, 넘는 것은 예비분으로 둠
4. train/val/test = 80/10/10 분할. 같은 문항의 비슷한 문장(Jaccard 0.70 이상)은 같은 쪽에 둔다(누수 방지)
5. 사후 확인
   - `verify_sql --final`: 최종 데이터 전체를 DB에 다시 저장해 확인
   - `selftest`: 프롬프트 예시와 검사 규칙이 서로 맞는지 확인

---

# 4부. 검증이 못 잡는 것

| 남는 것 | 이유 |
|---|---|
| 문법은 맞지만 어색한 표현 | 자연스러움 판정 3번이 모두 통과시키면 남는다 |
| 정규화 규칙이 직관과 다른 정답 | "약만 먹어요" → 진단=예, "지금 안 피워요 + 20년 피움" → 흡연 경험=예처럼 규칙상 맞는 정답은 거르지 않는다. 규칙이 맞는지는 정규화기 담당자가 판단한다 |
| 말투 분포 쏠림 | 짧은 답("네", "10년요")은 표현이 적어 중복으로 많이 빠지고, 긴 말투는 잘 통과한다. 검증이 아니라 생성 쪽에서 조정할 문제다 |

---

# 부록. 파일

| 파일 | 역할 |
|---|---|
| `scripts/pipeline.py` | 생성 실행: 조합 할당, 발화·응답 생성, 검사 순서, 3번 투표, 재검사, R1 |
| `scripts/checks.py` | 검사 규칙: 발화·응답 규칙, 역추출 대조, 이전 턴 모순, 상태 논리, DB 왕복 |
| `scripts/sampler.py` | 상황별 정답 값 뽑기, 정규화기 정답 계산 |
| `scripts/combos.py` | 조합 정의, 가능한 조합 목록, 조합별 목표 |
| `scripts/numerals.py` | 한글 수사 읽기, 아라비아 ↔ 한글 변환, 표기 비율 |
| `scripts/prompts.py`, `scripts/prompt_examples.py` | LLM 지시문과 예시 |
| `scripts/labels.py` | LoRA-A·B 입력·정답 형식 |
| `scripts/build_final.py` | 중복 제거, 할당량, 분할, 학습 파일 |
| `scripts/selftest.py`, `scripts/verify_sql.py` | 사후 확인 |
