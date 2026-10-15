"""End-to-end verification of the 100,000-record dataset through the LIVE API.

Read-only against MongoDB (it only reads documents to feed the independent oracle). Run it against a database you
filled with `python scripts/generate_test_data.py --drop` (use a disposable MONGO_DB such as attendance_verify):

    uvicorn app.main:app --port 8000          # in another terminal, same MONGO_URI / MONGO_DB
    python scripts/verify_dataset.py --api http://localhost:8000

It checks, and prints PASS/FAIL for each:
  * /health
  * explain for all five endpoints: IXSCAN present, COLLSCAN absent, plus executionTimeMillis
  * department summary, leaderboard (several limits, with and without department), employee monthly (including
    employees with no logs) and department trend, all compared with tests/integration/oracle.py
  * wall-clock time of every call (fails above --max-seconds)
"""
import argparse
import json
import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "integration"))

from dotenv import load_dotenv  # noqa: E402
from pymongo import MongoClient  # noqa: E402

import oracle  # noqa: E402


def approx_equal(a, b):
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(approx_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(approx_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) < 1e-9
    return a == b


class Runner:
    def __init__(self, api, max_seconds):
        self.api, self.max_seconds, self.results = api.rstrip("/"), max_seconds, []

    def get(self, path, **params):
        url = self.api + path + ("?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}) if params else "")
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                body = json.loads(r.read())
        except Exception as exc:  # noqa: BLE001
            return None, time.perf_counter() - t0, str(exc)
        return body, time.perf_counter() - t0, None

    def record(self, name, ok, detail=""):
        self.results.append((name, ok))
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def main():
    load_dotenv(override=False)
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--max-seconds", type=float, default=10.0)
    args = ap.parse_args()
    run = Runner(args.api, args.max_seconds)

    body, secs, err = run.get("/health")
    run.record("health", err is None and body == {"status": "ok"}, err or "")
    if err:
        sys.exit("API not reachable; start it first")

    db = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), tz_aware=True)[os.getenv("MONGO_DB", "attendance_db")]
    employees = [{k: v for k, v in e.items() if k != "_id"} for e in db.employees.find()]
    logs = [{k: v for k, v in l.items() if k != "_id"} for l in db.attendance_logs.find()]
    print(f"dataset: {len(employees)} employees, {len(logs)} attendance records in '{db.name}'")
    run.record("dataset size >= 100000 records", len(logs) >= 100_000, f"({len(logs)})")
    dates = sorted({l["date"] for l in logs})
    months = sorted({d[:7] for d in dates})
    pick = [months[0], months[len(months) // 2], months[-1]]
    depts = sorted({e["department"] for e in employees})
    some_emp = employees[0]["emp_code"]
    busy_emp = max(logs, key=lambda l: l.get("late_minutes") or 0)["emp_code"]

    # explain
    m = pick[1]
    explain_calls = {
        "attendance_list": {"date_from": m + "-01", "date_to": m + "-28", "page_size": 20},
        "attendance_list (no filter)": {},
        "employee_monthly": {"emp_code": busy_emp, "month": m},
        "department_summary": {"month": m},
        "late_leaderboard": {"month": m, "limit": 10},
        "department_trend": {"department": depts[0], "from": m + "-01", "to": m + "-28"},
    }
    for name, params in explain_calls.items():
        ep = name.split(" ")[0]
        body, secs, err = run.get(f"/admin/explain/{ep}", **params)
        text = json.dumps(body["explain"]) if body else ""
        ok = body is not None and "executionStats" in text and "IXSCAN" in text and "COLLSCAN" not in text
        run.record(f"explain {name}: IXSCAN and no COLLSCAN", ok, err or f"({secs:.2f}s)")

    # analytics vs oracle
    def check(name, path, expected, **params):
        body, secs, err = run.get(path, **params)
        ok = err is None and approx_equal(body, expected) and secs <= run.max_seconds
        run.record(name, ok, err or f"({secs:.2f}s)")
        if err is None and not approx_equal(body, expected):
            print("   expected:", json.dumps(expected)[:400], "\n   got:     ", json.dumps(body)[:400])

    for month in pick:
        check(f"department summary {month}", "/analytics/departments/summary", oracle.department_summary(employees, logs, month), month=month)
        check(f"department summary {month} / {depts[0]}", "/analytics/departments/summary",
              oracle.department_summary(employees, logs, month, depts[0]), month=month, department=depts[0])
        for limit in (1, 5, 10, 50):
            check(f"leaderboard {month} limit={limit}", "/analytics/leaderboard/late",
                  oracle.leaderboard(employees, logs, month, limit), month=month, limit=limit)
        check(f"leaderboard {month} department={depts[-1]}", "/analytics/leaderboard/late",
              oracle.leaderboard(employees, logs, month, 10, depts[-1]), month=month, department=depts[-1])
        sample = [e for e in employees[:3]] + [e for e in employees if e["emp_code"] == busy_emp]
        logged = {l["emp_code"] for l in logs}
        sample += [e for e in employees if e["emp_code"] not in logged][:2]          # employees with no logs at all
        for e in sample:
            check(f"employee monthly {e['emp_code']} {month}", f"/analytics/employees/{e['emp_code']}/monthly",
                  oracle.monthly(e, logs, month), month=month)
    end = dates[-1]
    start = oracle.d(end).toordinal() - 91
    from datetime import date
    start_s = date.fromordinal(start).isoformat()
    for dept in depts:
        dept_logs = [l for l in logs if l["emp_code"] in {e["emp_code"] for e in employees if e["department"] == dept}]
        check(f"trend {dept} {start_s}..{end} (92 days)", f"/analytics/departments/{urllib.parse.quote(dept)}/trend",
              oracle.trend(employees, dept_logs, dept, start_s, end), **{"from": start_s, "to": end})

    failed = [n for n, ok in run.results if not ok]
    print(f"\n{sum(ok for _, ok in run.results)} passed, {len(failed)} failed of {len(run.results)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
