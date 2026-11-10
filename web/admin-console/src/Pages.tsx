// 조립(app 층): link 의 훅 결과를 컴포넌트 props 로 이어 준다.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import { useAlerts } from "./AlertsContext";
import { AlertView } from "./components/AlertView";
import { FailureCaseDetail, FailureCaseList } from "./components/FailureReviewView";
import { QuestionSetView } from "./components/QuestionSetView";
import { ReleaseView } from "./components/ReleaseView";
import { ResultDetail } from "./components/ResultDetail";
import { ResultList } from "./components/ResultList";
import { StartCodeView } from "./components/StartCodeView";
import { errorText, problemOf } from "./errors";
import { enablePush, isPushEnabled, pushSupport } from "./link/alerts";
import {
  useAcknowledgeResult,
  useActivateQuestionSet,
  useActiveQuestionnaires,
  useDecideIntervention,
  useDeidentifiedTrace,
  useFailureCase,
  useFailureCaseList,
  useIssueStartCode,
  useQuestionSetVersions,
  useResult,
  useResultList,
  useReviewFailureCase,
  useUploadQuestionSet,
  type ReviewStatus,
  type SessionStatus,
} from "./link/survey";
import { useActivateModelPackage, useModelPackage, useModelStatus, useRollbackModelPackage } from "./link/model";
import type { UserRole } from "./link/session";

export function StartCodePage() {
  const questionnaires = useActiveQuestionnaires();
  const issue = useIssueStartCode();
  return (
    <StartCodeView
      questionnaires={questionnaires.data ?? []}
      issued={issue.data}
      pending={issue.isPending}
      problem={problemOf(issue.error)}
      onIssue={(v) => {
        issue.mutate({ subject_ref: v.subjectRef, ...(v.questionnaireId === "" ? {} : { questionnaire_id: v.questionnaireId }) });
      }}
    />
  );
}

export function AlertsPage({ roles }: { roles: readonly UserRole[] }) {
  const alerts = useAlerts();
  const intervene = useDecideIntervention();
  const queryClient = useQueryClient();
  const push = useQuery({ queryKey: ["push-enabled"], queryFn: isPushEnabled });
  const [pushMessage, setPushMessage] = useState<string>();
  const pushState = pushSupport() === "unsupported" ? "unsupported" : push.data === true ? "on" : "off";
  return (
    <AlertView
      alerts={alerts.alerts}
      connection={alerts.connection}
      loading={alerts.isLoading}
      errorMessage={errorText(alerts.error)}
      hasMore={alerts.hasMore}
      canIntervene={roles.includes("staff")}
      pushState={pushState}
      pushMessage={pushMessage}
      interventionError={errorText(intervene.error)}
      onIntervene={(sessionId, action) => {
        intervene.mutate({ sessionId, action });
      }}
      onLoadMore={alerts.loadMore}
      onReconnect={alerts.reconnect}
      onEnablePush={() => {
        setPushMessage(undefined);
        enablePush().then(
          () => queryClient.invalidateQueries({ queryKey: ["push-enabled"] }),
          (error: unknown) => {
            setPushMessage(errorText(error));
          },
        );
      }}
      renderResultLink={(sessionId) => <Link to={`/results/${sessionId}`}> 결과 보기</Link>}
    />
  );
}

export function ResultsPage() {
  const [status, setStatus] = useState<SessionStatus | "">("");
  const list = useResultList(status === "" ? undefined : status);
  return (
    <ResultList
      rows={list.data?.pages.flatMap((page) => page.items) ?? []}
      statusFilter={status}
      loading={list.isLoading}
      errorMessage={errorText(list.error)}
      hasMore={list.hasNextPage}
      onStatusFilter={setStatus}
      onLoadMore={() => void list.fetchNextPage()}
      renderDetailLink={(sessionId, label) => <Link to={`/results/${sessionId}`}>{label}</Link>}
    />
  );
}

