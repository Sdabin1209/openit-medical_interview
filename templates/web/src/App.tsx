// 조립(app 층): link 의 데이터를 components 에 props 로 이어 준다. 화면 라우팅은 react-router.
import { useState } from "react";
import { Link, Route, Routes } from "react-router";

import { ConfirmDialog } from "./components/ConfirmDialog";
import { GreetingTable, type Row } from "./components/GreetingTable";
import { HealthBadge } from "./components/HealthBadge";
import { NameForm } from "./components/NameForm";
import { useReadyz } from "./link/health";

function Home() {
  const readyz = useReadyz();
  const [rows, setRows] = useState<Row[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  return (
    <main>
      <h1>__AREA__</h1>
      <HealthBadge readyz={readyz.data} isLoading={readyz.isLoading} isError={readyz.isError} />
      <NameForm onSubmit={({ name }) => {
          setPending(name);
        }} />
      <GreetingTable rows={rows} />
      <ConfirmDialog
        open={pending !== null}
        title="추가할까요?"
        description={pending ?? ""}
        onConfirm={() => {
          if (pending !== null) setRows((current) => [...current, { id: current.length + 1, name: pending }]);
          setPending(null);
        }}
        onCancel={() => {
          setPending(null);
        }}
      />
      <Link to="/about">소개</Link>
    </main>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/about" element={<p>템플릿 예시 화면</p>} />
    </Routes>
  );
}
