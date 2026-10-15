import React, { useState } from "react";
import { api } from "../api/client.js";
import { currentMonthIst } from "../api/time.js";
import { useAllEmployees, useAsync } from "../hooks.js";
import { Card, Empty, EmployeeSelect, ErrorBox, Field, PageHeader, Spinner, Stat, fmt } from "../components/ui.jsx";

export default function EmployeeMonthly() {
  const employees = useAllEmployees();
  const [emp, setEmp] = useState("");
  const [month, setMonth] = useState(currentMonthIst());
  const res = useAsync(() => (emp ? api.employeeMonthly(emp, month) : Promise.resolve(null)), [emp, month]);
  const d = res.data;
  return (
    <>
      <PageHeader title="Employee monthly analytics" />
      <Card>
        <div className="filters">
          <Field label="Employee"><EmployeeSelect employees={employees.data} value={emp} onChange={setEmp} /></Field>
          <Field label="Month"><input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} /></Field>
        </div>
        <ErrorBox error={res.error} onRetry={res.reload} />
        {!emp ? <Empty>Select an employee.</Empty> : res.loading ? <Spinner /> : d && (
          <div className="grid grid-4">
            <Stat label="Working days" value={d.working_days} hint="Mon-Fri from joining date" />
            <Stat label="Present days" value={d.present_days} hint="half days count 0.5" />
            <Stat label="Attendance" value={d.attendance_pct === null ? "n/a" : `${fmt(d.attendance_pct, 2)}%`} />
            <Stat label="Leave days" value={d.leave_days} />
            <Stat label="Late count" value={d.late_count} />
            <Stat label="Late minutes" value={d.total_late_minutes} />
            <Stat label="Overtime minutes" value={d.total_overtime_minutes} />
          </div>
        )}
      </Card>
    </>
  );
}
