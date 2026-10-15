"""Brute-force reference implementation of the analytics, written independently of the MongoDB pipelines.

It works on plain Python lists of employee / attendance dicts (as stored in MongoDB) and uses Decimal half-up
arithmetic. Integration tests compare the API (MongoDB aggregation) output with these results.
"""
import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

PRESENT = {"PRESENT", "WFH", "ON_DUTY"}


def q(value, places):
    return Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def d(s):
    return date.fromisoformat(s)


def month_range(month):
    y, m = int(month[:4]), int(month[5:7])
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"


def in_month(log, month):
    a, b = month_range(month)
    return a <= log["date"] <= b


def late(log):
    return log.get("late_minutes") or 0


def present_value(log):
    if log["status"] in PRESENT and d(log["date"]).weekday() < 5:
        return Decimal("0.5") if log.get("half_day") else Decimal(1)
    return Decimal(0)


def monthly(emp, logs, month):
    first, last = month_range(month)
    start = max(first, emp["joined_on"])
    working = 0
    if start <= last:
        day = d(start)
        while day <= d(last):
            working += day.weekday() < 5
            day += timedelta(days=1)
    mine = [l for l in logs if l["emp_code"] == emp["emp_code"] and in_month(l, month)]
    present = sum((present_value(l) for l in mine), Decimal(0))
    return {
        "emp_code": emp["emp_code"], "month": month, "working_days": working, "present_days": float(present),
        "leave_days": sum(l["status"] == "LEAVE" for l in mine),
        "late_count": sum(late(l) > 0 for l in mine),
        "total_late_minutes": sum(late(l) for l in mine),
        "total_overtime_minutes": sum(l.get("overtime_minutes") or 0 for l in mine),
        "attendance_pct": float(q(present * 100 / working, 2)) if working else None,
    }


def department_summary(employees, logs, month, department=None):
    _, last = month_range(month)
    by_dept = {}
    for e in employees:
        if e["joined_on"] <= last and (department is None or e["department"] == department):
            by_dept.setdefault(e["department"], []).append(e["emp_code"])
    items = []
    for dept in sorted(by_dept):
        codes = set(by_dept[dept])
        recs = [l for l in logs if l["emp_code"] in codes and in_month(l, month)]
        hours = [Decimal(str(l["work_hours"])) for l in recs if l["status"] in PRESENT and l.get("work_hours") is not None]
        items.append({
            "department": dept, "headcount": len(codes),
            "present_days": float(sum((present_value(l) for l in recs), Decimal(0))),
            "avg_work_hours": float(q(sum(hours) / len(hours), 2)) if hours else None,
            "late_count": sum(late(l) > 0 for l in recs),
            "total_late_minutes": sum(late(l) for l in recs),
            "leave_count": sum(l["status"] == "LEAVE" for l in recs),
            "on_duty_count": sum(l["status"] == "ON_DUTY" for l in recs),
        })
    return {"month": month, "items": items}


def leaderboard(employees, logs, month, limit=10, department=None):
    emp = {e["emp_code"]: e for e in employees}
    totals = {}
    for l in logs:
        if l["emp_code"] in emp and in_month(l, month) and late(l) > 0:
            if department is not None and emp[l["emp_code"]]["department"] != department:
                continue
            t = totals.setdefault(l["emp_code"], [0, 0])
            t[0] += late(l)
            t[1] += 1
    rows = sorted(((code, v[0], v[1]) for code, v in totals.items()), key=lambda r: (-r[1], r[0]))
    out = []
    for code, minutes, count in rows:
        rank = 1 + sum(1 for _, m, _ in rows if m > minutes)   # competition ranking: 1 + number of strictly better
        if rank <= limit:
            out.append({"rank": rank, "emp_code": code, "name": emp[code]["name"],
                        "department": emp[code]["department"], "total_late_minutes": minutes, "late_count": count})
    return {"month": month, "items": out}


def trend(employees, logs, department, date_from, date_to):
    members = {e["emp_code"]: e for e in employees if e["department"] == department}
    rows, rates = [], []
    day = d(date_from)
    while day <= d(date_to):
        ds = day.isoformat()
        recs = [l for l in logs if l["emp_code"] in members and l["date"] == ds]
        headcount = sum(1 for e in members.values() if e["joined_on"] <= ds)
        present = sum((Decimal("0.5") if l.get("half_day") else Decimal(1) for l in recs if l["status"] in PRESENT),
                      Decimal(0))
        working = day.weekday() < 5
        rate = q(present / headcount, 4) if working and headcount > 0 else None
        rates.append(rate)
        window = [r for r in rates[-7:] if r is not None]
        rows.append({
            "date": ds, "is_working_day": working, "headcount": headcount, "present_count": float(present),
            "late_count": sum(late(l) > 0 for l in recs),
            "attendance_rate": float(rate) if rate is not None else None,
            "moving_avg_7d": float(q(sum(window) / len(window), 4)) if window else None,
        })
        day += timedelta(days=1)
    return {"department": department, "items": rows}
