"""Employee Attendance & Analytics API (FastAPI + MongoDB).

Contract: openapi.yaml (business rules R1-R10) and DATA_MODEL.md (stored shapes).
All application code lives in this one file, as the assignment requires.

Layout of the file
  1. Pure helpers (stdlib only): time zones, R1-R5 calculations, calendar maths, validators.
     The block between the BEGIN/END markers is exercised by tests/unit without any third-party package.
  2. Configuration, MongoDB connection and index creation.
  3. Request models and shared validators.
  4. Serialisation (BSON datetime <-> epoch milliseconds, no _id leaks).
  5. Aggregation pipeline builders (shared by the real endpoints and /admin/explain).
  6. Endpoints.
"""

# ======================================================================================================
# 1. PURE HELPERS  (stdlib only)
# ======================================================================================================
# ===== BEGIN PURE HELPERS =====
import calendar
import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

GRACE_SECONDS = 10 * 60            # R2: late only if strictly more than 10:00 after shift start
OVERTIME_MIN_MINUTES = 30          # R3
HALF_DAY_LIMIT = Decimal("4.50")   # R5
MAX_SHIFT_SPAN = timedelta(hours=24)
EPOCH_MS_MIN = 100_000_000_000
EPOCH_MS_MAX = 4_102_444_800_000

PRESENCE_STATUSES = ("PRESENT", "WFH", "ON_DUTY")        # R6
NO_PUNCH_STATUSES = ("ABSENT", "LEAVE")
ALL_STATUSES = PRESENCE_STATUSES + NO_PUNCH_STATUSES

_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_MONTH_RE = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
HHMM_PATTERN = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
MAX_TREND_DAYS = 92


