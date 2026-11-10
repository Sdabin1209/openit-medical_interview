# model-lab 브리프

공통 규칙은 [README](README.md). 맡는 일과 컴포넌트는 [design.md 2절 model-lab](../design.md). 프로젝트 최하위 순위다(E2E 뒤, 사용자 결정 2026-11-10).

## 무엇을 만드나
비전문가용 학습 래퍼다. 화면에서 학습 값을 조정하고 데이터셋 파일을 올려, 학습 서버에 있는 정본 학습 코드(`train_lora_a.py`, `train_lora_b.py`)를 그대로 부른다(D78: 학습 정본은 학습 서버 코드, G06: 비전문가가 쓸 수 있게 감싼다). 정본 코드를 복사하거나 다시 쓰지 않는다.

- 폴더: `services/model-lab`(API와 학습 실행), `web/model-lab`(학습 화면). 둘 다 학습 GPU 서버에서 뜬다(design.md 6절).
- 접속: SSH 터널로만(외부 포트 없음). 사용자는 한 명(소유자).
- 학습 값: 정본 학습 코드가 받는 인자(`--epochs --lr --batch --accum --rank --alpha --dropout --max_len --eval_steps --seed`, G06 기록)를 화면 칸으로 두고 기본값을 준다. 평가용 생성 값(temperature 등)은 평가 단계 설정이다.
- 실행: 한 번에 하나, GPU 는 지정 시간대에만. 진행과 로그를 화면에 보인다. 실행 기록(`run_config.json`)을 남긴다.
- 평가: `libs/model-io` 로 평가 보고서. 게시: model-runtime 의 package_publish 와 같은 OCI 형식.

## 시작 전에 필요한 것
- 학습 서버 사용 허가(쓰기·실행·GPU 시간대).
- 정본 학습 코드의 위치와 인자를 학습 서버에서 다시 확인(읽기만).

## 끝 조건(공통에 더해)
- GPU 없이: 데이터셋 올리기·검증 → 학습 값 → 가짜 실행기로 학습 → 평가(가짜 출력) → 로컬 레지스트리 게시 시나리오 시험 rc=0, 화면 Playwright 시나리오 rc=0.
- 실제 학습은 허가된 GPU 시간대에 따로 확인하고, 하지 않았으면 하지 않았다고 README 5절에 적는다.
