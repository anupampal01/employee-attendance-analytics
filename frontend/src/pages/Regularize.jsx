import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { formatIst, istInputToMs, msToIstInput } from "../api/time.js";
import { useAllEmployees, useAsync } from "../hooks.js";
import { Card, Empty, EmployeeSelect, ErrorBox, Field, Notice, PageHeader, Spinner, Table } from "../components/ui.jsx";
import { RecordColumns } from "./Attendance.jsx";

function History({ history }) {
  if (!history.length) return <Empty>No manual corrections yet.</Empty>;
  return history.map((h, i) => (
    <div className="history-entry" key={i}>
      <div><strong>{h.by}</strong> <span className="muted small">{formatIst(h.at)}</span></div>
      <div>{h.reason}</div>
      <ul className="small" style={{ margin: "4px 0 0", paddingLeft: 18 }}>
        {Object.entries(h.changes).map(([field, c]) => {
          const show = (v) => (field === "punch_in" || field === "punch_out" ? formatIst(v) : String(v));
          return <li key={field}>{field}: {show(c.from)} to {show(c.to)}</li>;
        })}
      </ul>
    </div>
  ));
}

export default function Regularize() {
  const employees = useAllEmployees();
  const [emp, setEmp] = useState("");
  const [date, setDate] = useState("");
  const [loadKey, setLoadKey] = useState(0);
  const rec = useAsync(async () => {
    if (!emp || !date) return null;
    const res = await api.listAttendance({ emp_code: emp, date_from: date, date_to: date, page_size: 1 });
    return res.items[0] || false;
  }, [emp, date, loadKey]);
  const record = rec.data || null;

  const [status, setStatus] = useState("");
  const [pin, setPin] = useState("");
  const [pout, setPout] = useState("");
  const [reason, setReason] = useState("");
  const [by, setBy] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setStatus(record ? record.status : "");
    setPin(record ? msToIstInput(record.punch_in) : "");
    setPout(record ? msToIstInput(record.punch_out) : "");
    setReason("");
    setError(null);
  }, [record]);

  const noPunch = status === "ABSENT" || status === "LEAVE";

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null); setSaved(false);
    try {
      const body = { reason, regularized_by: by };
      if (status !== record.status) body.status = status;
      if (!noPunch) {
        const inMs = istInputToMs(pin), outMs = istInputToMs(pout);
        if (inMs !== undefined && inMs !== record.punch_in) body.punch_in = inMs;
        if (outMs !== undefined && outMs !== record.punch_out) body.punch_out = outMs;
      }
      await api.regularize(emp, date, body);
      setSaved(true);
      setLoadKey((k) => k + 1);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Regularization" subtitle="Correct a record. Derived values are recalculated by the server and every change is audited." />
      <Card>
        <div className="filters">
          <Field label="Employee"><EmployeeSelect employees={employees.data} value={emp} onChange={(v) => { setEmp(v); setSaved(false); }} /></Field>
          <Field label="Attendance date"><input type="date" value={date} onChange={(e) => { setDate(e.target.value); setSaved(false); }} /></Field>
        </div>
        <ErrorBox error={rec.error} onRetry={rec.reload} />
        {emp && date && rec.loading && <Spinner />}
        {emp && date && !rec.loading && rec.data === false && <Empty>No attendance record exists for {emp} on {date}.</Empty>}
      </Card>
      {record && (
        <>
          <Card title="Current record"><Table rowKey={(r) => r.date} rows={[record]} columns={RecordColumns} /></Card>
          <Card title="Correction">
            {saved && <Notice kind="ok">Correction saved and recorded in the audit history.</Notice>}
            <ErrorBox error={error} />
            <form onSubmit={submit}>
              <div className="form-grid">
                <Field label="Status">
                  <select value={status} onChange={(e) => setStatus(e.target.value)}>
                    {["PRESENT", "WFH", "ON_DUTY", "ABSENT", "LEAVE"].map((s) => <option key={s}>{s}</option>)}
                  </select>
                </Field>
                <Field label="Punch in (IST)" hint={noPunch ? "Cleared for ABSENT / LEAVE" : undefined}>
                  <input type="datetime-local" step="1" disabled={noPunch} value={noPunch ? "" : pin} onChange={(e) => setPin(e.target.value)} />
                </Field>
                <Field label="Punch out (IST)">
                  <input type="datetime-local" step="1" disabled={noPunch} value={noPunch ? "" : pout} onChange={(e) => setPout(e.target.value)} />
                </Field>
                <Field label="Reason" hint="5-200 characters"><input required minLength={5} maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
                <Field label="Corrected by"><input required maxLength={50} value={by} onChange={(e) => setBy(e.target.value)} /></Field>
              </div>
              <div style={{ marginTop: 14 }}><button className="btn btn-primary" disabled={busy}>{busy ? "Saving..." : "Save correction"}</button></div>
            </form>
          </Card>
          <Card title={`Audit history (${record.history.length})`}><History history={record.history} /></Card>
        </>
      )}
    </>
  );
}
