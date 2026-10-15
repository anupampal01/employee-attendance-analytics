"""Small helpers shared by the integration tests."""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def ist_dt(y, mo, d, h=0, mi=0, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=IST)


def ist_ms(y, mo, d, h=0, mi=0, s=0, ms=0):
    """Epoch milliseconds of an IST wall-clock time."""
    return (ist_dt(y, mo, d, h, mi, s) - EPOCH) // timedelta(milliseconds=1) + ms


def employee_body(emp_code="EMP0001", department="Engineering", **over):
    body = {"emp_code": emp_code, "name": f"Person {emp_code}", "email": f"{emp_code.lower()}@example.com",
            "department": department, "joined_on": "2026-01-05"}
    body.update(over)
    return body


def insert_employee(db, emp_code, department="Engineering", joined_on="2026-01-05", shift_start="09:30",
                    shift_end="18:30", name=None):
    doc = {"emp_code": emp_code, "name": name or f"Person {emp_code}", "email": f"{emp_code.lower()}@example.com",
           "department": department, "shift_start": shift_start, "shift_end": shift_end, "joined_on": joined_on,
           "created_at": datetime(2026, 1, 5, 4, 30, tzinfo=timezone.utc)}
    db.employees.insert_one(dict(doc))
    return doc


def insert_log(db, emp_code, date, status="PRESENT", late=0, overtime=0, half_day=False, work_hours=None,
               punch_in="auto", punch_out=None, history=None, legacy=False):
    """Insert a seeded attendance document directly (as the grader does). Derived values are given explicitly."""
    doc = {"emp_code": emp_code, "date": date, "status": status}
    if punch_in == "auto":
        punch_in = None if status in ("ABSENT", "LEAVE") else datetime.fromisoformat(date + "T04:00:00+00:00")
    doc["punch_in"] = punch_in
    doc["punch_out"] = punch_out
    doc["work_hours"] = work_hours
    doc["late_minutes"] = late
    doc["overtime_minutes"] = overtime
    if not legacy:
        doc["half_day"] = half_day
        doc["history"] = history if history is not None else []
    db.attendance_logs.insert_one(dict(doc))
    return doc


def strip(doc):
    doc = dict(doc)
    doc.pop("_id", None)
    return doc
