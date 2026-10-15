import React, { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client.js";
import { addDays, currentMonthIst, todayIst } from "../api/time.js";
import { useAllEmployees, useAsync } from "../hooks.js";
import { Card, DepartmentSelect, Empty, ErrorBox, Field, PageHeader, Spinner, Stat, Table, fmt } from "../components/ui.jsx";

export default function Dashboard() {
  const [month, setMonth] = useState(currentMonthIst());
  const [dept, setDept] = useState("");
  const employees = useAllEmployees();
  const summary = useAsync(() => api.departmentSummary({ month }), [month]);
  const board = useAsync(() => api.leaderboard({ month, limit: 5 }), [month]);
  const to = todayIst();
  const from = addDays(to, -29);
  const trend = useAsync(() => (dept ? api.departmentTrend(dept, from, to) : Promise.resolve(null)), [dept]);

  const items = summary.data ? summary.data.items : [];
  const headcount = items.reduce((a, d) => a + d.headcount, 0);
  const present = items.reduce((a, d) => a + d.present_days, 0);
  const late = items.reduce((a, d) => a + d.late_count, 0);
  const leave = items.reduce((a, d) => a + d.leave_count, 0);

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Live figures from the attendance database">
        <Field label="Month">
          <input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} />
        </Field>
      </PageHeader>
      <ErrorBox error={summary.error} onRetry={summary.reload} />
      {summary.loading ? (
        <Spinner />
      ) : (
        <div className="grid grid-4" style={{ marginBottom: 16 }}>
          <Stat label="Headcount" value={headcount} hint="joined on or before month end" />
          <Stat label="Present days" value={present} hint="Mon-Fri, half days = 0.5" />
          <Stat label="Late arrivals" value={late} />
          <Stat label="Leave records" value={leave} />
        </div>
      )}
      <div className="grid grid-2">
        <Card title="Department comparison (present days)">
          {summary.loading ? <Spinner /> : items.length === 0 ? <Empty>No departments for this month.</Empty> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={items}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="department" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="headcount" fill="#9db7d1" name="Headcount" />
                <Bar dataKey="present_days" fill="#1f4e79" name="Present days" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Top late-comers">
          <ErrorBox error={board.error} onRetry={board.reload} />
          {board.loading ? <Spinner /> : board.data && board.data.items.length === 0 ? <Empty>No late arrivals this month.</Empty> : board.data && (
            <Table
              rowKey={(r) => r.emp_code}
              rows={board.data.items}
              columns={[
                { key: "rank", title: "Rank" },
                { key: "emp_code", title: "Employee", render: (r) => `${r.emp_code} - ${r.name}` },
                { key: "department", title: "Department" },
                { key: "total_late_minutes", title: "Late min", num: true },
              ]}
            />
          )}
        </Card>
      </div>
      <Card
        title="Attendance trend, last 30 days"
        actions={<DepartmentSelect employees={employees.data} value={dept} onChange={setDept} />}
      >
        <ErrorBox error={trend.error} onRetry={trend.reload} />
        {!dept ? <Empty>Select a department to see its trend.</Empty> : trend.loading ? <Spinner /> : trend.data && (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trend.data.items}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} />
              <YAxis domain={[0, 1]} />
              <Tooltip formatter={(v) => fmt(v, 4)} />
              <Legend />
              <Line type="monotone" dataKey="attendance_rate" name="Attendance rate" stroke="#9db7d1" dot={false} connectNulls={false} />
              <Line type="monotone" dataKey="moving_avg_7d" name="7-day average" stroke="#1f4e79" strokeWidth={2} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>
    </>
  );
}