export function ResultDetailPage({ roles }: { roles: readonly UserRole[] }) {
  const { sessionId = "" } = useParams();
  const result = useResult(sessionId);
  const acknowledge = useAcknowledgeResult(sessionId);
  if (result.isLoading) return <p>불러오는 중</p>;
  if (result.data === undefined) return <p role="alert">{errorText(result.error) ?? "결과를 읽지 못했다"}</p>;
  return (
    <>
      <p className="no-print">
        <Link to="/results">목록으로</Link>
      </p>
      <ResultDetail
        result={result.data}
        canAcknowledge={roles.includes("clinician")}
        acknowledging={acknowledge.isPending}
        errorMessage={errorText(acknowledge.error)}
        onAcknowledge={() => {
          acknowledge.mutate();
        }}
      />
    </>
  );
}

export function QuestionSetsPage() {
  const list = useQuestionSetVersions();
  const upload = useUploadQuestionSet();
  const activate = useActivateQuestionSet();
  return (
    <QuestionSetView
      versions={list.data?.pages.flatMap((page) => page.items) ?? []}
      loading={list.isLoading}
      listError={errorText(list.error)}
      hasMore={list.hasNextPage}
      uploading={upload.isPending}
      uploadProblem={problemOf(upload.error)}
      uploaded={upload.data}
      activating={activate.isPending}
      activated={activate.data}
      activateError={errorText(activate.error)}
      onUpload={(body) => {
        upload.mutate(body);
      }}
      onActivate={(id) => {
        activate.mutate(id);
      }}
      onLoadMore={() => void list.fetchNextPage()}
    />
  );
}

export function CasesPage() {
  const [status, setStatus] = useState<ReviewStatus | "">("");
  const list = useFailureCaseList(status === "" ? undefined : status);
  return (
    <FailureCaseList
      cases={list.data?.pages.flatMap((page) => page.items) ?? []}
      statusFilter={status}
      loading={list.isLoading}
      errorMessage={errorText(list.error)}
      hasMore={list.hasNextPage}
      onStatusFilter={setStatus}
      onLoadMore={() => void list.fetchNextPage()}
      renderCaseLink={(caseId, label) => <Link to={`/cases/${caseId}`}>{label}</Link>}
    />
  );
}

export function CaseDetailPage() {
  const { caseId = "" } = useParams();
  const failureCase = useFailureCase(caseId);
  const trace = useDeidentifiedTrace(caseId);
  const review = useReviewFailureCase(caseId);
  if (failureCase.isLoading) return <p>불러오는 중</p>;
  if (failureCase.data === undefined) return <p role="alert">{errorText(failureCase.error) ?? "사례를 읽지 못했다"}</p>;
  return (
    <>
      <p>
        <Link to="/cases">목록으로</Link>
      </p>
      {/* key: 다른 검토자의 새 버전을 불러오면 폼을 새 값으로 다시 시작한다 */}
      <FailureCaseDetail
        key={failureCase.data.case_version}
        failureCase={failureCase.data}
        trace={trace.data}
        traceError={errorText(trace.error)}
        saving={review.isPending}
        problem={problemOf(review.error)}
        saved={review.isSuccess}
        onSubmit={(body) => {
          review.mutate(body);
        }}
        onReload={() => {
          review.reset();
          void failureCase.refetch();
        }}
      />
    </>
  );
}

export function ReleasePage({ roles }: { roles: readonly UserRole[] }) {
  const status = useModelStatus();
  const [digest, setDigest] = useState<string>();
  const pkg = useModelPackage(digest);
  const activate = useActivateModelPackage();
  const rollback = useRollbackModelPackage();
  return (
    <ReleaseView
      status={status.data}
      statusError={errorText(status.error)}
      canActivate={roles.includes("release-approver")}
      canRollback={roles.includes("release-approver") || roles.includes("operator")}
      manifest={pkg.data}
      viewedDigest={pkg.data === undefined ? undefined : digest}
      manifestLoading={pkg.isFetching}
      manifestProblem={problemOf(pkg.error)}
      actionPending={activate.isPending || rollback.isPending}
      actionProblem={problemOf(activate.error) ?? problemOf(rollback.error)}
      onViewPackage={setDigest}
      onActivate={(packageDigest, reason) => {
        rollback.reset();
        activate.mutate({ packageDigest, reason });
      }}
      onRollback={(targetPackageDigest, reason) => {
        activate.reset();
        rollback.mutate({ targetPackageDigest, reason });
      }}
    />
  );
}
