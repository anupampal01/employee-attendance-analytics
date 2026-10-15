import React, { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client.js";
import { addDays, todayIst } from "../api/time.js";
import { useAllEmployees, useAsync } from "../hooks.js";
import { Card, DepartmentSelect, Empty, ErrorBox, Field, PageHeader, Spinner, Table, fmt } from "../components/ui.jsx";

export default function DepartmentTrend() {
  const employees = useAllEmployees();
  const [dept, setDept] = useState("");
  const [to, setTo] = useState(todayIst());
  const [from, setFrom] = useState(addDays(todayIst(), -29));
  const days = from && to ? (new Date(to) - new Date(from)) / 86400000 + 1 : 0;
  const rangeError = !from || !to ? null : to < from ? "To must not be before From" : days > 92 ? "Range must not exceed 92 days" : null;
  const res = useAsync(() => (dept && from && to && !rangeError ? api.departmentTrend(dept, from, to) : Promise.resolve(null)), [dept, from, to]);
  return (
    <>
      <PageHeader title="Department trend" subtitle="One row per calendar day with a 7-day moving average of the attendance rate" />
      <Card>
        <div className="filters">
          <Field label="Department"><DepartmentSelect employees={employees.data} value={dept} onChange={setDept} /></Field>
          <Field label="From"><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field label="To" error={rangeError}><input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></Field>
        </div>
        <ErrorBox error={res.error} onRetry={res.reload} />
        {!dept ? <Empty>Select a department.</Empty> : res.loading ? <Spinner /> : res.data && (
          <>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={res.data.items}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} />
                <YAxis domain={[0, 1]} />
                <Tooltip formatter={(v) => fmt(v, 4)} />
                <Legend />
                <Line type="monotone" dataKey="attendance_rate" name="Attendance rate" stroke="#9db7d1" dot={false} />
                <Line type="monotone" dataKey="moving_avg_7d" name="7-day average" stroke="#1f4e79" strokeWidth={2} dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
            <Table
              rowKey={(r) => r.date}
              rows={res.data.items}
              columns={[
                { key: "date", title: "Date" },
                { key: "is_working_day", title: "Working day", render: (r) => (r.is_working_day ? "Yes" : "Weekend") },
                { key: "headcount", title: "Headcount", num: true },
                { key: "present_count", title: "Present", num: true },
                { key: "late_count", title: "Late", num: true },
                { key: "attendance_rate", title: "Rate", num: true, render: (r) => fmt(r.attendance_rate, 4) },
                { key: "moving_avg_7d", title: "7-day avg", num: true, render: (r) => fmt(r.moving_avg_7d, 4) },
              ]}
            />
          </>
        )}
      </Card>
    </>
  );
}
