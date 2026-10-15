import React, { useState } from "react";
import { api } from "../api/client.js";
import { currentMonthIst } from "../api/time.js";
import { useAllEmployees, useAsync } from "../hooks.js";
import { Card, DepartmentSelect, Empty, ErrorBox, Field, PageHeader, Spinner, Table } from "../components/ui.jsx";

export default function Leaderboard() {
  const employees = useAllEmployees();
  const [month, setMonth] = useState(currentMonthIst());
  const [dept, setDept] = useState("");
  const [limit, setLimit] = useState(10);
  const res = useAsync(() => api.leaderboard({ month, limit, department: dept }), [month, dept, limit]);
  return (
    <>
      <PageHeader title="Late-comer leaderboard" subtitle="Ranked by total late minutes. Ties share a rank (1, 2, 2, 4) and are all returned." />
      <Card>
        <div className="filters">
          <Field label="Month"><input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} /></Field>
          <Field label="Department"><DepartmentSelect employees={employees.data} value={dept} onChange={setDept} allowAll /></Field>
          <Field label="Top ranks (1-50)"><input type="number" min={1} max={50} value={limit} onChange={(e) => setLimit(Math.min(50, Math.max(1, Number(e.target.value) || 1)))} /></Field>
        </div>
        <ErrorBox error={res.error} onRetry={res.reload} />
        {res.loading ? <Spinner /> : res.data && res.data.items.length === 0 ? <Empty>No late arrivals for this selection.</Empty> : res.data && (
          <Table
            rowKey={(r) => r.emp_code}
            rows={res.data.items}
            columns={[
              { key: "rank", title: "Rank" },
              { key: "emp_code", title: "Employee" },
              { key: "name", title: "Name" },
              { key: "department", title: "Department" },
              { key: "total_late_minutes", title: "Late minutes", num: true },
              { key: "late_count", title: "Late days", num: true },
            ]}
          />
        )}
      </Card>
    </>
  );
}
