import React from "react";

export const Spinner = ({ label = "Loading" }) => (
  <div className="state" role="status">
    <span className="spinner" /> {label}...
  </div>
);

export const ErrorBox = ({ error, onRetry }) =>
  error ? (
    <div className="alert alert-error" role="alert">
      <strong>{error.status ? `Error ${error.status}` : "Error"}</strong>
      <span>{error.message}</span>
      {onRetry && (
        <button className="btn btn-small" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  ) : null;

export const Notice = ({ children, kind = "info" }) => (children ? <div className={`alert alert-${kind}`}>{children}</div> : null);

export const Empty = ({ children }) => <div className="state empty">{children}</div>;

export const Card = ({ title, actions, children }) => (
  <section className="card">
    {(title || actions) && (
      <header className="card-head">
        <h2>{title}</h2>
        <div className="card-actions">{actions}</div>
      </header>
    )}
    {children}
  </section>
);

export const PageHeader = ({ title, subtitle, children }) => (
  <div className="page-head">
    <div>
      <h1>{title}</h1>
      {subtitle && <p className="muted">{subtitle}</p>}
    </div>
    <div className="page-head-actions">{children}</div>
  </div>
);

export const Stat = ({ label, value, hint }) => (
  <div className="stat">
    <div className="stat-label">{label}</div>
    <div className="stat-value">{value}</div>
    {hint && <div className="muted small">{hint}</div>}
  </div>
);

export const StatusBadge = ({ status }) => <span className={`badge badge-${String(status).toLowerCase()}`}>{status}</span>;

export function Field({ label, error, hint, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="muted small">{hint}</span>}
      {error && <span className="field-error">{error}</span>}
    </label>
  );
}

export function Pagination({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="pagination">
      <span className="muted small">
        {from}-{to} of {total}
      </span>
      <button className="btn btn-small" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <span className="small">
        Page {page} / {pages}
      </span>
      <button className="btn btn-small" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </div>
  );
}

export function Modal({ title, onClose, children }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <header className="card-head">
          <h2>{title}</h2>
          <button className="btn btn-small" onClick={onClose} aria-label="Close">
            Close
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

export const EmployeeSelect = ({ employees, value, onChange, allowAll = false, id }) => (
  <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
    {allowAll ? <option value="">All employees</option> : <option value="">Select an employee...</option>}
    {(employees || []).map((e) => (
      <option key={e.emp_code} value={e.emp_code}>
        {e.emp_code} - {e.name}
      </option>
    ))}
  </select>
);

export const DepartmentSelect = ({ employees, value, onChange, allowAll = false }) => {
  const depts = [...new Set((employees || []).map((e) => e.department))].sort();
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {allowAll ? <option value="">All departments</option> : <option value="">Select a department...</option>}
      {depts.map((d) => (
        <option key={d} value={d}>
          {d}
        </option>
      ))}
    </select>
  );
};

export function Table({ columns, rows, rowKey }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.num ? "num" : undefined}>
                {c.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)}>
              {columns.map((c) => (
                <td key={c.key} className={c.num ? "num" : undefined}>
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const fmt = (v, digits) => (v === null || v === undefined ? "-" : digits !== undefined ? Number(v).toFixed(digits) : v);
export const pct = (v) => (v === null || v === undefined ? "-" : `${(v * 100).toFixed(1)}%`);