def ms_to_dt(ms: int) -> datetime:
    """Epoch milliseconds -> aware UTC datetime, truncated to whole seconds (R1)."""
    return EPOCH + timedelta(seconds=ms // 1000)


def as_utc(value: datetime) -> datetime:
    """PyMongo returns naive datetimes unless tz_aware=True; naive values are always UTC in BSON."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def dt_to_ms(value: datetime) -> int:
    """Datetime -> integer epoch milliseconds (exact integer arithmetic, no float round-trip)."""
    return (as_utc(value) - EPOCH) // timedelta(milliseconds=1)


def trunc_seconds(value: datetime) -> datetime:
    return as_utc(value).replace(microsecond=0)


def trunc_millis(value: datetime) -> datetime:
    """BSON dates only hold milliseconds; used for server-set instants (created_at, history[].at)."""
    value = as_utc(value)
    return value.replace(microsecond=value.microsecond // 1000 * 1000)


def parse_hhmm(text: str):
    return int(text[0:2]), int(text[3:5])


def is_overnight(shift_start: str, shift_end: str) -> bool:
    """shift_end <= shift_start means the shift ends on the next calendar day (zero-padded HH:MM compares correctly)."""
    return shift_end <= shift_start


def _ist_datetime(date_str: str, hhmm: str) -> datetime:
    year, month, day = int(date_str[0:4]), int(date_str[5:7]), int(date_str[8:10])
    hour, minute = parse_hhmm(hhmm)
    return datetime(year, month, day, hour, minute, tzinfo=IST)


def attendance_date(punch_in: datetime, shift_start: str, shift_end: str) -> str:
    """R1: IST calendar date of the punch-in; for an overnight shift a punch-in whose IST time of day is earlier
    than shift_end belongs to the shift that started the previous day."""
    local = trunc_seconds(punch_in).astimezone(IST)
    day = local.date()
    if is_overnight(shift_start, shift_end):
        end_h, end_m = parse_hhmm(shift_end)
        if (local.hour, local.minute, local.second) < (end_h, end_m, 0):
            day = day - timedelta(days=1)
    return day.isoformat()


def shift_start_dt(date_str: str, shift_start: str) -> datetime:
    return _ist_datetime(date_str, shift_start)


def shift_end_dt(date_str: str, shift_start: str, shift_end: str) -> datetime:
    end = _ist_datetime(date_str, shift_end)
    return end + timedelta(days=1) if is_overnight(shift_start, shift_end) else end


def calc_late_minutes(punch_in: datetime, date_str: str, shift_start: str) -> int:
    """R2: late only when strictly more than 10:00 after shift start; then whole minutes since shift start."""
    seconds = int((trunc_seconds(punch_in) - shift_start_dt(date_str, shift_start)).total_seconds())
    return seconds // 60 if seconds > GRACE_SECONDS else 0


def calc_overtime_minutes(punch_out: datetime, date_str: str, shift_start: str, shift_end: str) -> int:
    """R3: whole minutes between shift end and punch-out, counted only when at least 30."""
    seconds = int((trunc_seconds(punch_out) - shift_end_dt(date_str, shift_start, shift_end)).total_seconds())
    minutes = seconds // 60 if seconds > 0 else 0
    return minutes if minutes >= OVERTIME_MIN_MINUTES else 0


def calc_work_hours(punch_in: datetime, punch_out: datetime) -> Decimal:
    """R4: (out - in) seconds / 3600, 2 decimals, decimal half-up (never float or banker's rounding)."""
    seconds = int((trunc_seconds(punch_out) - trunc_seconds(punch_in)).total_seconds())
    return (Decimal(seconds) / Decimal(3600)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calc_half_day(work_hours: Decimal) -> bool:
    """R5: judged on the already rounded work hours."""
    return work_hours < HALF_DAY_LIMIT


def derive_fields(status, punch_in, punch_out, date_str, shift_start, shift_end) -> dict:
    """Derived values stored with a record (DATA_MODEL.md, "For a record your own code writes")."""
    if status in NO_PUNCH_STATUSES or punch_in is None:
        return {"work_hours": None, "late_minutes": 0, "overtime_minutes": 0, "half_day": False}
    late = calc_late_minutes(punch_in, date_str, shift_start)
    if punch_out is None:
        return {"work_hours": None, "late_minutes": late, "overtime_minutes": 0, "half_day": False}
    hours = calc_work_hours(punch_in, punch_out)
    return {
        "work_hours": float(hours),
        "late_minutes": late,
        "overtime_minutes": calc_overtime_minutes(punch_out, date_str, shift_start, shift_end),
        "half_day": calc_half_day(hours),
    }


def round_half_up(value, places: int) -> Decimal:
    """R8 half-up rounding of a number (goes through str so a float such as 1.005 is read as written)."""
    quantum = Decimal(1).scaleb(-places)
    return Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)


def validate_date_str(text: str) -> str:
    if not _DATE_RE.match(text):
        raise ValueError("date must be YYYY-MM-DD")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise ValueError("not a real calendar date")
    return text


def validate_month_str(text: str) -> str:
    if not _MONTH_RE.match(text) or int(text[:4]) < 1:
        raise ValueError("month must be YYYY-MM")
    return text


def month_bounds(month: str):
    """('YYYY-MM-01', 'YYYY-MM-<last day>') for a validated YYYY-MM string."""
    year, mon = int(month[:4]), int(month[5:7])
    last = calendar.monthrange(year, mon)[1]
    return f"{year:04d}-{mon:02d}-01", f"{year:04d}-{mon:02d}-{last:02d}"


def count_working_days(month: str, joined_on: str) -> int:
    """R7: Monday-Friday days of the month, counted from joined_on when the employee joined mid-month."""
    first, last = month_bounds(month)
    start = max(first, joined_on)
    if start > last:
        return 0
    day = datetime.strptime(start, "%Y-%m-%d")
    end = datetime.strptime(last, "%Y-%m-%d")
    total = 0
    while day <= end:
        if day.weekday() < 5:
            total += 1
        day += timedelta(days=1)
    return total


def attendance_pct(present_days, working_days: int):
    """present_days / working_days x 100, 2 decimals half-up; None when there are no working days."""
    if working_days <= 0:
        return None
    ratio = Decimal(str(present_days)) * 100 / Decimal(working_days)
    return float(ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def days_in_range(date_from: str, date_to: str) -> int:
    """Number of calendar days from..to inclusive."""
    delta = datetime.strptime(date_to, "%Y-%m-%d") - datetime.strptime(date_from, "%Y-%m-%d")
    return delta.days + 1
# ===== END PURE HELPERS =====


# ======================================================================================================
# 2. CONFIGURATION, MONGODB, INDEXES
# ======================================================================================================
import json
import logging
import os
import random
import threading
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal, Optional

from bson import json_util
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AfterValidator, BaseModel, Field, model_validator
from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.errors import ConnectionFailure, DuplicateKeyError, ExecutionTimeout, PyMongoError

# override=False: real environment variables always win over a local .env file.
load_dotenv(override=False)

logger = logging.getLogger("attendance")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

AGGREGATE_MAX_TIME_MS = 25_000
PATCH_MAX_ATTEMPTS = 8

INDEX_SPECS = {
    "employees": [
        # uniqueness of emp_code (POST /employees race) + lookups by emp_code (leaderboard $lookup, sorted listing)
        ([("emp_code", ASCENDING)], {"unique": True, "name": "uq_emp_code"}),
        # GET /employees?department=...  (equality + sort by emp_code) and department/trend $match
        ([("department", ASCENDING), ("emp_code", ASCENDING)], {"name": "ix_dept_emp_code"}),
        # headcount: joined_on <= end of period (R9) for the department summary
        ([("joined_on", ASCENDING)], {"name": "ix_joined_on"}),
    ],
    "attendance_logs": [
        # one record per (emp_code, date): punch-in race guard, PATCH lookup, monthly analytics, $lookup joins
        ([("emp_code", ASCENDING), ("date", ASCENDING)], {"unique": True, "name": "uq_emp_date"}),
        # GET /attendance sort (date desc, emp_code asc), date ranges, month scans for the leaderboard
        ([("date", DESCENDING), ("emp_code", ASCENDING)], {"name": "ix_date_emp"}),
        # GET /attendance?status=... with the same sort
        ([("status", ASCENDING), ("date", DESCENDING), ("emp_code", ASCENDING)], {"name": "ix_status_date_emp"}),
        # punch-out: the employee's latest record with punch_in <= punched_at
        ([("emp_code", ASCENDING), ("punch_in", DESCENDING)], {"name": "ix_emp_punch_in"}),
    ],
}

_state_lock = threading.Lock()
_state: dict = {"client": None, "uri": None, "db_name": None, "indexes_ready": False}


def get_client() -> MongoClient:
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    with _state_lock:
        if _state["client"] is None or _state["uri"] != uri:
            if _state["client"] is not None:
                _state["client"].close()
            _state["client"] = MongoClient(
                uri,
                tz_aware=True,                 # aware UTC datetimes instead of PyMongo's naive default
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=60000,
                maxPoolSize=100,
            )
            _state["uri"] = uri
            _state["indexes_ready"] = False
        return _state["client"]


def get_db():
    return get_client()[os.getenv("MONGO_DB", "attendance_db")]


def employees_col():
    return get_db()["employees"]


def attendance_col():
    return get_db()["attendance_logs"]


def ensure_indexes() -> None:
    """Idempotent: create_index with an identical spec is a no-op."""
    db = get_db()
    for collection, specs in INDEX_SPECS.items():
        for keys, options in specs:
            db[collection].create_index(keys, **options)
    _state["indexes_ready"] = True


def ensure_indexes_once() -> None:
    if not _state["indexes_ready"]:
        try:
            ensure_indexes()
        except PyMongoError:
            logger.exception("index creation failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        ensure_indexes()
        logger.info("indexes ready")
    except PyMongoError:
        # Do not crash: /health reports 503 and retries index creation once MongoDB answers.
        logger.exception("could not create indexes at startup (MongoDB unreachable?)")
    yield
    with _state_lock:
        if _state["client"] is not None:
            _state["client"].close()
            _state["client"] = None


app = FastAPI(
    title="Employee Attendance & Analytics API",
    version="2.0.0",
    lifespan=lifespan,
)

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(PyMongoError)
async def mongo_error_handler(_request: Request, exc: PyMongoError):
    logger.error("MongoDB error: %r", exc)
    if isinstance(exc, (ConnectionFailure, ExecutionTimeout)):
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(Exception)
async def unhandled_error_handler(_request: Request, exc: Exception):
    logger.error("Unhandled error: %r", exc, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ======================================================================================================
# 3. REQUEST MODELS AND SHARED VALIDATORS
# ======================================================================================================
def _check_date(value: str) -> str:
    return validate_date_str(value)


def _check_month(value: str) -> str:
    return validate_month_str(value)


DateStr = Annotated[str, AfterValidator(_check_date)]
MonthStr = Annotated[str, AfterValidator(_check_month)]
# Strict integer: strings, floats (even 1.0) and booleans are rejected; seconds-looking values fail the lower bound.
EpochMs = Annotated[int, Field(strict=True, ge=EPOCH_MS_MIN, le=EPOCH_MS_MAX)]
StatusLiteral = Literal["PRESENT", "ABSENT", "LEAVE", "WFH", "ON_DUTY"]


def unprocessable(loc: tuple, message: str):
    """Raise a FastAPI-style 422 (body: {"detail": [ ... ]}) for rules that span several fields."""
    raise RequestValidationError([{"type": "value_error", "loc": loc, "msg": message, "input": None}])


class EmployeeCreate(BaseModel):
    emp_code: str = Field(pattern=r"^EMP[0-9]{4,6}$")
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    department: str = Field(min_length=1, max_length=50)
    shift_start: str = Field(default="09:30", pattern=HHMM_PATTERN)
    shift_end: str = Field(default="18:30", pattern=HHMM_PATTERN)
    joined_on: DateStr

    @model_validator(mode="after")
    def shifts_differ(self):
        if self.shift_start == self.shift_end:
            raise ValueError("shift_start must differ from shift_end")
        return self


# The contract's request schemas are NOT nullable: a field may be omitted, but an explicit JSON null is invalid.
# Pydantic does not validate defaults, so `field: Type = None` means "omitted -> None" while an explicit null fails
# validation with 422.
class PunchInRequest(BaseModel):
    emp_code: str
    punched_at: EpochMs = None
    status: Literal["PRESENT", "WFH", "ON_DUTY"] = "PRESENT"


class PunchOutRequest(BaseModel):
    emp_code: str
    punched_at: EpochMs = None


class RegularizeRequest(BaseModel):
    status: StatusLiteral = None
    punch_in: EpochMs = None
    punch_out: EpochMs = None
    reason: str = Field(min_length=5, max_length=200)
    regularized_by: str = Field(min_length=1, max_length=50)


PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


def check_date_order(date_from: Optional[str], date_to: Optional[str], loc_from="date_from", loc_to="date_to"):
    if date_from is not None and date_to is not None and date_from > date_to:
        unprocessable(("query", loc_from), f"{loc_from} must not be after {loc_to}")


def check_trend_range(d_from: str, d_to: str):
    if d_to < d_from:
        unprocessable(("query", "to"), "to must not be before from")
    if days_in_range(d_from, d_to) > MAX_TREND_DAYS:
        unprocessable(("query", "to"), f"range must not exceed {MAX_TREND_DAYS} days")


# ======================================================================================================
# 4. SERIALISATION
# ======================================================================================================
def _convert_instants(value: Any):
    """Turn BSON datetimes (also nested in history[].changes) into epoch milliseconds."""
    if isinstance(value, datetime):
        return dt_to_ms(value)
    if isinstance(value, dict):
        return {k: _convert_instants(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_instants(v) for v in value]
    return value


def serialize_employee(doc: dict) -> dict:
    return {
        "emp_code": doc["emp_code"],
        "name": doc.get("name"),
        "email": doc.get("email"),
        "department": doc.get("department"),
        "shift_start": doc.get("shift_start", "09:30"),
        "shift_end": doc.get("shift_end", "18:30"),
        "joined_on": doc.get("joined_on"),
        "created_at": dt_to_ms(doc["created_at"]) if doc.get("created_at") is not None else None,
    }


def serialize_history(entry: dict) -> dict:
    return {
        "at": dt_to_ms(entry["at"]) if isinstance(entry.get("at"), datetime) else entry.get("at"),
        "by": entry.get("by"),
        "reason": entry.get("reason"),
        "changes": _convert_instants(entry.get("changes") or {}),
    }


def serialize_attendance(doc: dict) -> dict:
    """Public shape of a record. No _id; missing derived fields take their DATA_MODEL defaults."""
    work_hours = doc.get("work_hours")
    return {
        "emp_code": doc["emp_code"],
        "date": doc["date"],
        "status": doc["status"],
        "punch_in": dt_to_ms(doc["punch_in"]) if doc.get("punch_in") is not None else None,
        "punch_out": dt_to_ms(doc["punch_out"]) if doc.get("punch_out") is not None else None,
        "work_hours": float(work_hours) if work_hours is not None else None,
        "late_minutes": int(doc.get("late_minutes") or 0),
        "overtime_minutes": int(doc.get("overtime_minutes") or 0),
        "half_day": bool(doc.get("half_day") or False),
        "history": [serialize_history(h) for h in (doc.get("history") or [])],
    }


def page_response(items: list, total: int, page: int, page_size: int) -> dict:
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_employee_or_404(emp_code: str) -> dict:
    doc = employees_col().find_one({"emp_code": emp_code}, {"_id": 0})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Employee {emp_code} not found")
    return doc


# ======================================================================================================
# 5. AGGREGATION PIPELINE BUILDERS (shared by the endpoints and /admin/explain)
# ======================================================================================================
# Field references: base "$" addresses a field of the current document ("$status"); base "$$l." addresses a field of
# the loop variable `l` inside $map/$filter ("$$l.status"); "$log." addresses an unwound sub-document.
def _presence(b: str) -> dict:
    return {"$in": [b + "status", list(PRESENCE_STATUSES)]}


def _is_weekday(b: str) -> dict:
    return {"$lte": [{"$isoDayOfWeek": {"$dateFromString": {"dateString": b + "date", "format": "%Y-%m-%d"}}}, 5]}


def _late(b: str) -> dict:
    return {"$ifNull": [b + "late_minutes", 0]}


def _overtime(b: str) -> dict:
    return {"$ifNull": [b + "overtime_minutes", 0]}


def _half_day_value(b: str) -> dict:
    """A present record is worth 1 day, or 0.5 when half_day (missing means false)."""
    return {"$cond": [{"$eq": [{"$ifNull": [b + "half_day", False]}, True]}, 0.5, 1]}


def _present_days_value(b: str) -> dict:
    """R5-R7: present status AND Monday-Friday -> 1 / 0.5, otherwise 0."""
    return {"$cond": [{"$and": [_presence(b), _is_weekday(b)]}, _half_day_value(b), 0]}


def _half_up_decimal(expr: Any, places: int) -> dict:
    """R8 half-up in the database. $round rounds ties to even, so floor(x * 10^p + 0.5) / 10^p is done in exact
    Decimal128 arithmetic instead (values here are never negative)."""
    scale = 10 ** places
    return {"$divide": [{"$floor": {"$add": [{"$multiply": [{"$toDecimal": expr}, scale]}, 0.5]}}, scale]}


def _half_up_double(expr: Any, places: int) -> dict:
    return {"$toDouble": _half_up_decimal(expr, places)}


def build_employee_monthly_pipeline(emp_code: str, month: str) -> list:
    start, end = month_bounds(month)
    return [
        {"$match": {"emp_code": emp_code, "date": {"$gte": start, "$lte": end}}},
        {"$group": {
            "_id": None,
            "present_days": {"$sum": _present_days_value("$")},
            "leave_days": {"$sum": {"$cond": [{"$eq": ["$status", "LEAVE"]}, 1, 0]}},
            "late_count": {"$sum": {"$cond": [{"$gt": [_late("$"), 0]}, 1, 0]}},
            "total_late_minutes": {"$sum": _late("$")},
            "total_overtime_minutes": {"$sum": _overtime("$")},
        }},
    ]


def build_department_summary_pipeline(month: str, department: Optional[str]) -> list:
    """Starts from `employees` so that people without logs still count (R9), then joins the month's logs."""
    start, end = month_bounds(month)
    match: dict = {"joined_on": {"$lte": end}}
    if department is not None:
        match["department"] = department
    L = "$$l."
    work_hour_logs = {"$filter": {"input": "$logs", "as": "l",
                                  "cond": {"$and": [_presence(L), {"$isNumber": L + "work_hours"}]}}}

    def count_where(cond: dict) -> dict:
        return {"$size": {"$filter": {"input": "$logs", "as": "l", "cond": cond}}}

    return [
        {"$match": match},
        {"$lookup": {
            "from": "attendance_logs", "localField": "emp_code", "foreignField": "emp_code",
            "pipeline": [
                {"$match": {"date": {"$gte": start, "$lte": end}}},
                {"$project": {"_id": 0, "status": 1, "date": 1, "late_minutes": 1, "half_day": 1, "work_hours": 1}},
            ],
            "as": "logs",
        }},
        {"$project": {
            "department": 1,
            "present_days": {"$sum": {"$map": {"input": "$logs", "as": "l", "in": _present_days_value(L)}}},
            "late_count": count_where({"$gt": [_late(L), 0]}),
            "total_late_minutes": {"$sum": {"$map": {"input": "$logs", "as": "l", "in": _late(L)}}},
            "leave_count": count_where({"$eq": [L + "status", "LEAVE"]}),
            "on_duty_count": count_where({"$eq": [L + "status", "ON_DUTY"]}),
            # exact decimal sum + count of present-status records that have work_hours (average over records)
            "wh_sum": {"$sum": {"$map": {"input": work_hour_logs, "as": "l", "in": {"$toDecimal": L + "work_hours"}}}},
            "wh_cnt": {"$size": work_hour_logs},
        }},
        {"$group": {
            "_id": "$department",
            "headcount": {"$sum": 1},
            "present_days": {"$sum": "$present_days"},
            "late_count": {"$sum": "$late_count"},
            "total_late_minutes": {"$sum": "$total_late_minutes"},
            "leave_count": {"$sum": "$leave_count"},
            "on_duty_count": {"$sum": "$on_duty_count"},
            "wh_sum": {"$sum": "$wh_sum"},
            "wh_cnt": {"$sum": "$wh_cnt"},
        }},
        {"$sort": {"_id": 1}},
        {"$project": {
            "_id": 0,
            "department": "$_id",
            "headcount": 1,
            "present_days": {"$toDouble": "$present_days"},
            "avg_work_hours": {"$cond": [{"$gt": ["$wh_cnt", 0]},
                                         _half_up_double({"$divide": ["$wh_sum", "$wh_cnt"]}, 2), None]},
            "late_count": 1,
            "total_late_minutes": 1,
            "leave_count": 1,
            "on_duty_count": 1,
        }},
    ]


def build_late_leaderboard_pipeline(month: str, limit: int, department: Optional[str]) -> list:
    """Total late minutes per employee, competition ranking with $rank (1, 2, 2, 4), limit applied after ranking."""
    start, end = month_bounds(month)
    pipeline: list = [
        {"$match": {"date": {"$gte": start, "$lte": end}, "late_minutes": {"$gt": 0}}},
        {"$group": {"_id": "$emp_code", "total_late_minutes": {"$sum": "$late_minutes"}, "late_count": {"$sum": 1}}},
        {"$lookup": {"from": "employees", "localField": "_id", "foreignField": "emp_code", "as": "emp"}},
        {"$unwind": "$emp"},  # logs whose employee does not exist are dropped here
    ]
    if department is not None:
        pipeline.append({"$match": {"emp.department": department}})  # ranking happens inside the department
    pipeline += [
        {"$setWindowFields": {"sortBy": {"total_late_minutes": -1}, "output": {"rank": {"$rank": {}}}}},
        {"$match": {"rank": {"$lte": limit}}},
        {"$sort": {"total_late_minutes": -1, "_id": 1}},
        {"$project": {"_id": 0, "rank": 1, "emp_code": "$_id", "name": "$emp.name", "department": "$emp.department",
                      "total_late_minutes": 1, "late_count": 1}},
    ]
    return pipeline


def build_department_trend_pipeline(department: str, date_from: str, date_to: str) -> list:
    """One row per calendar day. The calendar (gap filling) is generated inside MongoDB with $range and merged with the
    per-day log aggregates through $unionWith; the 7-day moving average is a $setWindowFields over the ordered rows."""
    days = days_in_range(date_from, date_to)
    start_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=UTC)
    calendar_rows = [
        {"$match": {"department": department}},
        {"$group": {"_id": None, "joins": {"$push": "$joined_on"}}},
        {"$project": {"_id": 0, "joins": 1, "offset": {"$range": [0, days]}}},
        {"$unwind": "$offset"},
        {"$project": {"joins": 1, "day": {"$dateToString": {
            "format": "%Y-%m-%d",
            "date": {"$add": [start_dt, {"$multiply": ["$offset", 86_400_000]}]}}}}},
        {"$project": {  # headcount (R9): department employees with joined_on <= that day
            "_id": "$day",
            "headcount": {"$size": {"$filter": {"input": "$joins", "as": "j", "cond": {"$lte": ["$$j", "$day"]}}}},
            "present_count": {"$literal": 0},
            "late_count": {"$literal": 0},
        }},
    ]
    return [
        {"$match": {"department": department}},
        {"$lookup": {
            "from": "attendance_logs", "localField": "emp_code", "foreignField": "emp_code",
            "pipeline": [
                {"$match": {"date": {"$gte": date_from, "$lte": date_to}}},
                {"$project": {"_id": 0, "date": 1, "status": 1, "late_minutes": 1, "half_day": 1}},
            ],
            "as": "log",
        }},
        {"$unwind": "$log"},
        {"$group": {
            "_id": "$log.date",
            "present_count": {"$sum": {"$cond": [_presence("$log."), _half_day_value("$log."), 0]}},
            "late_count": {"$sum": {"$cond": [{"$gt": [_late("$log."), 0]}, 1, 0]}},
        }},
        {"$unionWith": {"coll": "employees", "pipeline": calendar_rows}},
        {"$group": {
            "_id": "$_id",
            "headcount": {"$max": "$headcount"},
            "present_count": {"$sum": "$present_count"},
            "late_count": {"$sum": "$late_count"},
        }},
        {"$sort": {"_id": 1}},
        {"$addFields": {"is_working_day": {"$lte": [{"$isoDayOfWeek": {
            "$dateFromString": {"dateString": "$_id", "format": "%Y-%m-%d"}}}, 5]}}},
        {"$addFields": {"rate": {"$cond": [
            {"$and": ["$is_working_day", {"$gt": ["$headcount", 0]}]},
            _half_up_decimal({"$divide": [{"$toDecimal": "$present_count"}, "$headcount"]}, 4),
            None]}}},
        {"$setWindowFields": {"sortBy": {"_id": 1},
                              "output": {"moving": {"$avg": "$rate", "window": {"documents": [-6, 0]}}}}},
        {"$project": {
            "_id": 0,
            "date": "$_id",
            "is_working_day": 1,
            "headcount": 1,
            "present_count": {"$toDouble": "$present_count"},
            "late_count": 1,
            "attendance_rate": {"$toDouble": "$rate"},
            "moving_avg_7d": {"$cond": [{"$eq": [{"$ifNull": ["$moving", None]}, None]},
                                        None, _half_up_double("$moving", 4)]},
        }},
    ]


def build_attendance_query(emp_code, date_from, date_to, status, page: int, page_size: int) -> dict:
    flt: dict = {}
    if emp_code is not None:
        flt["emp_code"] = emp_code
    if date_from is not None or date_to is not None:
        flt["date"] = {}
        if date_from is not None:
            flt["date"]["$gte"] = date_from
        if date_to is not None:
            flt["date"]["$lte"] = date_to
    if status is not None:
        flt["status"] = status
    return {
        "filter": flt,
        "sort": {"date": -1, "emp_code": 1},
        "skip": (page - 1) * page_size,
        "limit": page_size,
    }


# ======================================================================================================
# 6. ENDPOINTS
# ======================================================================================================
@app.get("/health", tags=["system"])
def health():
    try:
        get_db().command("ping")
    except PyMongoError:
        return JSONResponse(status_code=503, content={"detail": "MongoDB is not reachable"})
    ensure_indexes_once()
    return {"status": "ok"}


# ---------------------------------------------------------------------------------------- employees
@app.post("/employees", status_code=201, tags=["employees"])
def create_employee(body: EmployeeCreate):
    doc = {
        "emp_code": body.emp_code,
        "name": body.name,
        "email": body.email,
        "department": body.department,
        "shift_start": body.shift_start,
        "shift_end": body.shift_end,
        "joined_on": body.joined_on,
        "created_at": trunc_millis(datetime.now(UTC)),
    }
    try:
        employees_col().insert_one(doc)  # the unique index on emp_code decides races, not a prior read
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail=f"Employee {body.emp_code} already exists")
    return serialize_employee(doc)


@app.get("/employees", tags=["employees"])
def list_employees(department: Optional[str] = None, page: PageParam = 1, page_size: PageSizeParam = 20):
    flt = {"department": department} if department is not None else {}
    cursor = (employees_col().find(flt, {"_id": 0}).sort("emp_code", ASCENDING)
              .skip((page - 1) * page_size).limit(page_size))
    items = [serialize_employee(d) for d in cursor]
    total = employees_col().count_documents(flt)
    return page_response(items, total, page, page_size)


# ---------------------------------------------------------------------------------------- attendance
@app.post("/attendance/punch-in", status_code=201, tags=["attendance"])
def punch_in(body: PunchInRequest):
    emp = get_employee_or_404(body.emp_code)
    punched = ms_to_dt(body.punched_at) if body.punched_at is not None else trunc_seconds(datetime.now(UTC))
    shift_start, shift_end = emp.get("shift_start", "09:30"), emp.get("shift_end", "18:30")
    date_str = attendance_date(punched, shift_start, shift_end)
    doc = {
        "emp_code": body.emp_code,
        "date": date_str,
        "status": body.status,
        "punch_in": punched,
        "punch_out": None,
        **derive_fields(body.status, punched, None, date_str, shift_start, shift_end),
        "history": [],
    }
    try:
        # Single atomic insert; the unique (emp_code, date) index lets exactly one concurrent request win.
        attendance_col().insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail=f"{body.emp_code} already has a record for {date_str}")
    return serialize_attendance(doc)


@app.post("/attendance/punch-out", tags=["attendance"])
def punch_out(body: PunchOutRequest):
    emp = get_employee_or_404(body.emp_code)
    punched = ms_to_dt(body.punched_at) if body.punched_at is not None else trunc_seconds(datetime.now(UTC))
    # most recent record whose punch_in is at or before punched_at (works across midnight for overnight shifts)
    rec = attendance_col().find_one({"emp_code": body.emp_code, "punch_in": {"$lte": punched}},
                                    sort=[("punch_in", DESCENDING)])
    if rec is None:
        raise HTTPException(status_code=404, detail="No punch-in found for this employee")
    if rec.get("punch_out") is not None:
        raise HTTPException(status_code=409, detail="This record is already punched out")
    punched_in = trunc_seconds(rec["punch_in"])
    if punched <= punched_in:
        unprocessable(("body", "punched_at"), "punched_at must be after punch_in")
    if punched - punched_in > MAX_SHIFT_SPAN:
        unprocessable(("body", "punched_at"), "punch-out is more than 24 hours after punch-in")
    derived = derive_fields(rec["status"], punched_in, punched, rec["date"],
                            emp.get("shift_start", "09:30"), emp.get("shift_end", "18:30"))
    updated = attendance_col().find_one_and_update(
        {"_id": rec["_id"], "punch_out": None},  # matches null or missing: only the first of N racers succeeds
        {"$set": {"punch_out": punched, "work_hours": derived["work_hours"],
                  "overtime_minutes": derived["overtime_minutes"], "half_day": derived["half_day"]}},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise HTTPException(status_code=409, detail="This record is already punched out")
    return serialize_attendance(updated)


@app.get("/attendance", tags=["attendance"])
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[DateStr] = None,
    date_to: Optional[DateStr] = None,
    status: Optional[StatusLiteral] = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
):
    check_date_order(date_from, date_to)
    q = build_attendance_query(emp_code, date_from, date_to, status, page, page_size)
    cursor = (attendance_col().find(q["filter"], {"_id": 0})
              .sort([("date", DESCENDING), ("emp_code", ASCENDING)]).skip(q["skip"]).limit(q["limit"]))
    items = [serialize_attendance(d) for d in cursor]
    total = attendance_col().count_documents(q["filter"])
    return page_response(items, total, page, page_size)


def plan_regularization(rec: dict, emp: dict, body: RegularizeRequest):
    """Validate a correction against the stored record and compute the new values.
    Returns (new_values, changes) where changes holds {field: {"from": old, "to": new}} for real changes only."""
    shift_start, shift_end = emp.get("shift_start", "09:30"), emp.get("shift_end", "18:30")
    new_status = body.status or rec["status"]
    cur_in = trunc_seconds(rec["punch_in"]) if rec.get("punch_in") is not None else None
    cur_out = trunc_seconds(rec["punch_out"]) if rec.get("punch_out") is not None else None

    if new_status in NO_PUNCH_STATUSES:
        if body.punch_in is not None or body.punch_out is not None:
            unprocessable(("body", "status"), f"{new_status} clears the punch times; do not send punch_in/punch_out")
        final_in, final_out = None, None
    else:
        final_in = ms_to_dt(body.punch_in) if body.punch_in is not None else cur_in
        final_out = ms_to_dt(body.punch_out) if body.punch_out is not None else cur_out
        if final_in is None:
            unprocessable(("body", "punch_in"), f"status {new_status} requires a punch_in")
        if body.punch_in is not None and attendance_date(final_in, shift_start, shift_end) != rec["date"]:
            unprocessable(("body", "punch_in"), "punch_in must stay on the record's attendance date")
        if final_out is not None:
            if final_out <= final_in:
                unprocessable(("body", "punch_out"), "punch_out must be after punch_in")
            if final_out - final_in > MAX_SHIFT_SPAN:
                unprocessable(("body", "punch_out"), "punch_out must be within 24 hours of punch_in")

    derived = derive_fields(new_status, final_in, final_out, rec["date"], shift_start, shift_end)
    new_values = {"status": new_status, "punch_in": final_in, "punch_out": final_out, **derived}
    old_values = {
        "status": rec["status"],
        "punch_in": cur_in,
        "punch_out": cur_out,
        "work_hours": float(rec["work_hours"]) if rec.get("work_hours") is not None else None,
        "late_minutes": int(rec.get("late_minutes") or 0),
        "overtime_minutes": int(rec.get("overtime_minutes") or 0),
        "half_day": bool(rec.get("half_day") or False),
    }
    changes = {k: {"from": old_values[k], "to": new_values[k]} for k in new_values if old_values[k] != new_values[k]}
    if not changes:
        unprocessable(("body",), "the request changes nothing")
    return changes


@app.patch("/attendance/{emp_code}/{date}", tags=["attendance"])
def regularize_attendance(emp_code: str, body: RegularizeRequest, date: Annotated[DateStr, Path()]):
    emp = get_employee_or_404(emp_code)
    for attempt in range(PATCH_MAX_ATTEMPTS):
        rec = attendance_col().find_one({"emp_code": emp_code, "date": date})
        if rec is None:
            raise HTTPException(status_code=404, detail=f"No attendance record for {emp_code} on {date}")
        changes = plan_regularization(rec, emp, body)
        entry = {"at": trunc_millis(datetime.now(UTC)), "by": body.regularized_by, "reason": body.reason,
                 "changes": changes}
        sets = {field: change["to"] for field, change in changes.items()}
        # Optimistic concurrency: the write only applies if the fields we read and the history length are unchanged.
        guard = {"_id": rec["_id"], "status": rec["status"],
                 "punch_in": rec.get("punch_in"), "punch_out": rec.get("punch_out")}
        history = rec.get("history")
        if isinstance(history, list):
            guard["history"] = {"$size": len(history)}
            update = {"$set": sets, "$push": {"history": entry}}
        else:  # legacy record: history missing (or null) is an empty list
            guard["history"] = None
            update = {"$set": {**sets, "history": [entry]}}
        updated = attendance_col().find_one_and_update(guard, update, return_document=ReturnDocument.AFTER)
        if updated is not None:
            return serialize_attendance(updated)
        time.sleep(random.uniform(0.005, 0.03) * (attempt + 1))  # lost the race: back off, re-read, re-plan
    raise HTTPException(status_code=409, detail="The record is being modified concurrently; retry")


# ---------------------------------------------------------------------------------------- analytics
@app.get("/analytics/employees/{emp_code}/monthly", tags=["analytics"])
def employee_monthly(emp_code: str, month: MonthStr):
    emp = get_employee_or_404(emp_code)
    rows = list(attendance_col().aggregate(build_employee_monthly_pipeline(emp_code, month),
                                           maxTimeMS=AGGREGATE_MAX_TIME_MS))
    agg = rows[0] if rows else {}
    present = float(agg.get("present_days", 0))
    working_days = count_working_days(month, emp.get("joined_on", "0001-01-01"))
    return {
        "emp_code": emp_code,
        "month": month,
        "working_days": working_days,
        "present_days": present,
        "leave_days": int(agg.get("leave_days", 0)),
        "late_count": int(agg.get("late_count", 0)),
        "total_late_minutes": int(agg.get("total_late_minutes", 0)),
        "total_overtime_minutes": int(agg.get("total_overtime_minutes", 0)),
        "attendance_pct": attendance_pct(present, working_days),
    }


@app.get("/analytics/departments/summary", tags=["analytics"])
def department_summary(month: MonthStr, department: Optional[str] = None):
    rows = employees_col().aggregate(build_department_summary_pipeline(month, department),
                                     maxTimeMS=AGGREGATE_MAX_TIME_MS, allowDiskUse=True)
    items = [{
        "department": r["department"],
        "headcount": int(r["headcount"]),
        "present_days": float(r["present_days"]),
        "avg_work_hours": r.get("avg_work_hours"),
        "late_count": int(r["late_count"]),
        "total_late_minutes": int(r["total_late_minutes"]),
        "leave_count": int(r["leave_count"]),
        "on_duty_count": int(r["on_duty_count"]),
    } for r in rows]
    return {"month": month, "items": items}


@app.get("/analytics/leaderboard/late", tags=["analytics"])
def late_leaderboard(month: MonthStr, limit: Annotated[int, Query(ge=1, le=50)] = 10,
                     department: Optional[str] = None):
    rows = attendance_col().aggregate(build_late_leaderboard_pipeline(month, limit, department),
                                      maxTimeMS=AGGREGATE_MAX_TIME_MS, allowDiskUse=True)
    items = [{
        "rank": int(r["rank"]),
        "emp_code": r["emp_code"],
        "name": r.get("name"),
        "department": r.get("department"),
        "total_late_minutes": int(r["total_late_minutes"]),
        "late_count": int(r["late_count"]),
    } for r in rows]
    return {"month": month, "items": items}


@app.get("/analytics/departments/{department}/trend", tags=["analytics"])
def department_trend(department: str,
                     date_from: Annotated[DateStr, Query(alias="from")],
                     date_to: Annotated[DateStr, Query(alias="to")]):
    check_trend_range(date_from, date_to)
    if employees_col().find_one({"department": department}, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail=f"Department {department} not found")
    rows = employees_col().aggregate(build_department_trend_pipeline(department, date_from, date_to),
                                     maxTimeMS=AGGREGATE_MAX_TIME_MS, allowDiskUse=True)
    items = [{
        "date": r["date"],
        "is_working_day": bool(r["is_working_day"]),
        "headcount": int(r["headcount"]),
        "present_count": float(r["present_count"]),
        "late_count": int(r["late_count"]),
        "attendance_rate": r.get("attendance_rate"),
        "moving_avg_7d": r.get("moving_avg_7d"),
    } for r in rows]
    return {"department": department, "items": items}


# ---------------------------------------------------------------------------------------- admin / explain
ExplainTarget = Literal["attendance_list", "employee_monthly", "department_summary", "late_leaderboard",
                        "department_trend"]


def _require(value: Any, name: str):
    if value is None:
        unprocessable(("query", name), f"{name} is required for this endpoint")
    return value


@app.get("/admin/explain/{endpoint}", tags=["admin"])
def explain_endpoint(
    endpoint: ExplainTarget,
    emp_code: Optional[str] = None,
    month: Optional[MonthStr] = None,
    department: Optional[str] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    date_from: Optional[DateStr] = None,
    date_to: Optional[DateStr] = None,
    status: Optional[StatusLiteral] = None,
    from_: Annotated[Optional[DateStr], Query(alias="from")] = None,
    to: Optional[DateStr] = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
):
    """Runs explain('executionStats') on the very query/pipeline the real endpoint builds."""
    if endpoint == "attendance_list":
        check_date_order(date_from, date_to)
        q = build_attendance_query(emp_code, date_from, date_to, status, page, page_size)
        collection = "attendance_logs"
        command = {"find": collection, "filter": q["filter"], "sort": q["sort"], "skip": q["skip"],
                   "limit": q["limit"]}
    elif endpoint == "employee_monthly":
        pipeline = build_employee_monthly_pipeline(_require(emp_code, "emp_code"), _require(month, "month"))
        collection = "attendance_logs"
        command = {"aggregate": collection, "pipeline": pipeline, "cursor": {}}
    elif endpoint == "department_summary":
        pipeline = build_department_summary_pipeline(_require(month, "month"), department)
        collection = "employees"
        command = {"aggregate": collection, "pipeline": pipeline, "cursor": {}}
    elif endpoint == "late_leaderboard":
        pipeline = build_late_leaderboard_pipeline(_require(month, "month"), limit, department)
        collection = "attendance_logs"
        command = {"aggregate": collection, "pipeline": pipeline, "cursor": {}}
    else:  # department_trend
        dept = _require(department, "department")
        d_from, d_to = _require(from_, "from"), _require(to, "to")
        check_trend_range(d_from, d_to)
        pipeline = build_department_trend_pipeline(dept, d_from, d_to)
        collection = "employees"
        command = {"aggregate": collection, "pipeline": pipeline, "cursor": {}}

    raw = get_db().command({"explain": command, "verbosity": "executionStats"})
    explain = json.loads(json_util.dumps(raw, json_options=json_util.RELAXED_JSON_OPTIONS))
    return {"endpoint": endpoint, "collection": collection, "explain": explain}
