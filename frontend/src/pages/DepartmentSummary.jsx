import React, { useState } from "react";
import { api } from "../api/client.js";
import { currentMonthIst } from "../api/time.js";
import { useAllEmployees, useAsync } from "../hooks.js";
import { Card, DepartmentSelect, Empty, ErrorBox, Field, PageHeader, Spinner, Table, fmt } from "../components/ui.jsx";

export default function DepartmentSummary() {
  const employees = useAllEmployees();
  const [month, setMonth] = useState(currentMonthIst());
  const [dept, setDept] = useState("");
  const res = useAsync(() => api.departmentSummary({ month, department: dept }), [month, dept]);
  return (
    <>
      <PageHeader title="Department summary" subtitle="Headcount includes everyone who joined on or before the month end, even without logs" />
      <Card>
        <div className="filters">
          <Field label="Month"><input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} /></Field>
          <Field label="Department"><DepartmentSelect employees={employees.data} value={dept} onChange={setDept} allowAll /></Field>
        </div>
        <ErrorBox error={res.error} onRetry={res.reload} />
        {res.loading ? <Spinner /> : res.data && res.data.items.length === 0 ? <Empty>No departments for this selection.</Empty> : res.data && (
          <Table
            rowKey={(r) => r.department}
            rows={res.data.items}
            columns={[
              { key: "department", title: "Department" },
              { key: "headcount", title: "Headcount", num: true },
              { key: "present_days", title: "Present days", num: true },
              { key: "avg_work_hours", title: "Avg work hours", num: true, render: (r) => fmt(r.avg_work_hours, 2) },
              { key: "late_count", title: "Late count", num: true },
              { key: "total_late_minutes", title: "Late minutes", num: true },
              { key: "leave_count", title: "Leave", num: true },
              { key: "on_duty_count", title: "On duty", num: true },
            ]}
          />
        )}
      </Card>
    </>
  );
}
