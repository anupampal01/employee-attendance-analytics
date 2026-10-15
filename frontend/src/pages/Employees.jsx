import React, { useState } from "react";
import { api } from "../api/client.js";
import { formatIst } from "../api/time.js";
import { useAllEmployees, useAsync } from "../hooks.js";
import { Card, DepartmentSelect, Empty, ErrorBox, Field, Modal, Notice, PageHeader, Pagination, Spinner, Table } from "../components/ui.jsx";

const BLANK = { emp_code: "", name: "", email: "", department: "", shift_start: "09:30", shift_end: "18:30", joined_on: "" };

function CreateForm({ onDone }) {
  const [form, setForm] = useState(BLANK);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createEmployee(form);
      onDone(created);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit}>
      <ErrorBox error={error} />
      <div className="form-grid">
        <Field label="Employee code" hint="EMP followed by 4-6 digits"><input required pattern="EMP[0-9]{4,6}" value={form.emp_code} onChange={set("emp_code")} placeholder="EMP0001" /></Field>
        <Field label="Name"><input required maxLength={100} value={form.name} onChange={set("name")} /></Field>
        <Field label="Email"><input required type="email" maxLength={120} value={form.email} onChange={set("email")} /></Field>
        <Field label="Department"><input required maxLength={50} value={form.department} onChange={set("department")} /></Field>
        <Field label="Shift start (IST)"><input required type="time" value={form.shift_start} onChange={set("shift_start")} /></Field>
        <Field label="Shift end (IST)" hint="Not later than start = overnight shift"><input required type="time" value={form.shift_end} onChange={set("shift_end")} /></Field>
        <Field label="Joined on"><input required type="date" value={form.joined_on} onChange={set("joined_on")} /></Field>
      </div>
      <div style={{ marginTop: 14 }}>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Saving..." : "Create employee"}</button>
      </div>
    </form>
  );
}

export default function Employees() {
  const [dept, setDept] = useState("");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState(null);
  const [flash, setFlash] = useState("");
  const pageSize = 20;
  const all = useAllEmployees();
  const list = useAsync(() => api.listEmployees({ department: dept, page, page_size: pageSize }), [dept, page]);
  const rows = (list.data ? list.data.items : []).filter(
    (e) => !search || `${e.emp_code} ${e.name} ${e.email}`.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <>
      <PageHeader title="Employees" subtitle="Directory and shift configuration">
        <button className="btn btn-primary" onClick={() => setCreating(true)}>Add employee</button>
      </PageHeader>
      {flash && <Notice kind="ok">{flash}</Notice>}
      <Card>
        <div className="filters">
          <Field label="Department">
            <DepartmentSelect employees={all.data} value={dept} onChange={(v) => { setDept(v); setPage(1); }} allowAll />
          </Field>
          <Field label="Search this page">
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search..." />
          </Field>
        </div>
        <ErrorBox error={list.error} onRetry={list.reload} />
        {list.loading ? <Spinner /> : rows.length === 0 ? <Empty>No employees match.</Empty> : (
          <Table
            rowKey={(r) => r.emp_code}
            rows={rows}
            columns={[
              { key: "emp_code", title: "Code", render: (r) => <button className="btn btn-small" onClick={() => setSelected(r)}>{r.emp_code}</button> },
              { key: "name", title: "Name" },
              { key: "department", title: "Department" },
              { key: "shift", title: "Shift (IST)", render: (r) => `${r.shift_start} - ${r.shift_end}` },
              { key: "joined_on", title: "Joined" },
            ]}
          />
        )}
        {list.data && <Pagination page={page} pageSize={pageSize} total={list.data.total} onPage={setPage} />}
      </Card>
      {creating && (
        <Modal title="Add employee" onClose={() => setCreating(false)}>
          <CreateForm onDone={(e) => { setCreating(false); setFlash(`Created ${e.emp_code}.`); setPage(1); list.reload(); all.reload(); }} />
        </Modal>
      )}
      {selected && (
        <Modal title={`${selected.emp_code} - ${selected.name}`} onClose={() => setSelected(null)}>
          <dl className="kv">
            <dt>Email</dt><dd>{selected.email}</dd>
            <dt>Department</dt><dd>{selected.department}</dd>
            <dt>Shift</dt><dd>{selected.shift_start} - {selected.shift_end} IST{selected.shift_end <= selected.shift_start ? " (overnight)" : ""}</dd>
            <dt>Joined on</dt><dd>{selected.joined_on}</dd>
            <dt>Created</dt><dd>{formatIst(selected.created_at)}</dd>
          </dl>
        </Modal>
      )}
    </>
  );
}
