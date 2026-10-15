// IST (UTC+05:30) helpers. The API speaks epoch milliseconds; people speak IST wall-clock time.
const IST_OFFSET_MS = 330 * 60 * 1000;

// "2026-07-06T09:30" (datetime-local, interpreted as IST) -> epoch ms
export function istInputToMs(value) {
  if (!value) return undefined;
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(value);
  if (!m) return undefined;
  const [, y, mo, d, h, mi, s] = m.map(Number);
  return Date.UTC(y, mo - 1, d, h, mi, s || 0) - IST_OFFSET_MS;
}

const pad = (n) => String(n).padStart(2, "0");

// epoch ms -> "2026-07-06T09:30:00" in IST (used for datetime-local inputs)
export function msToIstInput(ms) {
  if (ms === null || ms === undefined) return "";
  const d = new Date(ms + IST_OFFSET_MS);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(
    d.getUTCMinutes()
  )}:${pad(d.getUTCSeconds())}`;
}

// epoch ms -> "06 Jul 2026, 09:30:05 IST"
export function formatIst(ms) {
  if (ms === null || ms === undefined) return "-";
  const d = new Date(ms + IST_OFFSET_MS);
  const mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.getUTCMonth()];
  return `${pad(d.getUTCDate())} ${mon} ${d.getUTCFullYear()}, ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(
    d.getUTCSeconds()
  )} IST`;
}

export function todayIst() {
  const d = new Date(Date.now() + IST_OFFSET_MS);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
}

export const currentMonthIst = () => todayIst().slice(0, 7);

export function addDays(dateStr, n) {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + n));
  return `${dt.getUTCFullYear()}-${pad(dt.getUTCMonth() + 1)}-${pad(dt.getUTCDate())}`;
}
