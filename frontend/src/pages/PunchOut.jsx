import React, { useState } from "react";
import { api } from "../api/client.js";
import { istInputToMs } from "../api/time.js";
import { useAllEmployees, useAsync } from "../hooks.js";
import { Card, Empty, EmployeeSelect, ErrorBox, Field, Notice, PageHeader, Spinner, Table } from "../components/ui.jsx";
import { RecordColumns } from "./Attendance.jsx";

export default function PunchOut() {
  const employees = useAllEmployees();
  const [emp, setEmp] = useState("");
  const [when, setWhen] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  // recent records of the chosen employee; open ones (no punch-out) are the candidates
  const recent = useAsync(() => (emp ? api.listAttendance({ emp_code: emp, page_size: 10 }) : Promise.resolve(null)), [emp, result]);
  const open = recent.data ? recent.data.items.filter((r) => r.punch_in && !r.punch_out) : [];

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null); setResult(null);
    try {
      const body = { emp_code: emp };
      const ms = istInputToMs(when);
      if (ms !== undefined) body.punched_at = ms;
      setResult(await api.punchOut(body));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Punch out" subtitle="Closes the employee's most recent open record. Hours, overtime and half-day are derived by the server." />
      <Card>
        <ErrorBox error={error} />
        <form onSubmit={submit}>
          <div className="form-grid">
            <Field label="Employee"><EmployeeSelect employees={employees.data} value={emp} onChange={(v) => { setEmp(v); setResult(null); }} /></Field>
            <Field label="Time (IST)" hint="Leave empty to use the current time">
              <input type="datetime-local" step="1" value={when} onChange={(e) => setWhen(e.target.value)} />
            </Field>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" disabled={!emp || busy || open.length === 0}>{busy ? "Recording..." : "Record punch-out"}</button>
            {emp && !recent.loading && open.length === 0 && <span className="muted small" style={{ marginLeft: 12 }}>No open record for this employee.</span>}
          </div>
        </form>
      </Card>
      {emp && (
        <Card title="Open records for this employee">
          {recent.loading ? <Spinner /> : open.length === 0 ? <Empty>Nothing to punch out.</Empty> : (
            <Table rowKey={(r) => r.date} rows={open} columns={RecordColumns} />
          )}
        </Card>
      )}
      {result && (
        <Card title="Recorded">
          <Notice kind="ok">Punch-out saved for {result.emp_code} on {result.date}.</Notice>
          <Table rowKey={(r) => r.date} rows={[result]} columns={RecordColumns} />
        </Card>
      )}
    </>
  );
}
