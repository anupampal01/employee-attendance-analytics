import React, { useState } from "react";
import { api } from "../api/client.js";
import { formatIst } from "../api/time.js";
import { useAllEmployees, useAsync } from "../hooks.js";
import { Card, Empty, EmployeeSelect, ErrorBox, Field, PageHeader, Pagination, Spinner, StatusBadge, Table, fmt } from "../components/ui.jsx";

export const RecordColumns = [
  { key: "date", title: "Date" },
  { key: "emp_code", title: "Employee" },
  { key: "status", title: "Status", render: (r) => <StatusBadge status={r.status} /> },
  { key: "punch_in", title: "Punch in", render: (r) => formatIst(r.punch_in) },
  { key: "punch_out", title: "Punch out", render: (r) => formatIst(r.punch_out) },
  { key: "work_hours", title: "Hours", num: true, render: (r) => fmt(r.work_hours, 2) },
  { key: "late_minutes", title: "Late min", num: true },
  { key: "overtime_minutes", title: "OT min", num: true },
  { key: "half_day", title: "Half day", render: (r) => (r.half_day ? "Yes" : "") },
  { key: "history", title: "Edits", num: true, render: (r) => r.history.length },
];

export default function Attendance() {
  const [f, setF] = useState({ emp_code: "", date_from: "", date_to: "", status: "" });
  const [page, setPage] = useState(1);
  const employees = useAllEmployees();
  const pageSize = 20;
  const list = useAsync(() => api.listAttendance({ ...f, page, page_size: pageSize }), [f, page]);
  const set = (k) => (v) => { setF({ ...f, [k]: v }); setPage(1); };
  const badRange = f.date_from && f.date_to && f.date_from > f.date_to;

  return (
    <>
      <PageHeader title="Attendance records" subtitle="Newest first" />
      <Card>
        <div className="filters">
          <Field label="Employee"><EmployeeSelect employees={employees.data} value={f.emp_code} onChange={set("emp_code")} allowAll /></Field>
          <Field label="From" error={badRange ? "From must not be after To" : null}><input type="date" value={f.date_from} onChange={(e) => set("date_from")(e.target.value)} /></Field>
          <Field label="To"><input type="date" value={f.date_to} onChange={(e) => set("date_to")(e.target.value)} /></Field>
          <Field label="Status">
            <select value={f.status} onChange={(e) => set("status")(e.target.value)}>
              <option value="">All</option>
              {["PRESENT", "WFH", "ON_DUTY", "ABSENT", "LEAVE"].map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <button className="btn" onClick={() => { setF({ emp_code: "", date_from: "", date_to: "", status: "" }); setPage(1); }}>Clear</button>
        </div>
        {badRange ? null : <ErrorBox error={list.error} onRetry={list.reload} />}
        {list.loading ? <Spinner /> : list.data && list.data.items.length === 0 ? <Empty>No attendance records match these filters.</Empty> : list.data && (
          <Table rowKey={(r) => `${r.emp_code}|${r.date}`} rows={list.data.items} columns={RecordColumns} />
        )}
        {list.data && <Pagination page={page} pageSize={pageSize} total={list.data.total} onPage={setPage} />}
      </Card>
    </>
  );
}
