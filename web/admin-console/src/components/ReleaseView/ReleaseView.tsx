import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { useForm } from "react-hook-form";

import type { components } from "../../contract/model-runtime";

type ModelPackageSummary = components["schemas"]["ModelPackageSummary"];
type ModelStatus = components["schemas"]["ModelStatus"];
type ModelPackageManifest = components["schemas"]["ModelPackageManifest"];
type ProblemDetails = components["schemas"]["ProblemDetails"];
type ModelLoadState = components["schemas"]["ModelLoadState"];

const LOAD_LABEL: Record<ModelLoadState, string> = { NOT_LOADED: "적재 안 됨", LOADING: "적재 중", READY: "준비됨", FAILED: "적재 실패(이전 패키지 유지)" };

interface Props {
  status: ModelStatus | undefined;
  statusError: string | undefined;
  /** 활성화 승인은 승인자 역할만 */
  canActivate: boolean;
  /** 롤백은 운영자나 승인자 */
  canRollback: boolean;
  /** 게시된 패키지 목록(최근 것이 먼저) */
  packages: ModelPackageSummary[];
  packagesLoading: boolean;
  packagesError: string | undefined;
  packagesHasMore: boolean;
  onLoadMorePackages: () => void;
  manifest: ModelPackageManifest | undefined;
  /** 지금 보고 있는 패키지의 digest(manifest 가 있을 때) */
  viewedDigest: string | undefined;
  manifestLoading: boolean;
  manifestProblem: ProblemDetails | undefined;
  actionPending: boolean;
  actionProblem: ProblemDetails | undefined;
  onViewPackage: (digest: string) => void;
  onActivate: (digest: string, reason: string) => void;
  onRollback: (targetDigest: string, reason: string) => void;
}

interface ReasonValues {
  reason: string;
}

type Pending = { kind: "activate"; digest: string } | { kind: "rollback"; digest: string };

function ProblemText({ problem }: { problem: ProblemDetails }) {
  return (
    <div role="alert">
      <p>{problem.title}</p>
      {problem.reason ? <p>사유: {problem.reason}</p> : null}
      {problem.detail ? <p>{problem.detail}</p> : null}
    </div>
  );
}

