// link_survey: survey-service 호출(N05, N06). 시작 코드, 결과, 문항 세트, 실패 사례, 직원 알림 목록과 개입.
// 컴포넌트는 이 파일을 모른다. 조립(src/*.tsx)이 훅의 결과를 props 로 넘긴다.
import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import type { components } from "../contract/survey-service";
import { newIdempotencyKey, survey, unwrap } from "./http";

type Schemas = components["schemas"];
export type StartCode = Schemas["StartCode"];
export type StartCodeIssueRequest = Schemas["StartCodeIssueRequest"];
export type QuestionnaireSummary = Schemas["QuestionnaireSummary"];
export type StaffAlert = Schemas["StaffAlert"];
export type InterventionAction = Schemas["InterventionAction"];
export type ResultSummary = Schemas["ResultSummary"];
export type SessionResult = Schemas["SessionResult"];
export type SessionStatus = Schemas["SessionStatus"];
export type QuestionSetUpload = Schemas["QuestionSetUpload"];
export type QuestionSetVersion = Schemas["QuestionSetVersion"];
export type ActiveQuestionSet = Schemas["ActiveQuestionSet"];
export type FailureCase = Schemas["FailureCase"];
export type CaseReview = Schemas["CaseReview"];
export type ReviewStatus = Schemas["ReviewStatus"];
export type DeidentifiedTrace = Schemas["DeidentifiedTrace"];

// 쪽 크기는 계약 기본값(30)을 서버가 쓰도록 limit 을 보내지 않는다.

export function useActiveQuestionnaires() {
  return useQuery({
    queryKey: ["questionnaires"],
    queryFn: async ({ signal }) => unwrap(await survey.GET("/v1/questionnaires", { signal })).questionnaires,
  });
}

/**
 * 시작 코드 발급. 같은 Idempotency-Key 로 다시 보내면 앞서 발급한 코드를 돌려주므로(계약),
 * 성공하기 전에는 같은 키를 쓰고(재시도가 코드를 둘 만들지 않게) 성공하면 다음 발급에 새 키를 쓴다.
 */
export function useIssueStartCode() {
  const key = useRef(newIdempotencyKey());
  return useMutation({
    mutationFn: async (body: StartCodeIssueRequest) => {
      const code = unwrap(await survey.POST("/v1/start-codes", { params: { header: { "Idempotency-Key": key.current } }, body }));
      key.current = newIdempotencyKey();
      return code;
    },
  });
}

// ---- 직원 알림(목록과 개입). 스트림은 alerts.ts ----

export function useAlertList(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: ["alerts"],
    enabled,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam, signal }) =>
      unwrap(await survey.GET("/v1/staff-alerts", { params: { query: pageParam === undefined ? {} : { cursor: pageParam } }, signal })),
    getNextPageParam: (page) => page.next_cursor,
  });
}

export function useDecideIntervention() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { sessionId: string; action: InterventionAction }) =>
      unwrap(await survey.POST("/v1/sessions/{session_id}/intervention", { params: { path: { session_id: input.sessionId } }, body: { action: input.action } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

// ---- 결과 ----

export function useResultList(status: SessionStatus | undefined) {
  return useInfiniteQuery({
    queryKey: ["results", status ?? "ALL"],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam, signal }) =>
      unwrap(
        await survey.GET("/v1/results", {
          params: { query: { ...(pageParam === undefined ? {} : { cursor: pageParam }), ...(status === undefined ? {} : { status }) } },
          signal,
        }),
      ),
    getNextPageParam: (page) => page.next_cursor,
    placeholderData: keepPreviousData,
  });
}

export function useResult(sessionId: string) {
  return useQuery({
    queryKey: ["result", sessionId],
    queryFn: async ({ signal }) => unwrap(await survey.GET("/v1/results/{session_id}", { params: { path: { session_id: sessionId } }, signal })),
    // 왜: 결과를 읽으면 서버가 읽은 사람과 때를 접근 기록에 남긴다(getResult 계약). 창 초점이나 재연결로 다시 읽으면 읽지 않은 접근이 기록된다.
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: Infinity,
  });
}

export function useAcknowledgeResult(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await survey.POST("/v1/results/{session_id}/acknowledgements", { params: { path: { session_id: sessionId } } })),
    onSuccess: async (ack) => {
      // 확인 기록을 결과에 바로 반영한다(다시 읽으면 접근 기록이 하나 더 남으므로 읽지 않는다)
      queryClient.setQueryData<SessionResult>(["result", sessionId], (current) =>
        current === undefined ? current : { ...current, acknowledged_by: ack.acknowledged_by, acknowledged_at: ack.acknowledged_at },
      );
      await queryClient.invalidateQueries({ queryKey: ["results"] });
    },
  });
}

// ---- 문항 세트 ----

export function useQuestionSetVersions() {
  return useInfiniteQuery({
    queryKey: ["question-sets"],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam, signal }) =>
      unwrap(await survey.GET("/v1/question-set-versions", { params: { query: pageParam === undefined ? {} : { cursor: pageParam } }, signal })),
    getNextPageParam: (page) => page.next_cursor,
  });
}

/** 문항 세트 올리기. 시작 코드와 같은 이유로 성공 전에는 같은 Idempotency-Key 를 쓴다. */
export function useUploadQuestionSet() {
  const queryClient = useQueryClient();
  const key = useRef(newIdempotencyKey());
  return useMutation({
    mutationFn: async (body: QuestionSetUpload) => {
      const version = unwrap(await survey.POST("/v1/question-set-versions", { params: { header: { "Idempotency-Key": key.current } }, body }));
      key.current = newIdempotencyKey();
      return version;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["question-sets"] }),
  });
}

export function useActivateQuestionSet() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (versionId: string) =>
      unwrap(await survey.POST("/v1/question-set-versions/{question_set_version_id}/activation", { params: { path: { question_set_version_id: versionId } } })),
    // 활성 여부(is_active)가 바뀌므로 문항 세트 목록도 다시 읽는다
    onSuccess: () => Promise.all([queryClient.invalidateQueries({ queryKey: ["questionnaires"] }), queryClient.invalidateQueries({ queryKey: ["question-sets"] })]),
  });
}

// ---- 실패 사례 ----

export function useFailureCaseList(reviewStatus: ReviewStatus | undefined) {
  return useInfiniteQuery({
    queryKey: ["cases", reviewStatus ?? "ALL"],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam, signal }) =>
      unwrap(
        await survey.GET("/v1/cases", {
          params: { query: { ...(pageParam === undefined ? {} : { cursor: pageParam }), ...(reviewStatus === undefined ? {} : { review_status: reviewStatus }) } },
          signal,
        }),
      ),
    getNextPageParam: (page) => page.next_cursor,
    placeholderData: keepPreviousData,
  });
}

export function useFailureCase(caseId: string) {
  return useQuery({
    queryKey: ["case", caseId],
    queryFn: async ({ signal }) => unwrap(await survey.GET("/v1/cases/{case_id}", { params: { path: { case_id: caseId } }, signal })),
  });
}

export function useDeidentifiedTrace(caseId: string) {
  return useQuery({
    queryKey: ["trace", caseId],
    queryFn: async ({ signal }) => unwrap(await survey.GET("/v1/deidentified-traces/{case_id}", { params: { path: { case_id: caseId } }, signal })),
  });
}

export function useReviewFailureCase(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: CaseReview) => {
      const result = await survey.POST("/v1/cases/{case_id}/reviews", { params: { path: { case_id: caseId } }, body });
      return unwrap(result);
    },
    onSuccess: async (updated) => {
      queryClient.setQueryData(["case", caseId], updated);
      await queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });
}
