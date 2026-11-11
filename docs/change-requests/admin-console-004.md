# 변경 요청 admin-console-004: 문항 세트 목록에 어느 버전이 활성인지 없다

처리됨(계약 9.0.0(5f3c616, 848dbcb), 영역 e47d70e, 화면 77e2eb5): QuestionSetVersion.is_active.

- 영역: admin-console
- 대상 계약: `contracts/openapi/survey-service.yaml`(`listQuestionSetVersions`, `listActiveQuestionnaires`), `contracts/components.yaml`(`QuestionSetVersion`, `QuestionnaireSummary`, `ActiveQuestionSet`)
- 상태: 처리됨(맨 위 처리 기록 참고). 아래는 요청 당시의 상태다. 그동안 화면은 활성화를 막 한 직후의 응답(`ActiveQuestionSet`)만 보인다.

## 문제
올린 사람은 활성화할 버전을 고른다. 그런데 어느 버전이 지금 활성인지를 읽는 작업이 없다. `listActiveQuestionnaires` 는 문진표 식별자와 제목만 주고 활성 버전 식별자를 주지 않는다. `QuestionSetVersion` 에도 활성 표시가 없다. 화면을 다시 열면 현재 활성 버전을 알 수 없어 이미 활성인 버전을 다시 활성화하거나(계약은 멱등이라 해가 없다), 잘못된 버전을 활성이라 믿을 수 있다.

## 요청
`QuestionSetVersion` 에 활성 여부(또는 `activated_at`)를 더하거나, 문진표별 활성 `ActiveQuestionSet` 을 읽는 작업을 더한다.
