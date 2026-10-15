import React, { useState } from "react";
import { api } from "../api/client.js";
import { istInputToMs } from "../api/time.js";
import { useAllEmployees } from "../hooks.js";
import { Card, EmployeeSelect, ErrorBox, Field, Notice, PageHeader } from "../components/ui.jsx";
import { RecordColumns } from "./Attendance.jsx";
import { Table } from "../components/ui.jsx";

export default function PunchIn() {
  const employees = useAllEmployees();
  const [emp, setEmp] = useState("");
  const [status, setStatus] = useState("PRESENT");
  const [when, setWhen] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null); setResult(null);
    try {
      const body = { emp_code: emp, status };
      const ms = istInputToMs(when);
      if (ms !== undefined) body.punched_at = ms;
      setResult(await api.punchIn(body));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Punch in" subtitle="Creates the day's attendance record. Date, lateness and shift are derived by the server." />
      <Card>
        <ErrorBox error={error} />
        <ErrorBox error={employees.error} onRetry={employees.reload} />
        <form onSubmit={submit}>
          <div className="form-grid">
            <Field label="Employee"><EmployeeSelect employees={employees.data} value={emp} onChange={setEmp} /></Field>
            <Field label="Status">
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                {["PRESENT", "WFH", "ON_DUTY"].map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="Time (IST)" hint="Leave empty to use the current time">
              <input type="datetime-local" step="1" value={when} onChange={(e) => setWhen(e.target.value)} />
            </Field>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" disabled={!emp || busy}>{busy ? "Recording..." : "Record punch-in"}</button>
          </div>
        </form>
      </Card>
      {result && (
        <Card title="Recorded">
          <Notice kind="ok">Punch-in saved for {result.emp_code} on {result.date}.</Notice>
          <Table rowKey={(r) => r.date} rows={[result]} columns={RecordColumns} />
        </Card>
      )}
    </>
  );
}