/** 모델 패키지: 적재 상태, 평가 보고서 확인, 활성화 승인, 롤백. 승인한 사람은 서버가 토큰에서 얻는다(화면은 신원을 보내지 않는다). */
export function ReleaseView(p: Props) {
  const [pending, setPending] = useState<Pending | null>(null);
  // 활성 여부는 목록의 값이다(계약 ModelPackageSummary.is_active). 목록에 없으면 알 수 없어 막지 않고 서버가 멱등으로 답한다.
  const viewedIsActive = p.packages.find((pkg) => pkg.package_digest === p.viewedDigest)?.is_active === true;
  const reasonForm = useForm<ReasonValues>({ defaultValues: { reason: "" } });

  const close = () => {
    setPending(null);
    reasonForm.reset();
  };
  const submitReason = (values: ReasonValues) => {
    if (pending === null) return;
    if (pending.kind === "activate") p.onActivate(pending.digest, values.reason);
    else p.onRollback(pending.digest, values.reason);
    close();
  };

  return (
    <section aria-labelledby="release-title">
      <h1 id="release-title">모델 패키지</h1>
      <h2>적재 상태</h2>
      {p.statusError ? <p role="alert">{p.statusError}</p> : null}
      {p.status ? (
        <dl>
          <dt>상태</dt>
          <dd role="status">{LOAD_LABEL[p.status.state]}</dd>
          <dt>활성 패키지</dt>
          <dd>{p.status.package_digest ?? "없음"}</dd>
          <dt>직전 패키지</dt>
          <dd>{p.status.previous_package_digest ?? "없음"}</dd>
          {p.status.activated_by ? (
            <>
              <dt>활성화한 사람</dt>
              <dd>{p.status.activated_by}</dd>
            </>
          ) : null}
        </dl>
      ) : null}
      {p.canRollback && p.status?.previous_package_digest ? (
        <button
          type="button"
          disabled={p.actionPending}
          onClick={() => {
            if (p.status?.previous_package_digest) setPending({ kind: "rollback", digest: p.status.previous_package_digest });
          }}
        >
          직전 패키지로 롤백
        </button>
      ) : null}

      <h2>게시된 패키지</h2>
      {p.packagesError ? <p role="alert">{p.packagesError}</p> : null}
      {p.packagesLoading ? <p>불러오는 중</p> : null}
      {!p.packagesLoading && p.packages.length === 0 ? <p>게시된 패키지가 없다</p> : null}
      {p.packages.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th scope="col">digest</th>
              <th scope="col">게시한 때</th>
              <th scope="col">활성 여부</th>
              <th scope="col">평가 보고서</th>
            </tr>
          </thead>
          <tbody>
            {p.packages.map((pkg) => (
              <tr key={pkg.package_digest}>
                <th scope="row">{pkg.package_digest}</th>
                <td>{pkg.published_at ? new Date(pkg.published_at).toLocaleString("ko-KR") : "알 수 없음"}</td>
                <td>{pkg.is_active ? "활성" : "비활성"}</td>
                <td>
                  <button type="button" disabled={p.manifestLoading} onClick={() => { p.onViewPackage(pkg.package_digest); }}>
                    {`${pkg.package_digest} 평가 보고서 보기`}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {p.packagesHasMore ? (
        <button type="button" onClick={p.onLoadMorePackages}>
          더 보기
        </button>
      ) : null}
      {p.manifestProblem ? <ProblemText problem={p.manifestProblem} /> : null}
      {p.manifestLoading ? <p>불러오는 중</p> : null}
      {p.manifest && p.viewedDigest ? (
        <div>
          <h3>목록표</h3>
          <dl>
            <dt>기반 모델</dt>
            <dd>{p.manifest.base_model}</dd>
            <dt>model-runtime 버전</dt>
            <dd>{p.manifest.model_runtime_version}</dd>
            <dt>모델 입출력</dt>
            <dd>{p.manifest.model_io_version}</dd>
            <dt>런타임 계약 버전</dt>
            <dd>{p.manifest.runtime_contract_version}</dd>
            <dt>학습 데이터셋 버전</dt>
            <dd>{p.manifest.lineage.dataset_version_id}</dd>
          </dl>
          <h4>어댑터</h4>
          <ul>
            {p.manifest.adapters.map((a) => (
              <li key={a.role}>
                {a.role}: 가중치 {a.weights.size} 바이트, 최대 토큰 {a.serving_config.max_new_tokens}, 온도 {a.serving_config.temperature}, 제약 디코딩 {a.serving_config.constrained_decoding ? "사용" : "안 씀"}
              </li>
            ))}
          </ul>
          <h3>평가 보고서</h3>
          <p>평가 데이터셋 {p.manifest.evaluation.dataset_version_id}, 만든 때 {new Date(p.manifest.evaluation.created_at).toLocaleString("ko-KR")}</p>
          <table>
            <thead>
              <tr>
                <th scope="col">묶음</th>
                <th scope="col">지표</th>
                <th scope="col">조각</th>
                <th scope="col">값</th>
                <th scope="col">단위</th>
                <th scope="col">표본 수</th>
              </tr>
            </thead>
            <tbody>
              {p.manifest.evaluation.metrics.map((m, index) => (
                <tr key={`${m.name}-${m.slice ?? ""}-${String(index)}`}>
                  <td>{m.group ?? ""}</td>
                  <th scope="row">{m.name}</th>
                  <td>{m.slice ?? "전체"}</td>
                  <td>{m.value}</td>
                  <td>{m.unit}</td>
                  <td>{m.sample_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {viewedIsActive ? <p role="status">이 패키지는 지금 활성이다</p> : null}
          {p.canActivate && !viewedIsActive ? (
            <button
              type="button"
              disabled={p.actionPending}
              onClick={() => {
                if (p.viewedDigest) setPending({ kind: "activate", digest: p.viewedDigest });
              }}
            >
              이 패키지 활성화 승인
            </button>
          ) : null}
        </div>
      ) : null}
      {p.actionProblem ? <ProblemText problem={p.actionProblem} /> : null}

      <Dialog.Root open={pending !== null} onOpenChange={(next) => { if (!next) close(); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="dialog">
            <Dialog.Title>{pending?.kind === "rollback" ? "롤백" : "활성화 승인"}</Dialog.Title>
            <Dialog.Description>
              {pending ? `${pending.digest} 패키지를 ${pending.kind === "rollback" ? "활성으로 되돌린다" : "활성으로 승인한다"}. 하는 사람은 로그인한 계정으로 기록된다.` : ""}
            </Dialog.Description>
            <form onSubmit={(event) => void reasonForm.handleSubmit(submitReason)(event)} noValidate>
              <label htmlFor="change-reason">사유</label>
              <textarea id="change-reason" rows={3} {...reasonForm.register("reason", { required: "사유를 입력한다" })} />
              {reasonForm.formState.errors.reason ? <p role="alert">{reasonForm.formState.errors.reason.message}</p> : null}
              <button type="submit">{pending?.kind === "rollback" ? "롤백" : "승인"}</button>
              <Dialog.Close asChild>
                <button type="button">취소</button>
              </Dialog.Close>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
