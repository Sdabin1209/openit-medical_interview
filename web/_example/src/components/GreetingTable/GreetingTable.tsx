import { createColumnHelper, tableFeatures, useTable } from "@tanstack/react-table";

export interface Row {
  id: number;
  name: string;
}

// 왜 모듈 범위: Table v9 는 features·columns 가 렌더마다 새로 만들어지면 행 모델을 매번 다시 만든다(공식 가이드).
const features = tableFeatures({});
const helper = createColumnHelper<typeof features, Row>();
const columns = helper.columns([
  helper.accessor("id", { header: "번호" }),
  helper.accessor("name", { header: "이름" }),
]);

/** 표(@tanstack/react-table v9). 행은 props 로 받는다. */
export function GreetingTable({ rows }: { rows: Row[] }) {
  const table = useTable({ features, columns, data: rows });
  return (
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
  );
}
