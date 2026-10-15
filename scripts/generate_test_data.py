"""Generate a deterministic synthetic dataset (about 100,000 attendance records by default).

Synthetic data is kept apart from the assignment's sample documents: it only ever lives in the database you point
MONGO_URI / MONGO_DB at. It deliberately contains the awkward cases from the business rules: employees with no logs,
mid-month joiners, overnight shifts, weekend records, missing weekdays, ABSENT/LEAVE records, half days, open records,
and many ties in late minutes. Derived fields are computed with the same helpers the API uses.

Usage (from the repository root, with the virtual environment active):
    python scripts/generate_test_data.py --drop            # ~100k records into MONGO_DB
    python scripts/generate_test_data.py --employees 50 --start 2026-06-01 --days 90 --drop
"""
import argparse
import os
import pathlib
import random
import sys
from datetime import date, datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from app.main import INDEX_SPECS, IST, derive_fields  # noqa: E402

DEPARTMENTS = ["Engineering", "Sales", "Operations", "Finance", "Support", "HR"]


def ist_to_utc(day: date, hhmm: str, extra_days: int = 0, offset_minutes: int = 0, seconds: int = 0) -> datetime:
    h, m = int(hhmm[:2]), int(hhmm[3:])
    local = datetime(day.year, day.month, day.day, h, m, tzinfo=IST) + timedelta(days=extra_days, minutes=offset_minutes, seconds=seconds)
    return local.astimezone(timezone.utc)


def build(args):
    rnd = random.Random(args.seed)
    start = date.fromisoformat(args.start)
    end = start + timedelta(days=args.days - 1)
    employees = []
    for i in range(1, args.employees + 1):
        overnight = rnd.random() < 0.06
        joined = start - timedelta(days=rnd.randint(30, 400))
        if rnd.random() < 0.10:                                   # mid-period joiner
            joined = start + timedelta(days=rnd.randint(1, max(1, args.days - 1)))
        employees.append({
            "emp_code": f"EMP{i:04d}", "name": f"Employee {i:04d}", "email": f"emp{i:04d}@example.com",
            "department": DEPARTMENTS[i % len(DEPARTMENTS)],
            "shift_start": "22:00" if overnight else rnd.choice(["09:30", "09:30", "09:30", "10:00", "08:00"]),
            "shift_end": "06:00" if overnight else rnd.choice(["18:30", "18:30", "18:30", "19:00", "17:00"]),
            "joined_on": joined.isoformat(),
            "created_at": datetime(2026, 1, 5, 4, 30, tzinfo=timezone.utc),
        })
    no_log_codes = {e["emp_code"] for e in employees[: max(1, args.employees // 40)]}   # a few people with no logs at all
    logs = []
    for emp in employees:
        if emp["emp_code"] in no_log_codes:
            continue
        joined = date.fromisoformat(emp["joined_on"])
        for offset in range(args.days):
            day = start + timedelta(days=offset)
            if day < joined:
                continue
            weekend = day.weekday() >= 5
            if rnd.random() < (0.93 if weekend else 0.07):          # mostly skip weekends; some weekdays are unrecorded
                continue
            status = rnd.choices(["PRESENT", "WFH", "ON_DUTY", "ABSENT", "LEAVE"], [70, 12, 5, 7, 6])[0]
            doc = {"emp_code": emp["emp_code"], "date": day.isoformat(), "status": status}
            if status in ("ABSENT", "LEAVE"):
                doc.update(punch_in=None, punch_out=None, **derive_fields(status, None, None, doc["date"], emp["shift_start"], emp["shift_end"]))
            else:
                late_roll = rnd.random()
                in_offset = rnd.randint(-25, 9) if late_roll < 0.7 else rnd.choice([11, 15, 20, 30, 45, 60, 90])   # many ties
                punch_in = ist_to_utc(day, emp["shift_start"], 0, in_offset, rnd.randint(0, 59))
                overnight = emp["shift_end"] <= emp["shift_start"]
                punch_out = None
                if rnd.random() < 0.96:
                    roll = rnd.random()
                    if roll < 0.06:                                   # short day -> half day
                        punch_out = punch_in + timedelta(hours=rnd.uniform(2, 4.4))
                    else:
                        punch_out = ist_to_utc(day, emp["shift_end"], 1 if overnight else 0,
                                               rnd.choice([-30, -5, 0, 10, 29, 30, 45, 90]), rnd.randint(0, 59))
                    punch_out = punch_out.replace(microsecond=0)
                    if punch_out <= punch_in:
                        punch_out = punch_in + timedelta(hours=8)
                doc.update(punch_in=punch_in, punch_out=punch_out,
                           **derive_fields(status, punch_in, punch_out, doc["date"], emp["shift_start"], emp["shift_end"]))
            doc["history"] = []
            logs.append(doc)
    return employees, logs, end


def main():
    load_dotenv(override=False)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--employees", type=int, default=440)
    ap.add_argument("--start", default="2025-09-01")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--drop", action="store_true", help="delete existing employees/attendance_logs first")
    ap.add_argument("--force", action="store_true", help="allow --drop on a database whose name does not look disposable")
    args = ap.parse_args()
    db_name = os.getenv("MONGO_DB", "attendance_db")
    # Safety: never wipe a database that might hold real data unless it is clearly a throw-away one.
    if args.drop and not args.force and not any(tag in db_name.lower() for tag in ("test", "verify", "demo", "synthetic")):
        sys.exit(f"Refusing to --drop collections in '{db_name}': the name does not contain test/verify/demo/synthetic. "
                 "Point MONGO_DB at a disposable database (e.g. attendance_verify) or pass --force.")

    employees, logs, end = build(args)
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), tz_aware=True)
    db = client[db_name]
    if args.drop:
        db.employees.delete_many({})
        db.attendance_logs.delete_many({})
    db.employees.insert_many(employees)
    for i in range(0, len(logs), 5000):
        db.attendance_logs.insert_many(logs[i:i + 5000], ordered=False)
    for collection, specs in INDEX_SPECS.items():                     # same indexes the API creates at startup
        for keys, options in specs:
            db[collection].create_index(keys, **options)
    print(f"{len(employees)} employees, {len(logs)} attendance records, {args.start} .. {end.isoformat()} "
          f"-> database '{db.name}'")


if __name__ == "__main__":
    main()
