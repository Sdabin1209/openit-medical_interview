# 0009. import-linter 층 규칙: types 가 contract 를 알고, settings·jobs 를 층에 넣는다

## 상태
승인(2026-11-10, 영역 작업자 판단)

## 맥락
템플릿의 층 규칙은 types 와 contract 를 서로 모르는 같은 층에 둔다. 이 영역의 컴포넌트 사이 값(types)은 계약 값(세션 상태, 알림 종류, 추출 출력 등)을 필드 형으로 쓴다.

## 결정
층 순서를 `main | jobs` > `link | store | settings` > `components` > `types` > `contract` 로 한다. types 는 contract 를 import 할 수 있고 contract 는 아무것도 import 하지 않는다. settings 는 환경 입력 읽기(main 과 jobs 가 함께 쓴다)다.

## 왜
같은 뜻의 타입은 한 번만 정의한다(D117). 계약의 열거 값을 types 에 다시 정의하면 어긋난다. 나머지 경계(컴포넌트끼리 import 금지, 컴포넌트가 link·store 를 모름, 영역 밖 통신은 link 에서만, SQL 은 store 에서만)는 그대로다.

## 검토한 대안과 버리는 이유
- types 에서 계약 값을 복사한 열거 정의: 두 곳에 같은 뜻.
- 층 규칙을 그대로 두고 types 를 비우기: 컴포넌트 사이 값을 계약 값으로만 주고받아야 해 영역 안 값(세션, 알림 기록)을 둘 곳이 없다.

## 결과
얻는 것: 한 번 정의. 감수하는 것: 템플릿과 다른 영역 pyproject 의 층 규칙이 다르다.

## 되돌리는 조건
템플릿의 층 규칙이 바뀌면 따른다.
