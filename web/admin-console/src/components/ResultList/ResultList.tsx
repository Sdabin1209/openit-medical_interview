import { createColumnHelper, tableFeatures, useTable } from "@tanstack/react-table";
import { createContext, type ReactNode, use } from "react";

import type { components } from "../../contract/survey-service";

type ResultSummary = components["schemas"]["ResultSummary"];
type SessionStatus = components["schemas"]["SessionStatus"];

export const STATUS_LABEL: Record<SessionStatus, string> = {
  ACTIVE: "진행 중",
  PAUSED: "멈춤",
  ENDED_COMPLETE: "완료",
  ENDED_PARTIAL: "부분(중간에 끝냄)",
  EXPIRED: "만료",
};

// 왜 모듈 범위: Table v9 는 features 가 렌더마다 새로 만들어지면 행 모델을 다시 만든다(공식 가이드).
const features = tableFeatures({});
const helper = createColumnHelper<typeof features, ResultSummary>();

// 왜 컨텍스트: 상세 링크를 그리는 함수는 렌더마다 새로 만들어진다. 열 정의가 렌더마다 바뀌면 셀이 다시 마운트되어
// 클릭 도중에 링크 요소가 바뀐다(userEvent 시험에서 확인). 열은 모듈 범위에 두고 링크 그리기는 컨텍스트로 받는다.
const DetailLinkContext = createContext<(sessionId: string, label: string) => ReactNode>(() => null);

function DetailLinkCell({ row }: { row: ResultSummary }) {
  return use(DetailLinkContext)(row.session_id, `${row.subject_ref} 결과 보기`);
}

const columns = helper.columns([
  helper.accessor("started_at", { header: "시작", cell: (info) => new Date(info.getValue()).toLocaleString("ko-KR") }),
  helper.accessor("subject_ref", { header: "대상자 참조값" }),
  helper.accessor("questionnaire_title", { header: "문진표", cell: (info) => info.getValue() ?? info.row.original.questionnaire_id }),
  helper.accessor("status", { header: "상태", cell: (info) => STATUS_LABEL[info.getValue()] }),
  helper.accessor("acknowledged_at", { header: "확인", cell: (info) => (info.getValue() === undefined ? "아직" : "확인함") }),
  helper.display({ id: "open", header: "상세", cell: (info) => <DetailLinkCell row={info.row.original} /> }),
]);

interface Props {
  rows: ResultSummary[];
  statusFilter: SessionStatus | "";
  loading: boolean;
  errorMessage: string | undefined;
  hasMore: boolean;
  onStatusFilter: (status: SessionStatus | "") => void;
  onLoadMore: () => void;
  /** 세션 하나의 상세로 가는 링크를 그리는 쪽(라우터)이 넘긴다 */
  renderDetailLink: (sessionId: string, label: string) => ReactNode;
}

/** 결과 목록(최근 것이 먼저). 끝나지 않은 세션은 부분 결과로 상태와 함께 나온다. */
export function ResultList({ rows, statusFilter, loading, errorMessage, hasMore, onStatusFilter, onLoadMore, renderDetailLink }: Props) {
  const table = useTable({ features, columns, data: rows });
  return (
    <DetailLinkContext value={renderDetailLink}>
    <section aria-labelledby="results-title">
      <h1 id="results-title">문진 결과</h1>
      <label htmlFor="status-filter">상태</label>
      <select id="status-filter" value={statusFilter} onChange={(event) => { onStatusFilter(event.target.value as SessionStatus | ""); }}>
        <option value="">모두</option>
        {(Object.keys(STATUS_LABEL) as SessionStatus[]).map((status) => (
          <option key={status} value={status}>
            {STATUS_LABEL[status]}
          </option>
        ))}
      </select>
      {errorMessage ? <p role="alert">{errorMessage}</p> : null}
      {loading ? <p>불러오는 중</p> : null}
      {!loading && rows.length === 0 && !errorMessage ? <p>결과가 없다</p> : null}
      <table>
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => (
                <th key={header.id} scope="col">
                  {header.isPlaceholder ? null : <table.FlexRender header={header} />}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}>
              {row.getAllCells().map((cell) => (
                <td key={cell.id}>
                  <table.FlexRender cell={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {hasMore ? (
        <button type="button" onClick={onLoadMore}>
          더 보기
        </button>
      ) : null}
    </section>
    </DetailLinkContext>
  );
}
