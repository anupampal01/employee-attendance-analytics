// Central API client. All pages call the backend through this module.
const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TIMEOUT_MS = 30000;

export class ApiError extends Error {
  constructor(status, message, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function describe(status, detail) {
  if (status === 422 && Array.isArray(detail)) {
    return detail
      .map((d) => `${(d.loc || []).filter((p) => p !== "body" && p !== "query").join(".") || "request"}: ${d.msg}`)
      .join("; ");
  }
  if (typeof detail === "string") return detail;
  if (status === 503) return "The database is unavailable.";
  if (status >= 500) return "The server hit an unexpected error.";
  return `Request failed (${status}).`;
}

async function request(method, path, { params, body } = {}) {
  const url = new URL(BASE + path);
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
  } catch (e) {
    throw new ApiError(0, e.name === "AbortError" ? "The request timed out." : `Cannot reach the API at ${BASE}.`);
  } finally {
    clearTimeout(timer);
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) throw new ApiError(res.status, describe(res.status, data && data.detail), data && data.detail);
  return data;
}

export const api = {
  baseUrl: BASE,
  health: () => request("GET", "/health"),
  listEmployees: (params) => request("GET", "/employees", { params }),
  createEmployee: (body) => request("POST", "/employees", { body }),
  listAttendance: (params) => request("GET", "/attendance", { params }),
  punchIn: (body) => request("POST", "/attendance/punch-in", { body }),
  punchOut: (body) => request("POST", "/attendance/punch-out", { body }),
  regularize: (empCode, date, body) =>
    request("PATCH", `/attendance/${encodeURIComponent(empCode)}/${date}`, { body }),
  employeeMonthly: (empCode, month) =>
    request("GET", `/analytics/employees/${encodeURIComponent(empCode)}/monthly`, { params: { month } }),
  departmentSummary: (params) => request("GET", "/analytics/departments/summary", { params }),
  leaderboard: (params) => request("GET", "/analytics/leaderboard/late", { params }),
  departmentTrend: (dept, from, to) =>
    request("GET", `/analytics/departments/${encodeURIComponent(dept)}/trend`, { params: { from, to } }),
  explain: (name, params) => request("GET", `/admin/explain/${name}`, { params }),
};
