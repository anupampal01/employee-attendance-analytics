import React, { useState } from "react";
import { api } from "../api/client.js";
import { useAsync } from "../hooks.js";
import { Card, ErrorBox, Field, Notice, PageHeader, Spinner } from "../components/ui.jsx";

const NEEDS = {
  attendance_list: [],
  employee_monthly: ["emp_code", "month"],
  department_summary: ["month"],
  late_leaderboard: ["month"],
  department_trend: ["department", "from", "to"],
};

export default function SystemHealth() {
  const health = useAsync(() => api.health(), []);
  const [name, setName] = useState("attendance_list");
  const [p, setP] = useState({ emp_code: "", month: "", department: "", from: "", to: "" });
  const [out, setOut] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const run = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null); setOut(null);
    try { setOut(await api.explain(name, p)); } catch (x) { setErr(x); } finally { setBusy(false); }
  };
  const text = out ? JSON.stringify(out.explain) : "";
  return (
    <>
      <PageHeader title="API health" subtitle={`Backend: ${api.baseUrl}`}>
        <button className="btn" onClick={health.reload}>Check again</button>
      </PageHeader>
      <Card title="Connection status">
        {health.loading ? <Spinner label="Checking" /> : health.error ? (
          <ErrorBox error={health.error} />
        ) : (
          <Notice kind="ok">API reachable and MongoDB responding ({JSON.stringify(health.data)}).</Notice>
        )}
      </Card>
      <Card title="Query plan inspector (GET /admin/explain)">
        <form onSubmit={run}>
          <div className="form-grid">
            <Field label="Endpoint">
              <select value={name} onChange={(e) => setName(e.target.value)}>{Object.keys(NEEDS).map((k) => <option key={k}>{k}</option>)}</select>
            </Field>
            {["emp_code", "month", "department", "from", "to"].map((k) => (
              <Field key={k} label={k}>
                <input value={p[k]} placeholder={k === "month" ? "YYYY-MM" : k === "from" || k === "to" ? "YYYY-MM-DD" : ""} onChange={(e) => setP({ ...p, [k]: e.target.value })} />
              </Field>
            ))}
          </div>
          <div style={{ marginTop: 14 }}><button className="btn btn-primary" disabled={busy}>{busy ? "Running..." : "Run explain"}</button></div>
        </form>
        <ErrorBox error={err} />
        {out && (
          <>
            <p>
              Collection <strong>{out.collection}</strong>: IXSCAN {text.includes("IXSCAN") ? "present" : "absent"}, COLLSCAN {text.includes("COLLSCAN") ? "PRESENT" : "absent"}.
            </p>
            <pre className="json">{JSON.stringify(out.explain, null, 2)}</pre>
          </>
        )}
      </Card>
    </>
  );
}
