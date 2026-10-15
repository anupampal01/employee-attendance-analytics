"""Analytics tests: hand-built edge cases with known answers, plus randomised comparison against oracle.py."""
import random
from datetime import date, timedelta

import pytest

import oracle
from helpers import insert_employee, insert_log, strip

pytestmark = pytest.mark.integration

M = "2026-07"           # July 2026: starts on a Wednesday, 23 weekdays, 8 weekend days (4,5,11,12,18,19,25,26)


def approx_equal(a, b):
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(approx_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(approx_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) < 1e-9
    return a == b


def dump(db):
    return [strip(e) for e in db.employees.find()], [strip(l) for l in db.attendance_logs.find()]


# ------------------------------------------------------------------ employee monthly
def test_monthly_edge_cases(api, db):
    insert_employee(db, "EMP0001")
    # weekdays: PRESENT x2, one half day, WFH, ON_DUTY, LEAVE, ABSENT; plus a Saturday and Sunday record
    insert_log(db, "EMP0001", "2026-07-01", late=15, overtime=40)                       # Wed present, late
    insert_log(db, "EMP0001", "2026-07-02")                                              # Thu present
    insert_log(db, "EMP0001", "2026-07-03", half_day=True, work_hours=3.5)               # Fri half day = 0.5
    insert_log(db, "EMP0001", "2026-07-06", status="WFH")                                # Mon
    insert_log(db, "EMP0001", "2026-07-07", status="ON_DUTY", late=11)                   # Tue
    insert_log(db, "EMP0001", "2026-07-08", status="LEAVE")
    insert_log(db, "EMP0001", "2026-07-09", status="ABSENT")
    insert_log(db, "EMP0001", "2026-07-04", late=20, overtime=60)                        # Saturday: no present_days
    insert_log(db, "EMP0001", "2026-07-05", status="WFH", late=5)                        # Sunday
    insert_log(db, "EMP0001", "2026-06-30", late=99)                                     # other month: ignored
    insert_log(db, "EMP0001", "2026-08-01", late=99)
    r = api.get("/analytics/employees/EMP0001/monthly", params={"month": M})
    assert r.status_code == 200
    assert r.json() == {"emp_code": "EMP0001", "month": M, "working_days": 23, "present_days": 4.5, "leave_days": 1,
                        "late_count": 4, "total_late_minutes": 51, "total_overtime_minutes": 100,
                        "attendance_pct": 19.57}        # (1 + 1 + 0.5 + 1 + 1) / 23 * 100 = 19.565..


def test_monthly_mid_month_joiner_and_no_logs(api, db):
    insert_employee(db, "EMP0002", joined_on="2026-07-15")
    insert_employee(db, "EMP0003", joined_on="2026-08-10")
    insert_log(db, "EMP0002", "2026-07-15")
    r = api.get("/analytics/employees/EMP0002/monthly", params={"month": M}).json()
    assert r["working_days"] == 13 and r["present_days"] == 1 and r["attendance_pct"] == 7.69
    r = api.get("/analytics/employees/EMP0003/monthly", params={"month": M}).json()       # joins after the month
    assert r["working_days"] == 0 and r["attendance_pct"] is None and r["present_days"] == 0
    insert_employee(db, "EMP0004")
    r = api.get("/analytics/employees/EMP0004/monthly", params={"month": M}).json()        # no logs at all
    assert (r["working_days"], r["present_days"], r["attendance_pct"], r["late_count"]) == (23, 0, 0.0, 0)


def test_monthly_errors(api, db):
    insert_employee(db, "EMP0001")
    assert api.get("/analytics/employees/EMP9999/monthly", params={"month": M}).status_code == 404
    for bad in ("2026-13", "2026-7", "202607", "2026-00"):
        assert api.get("/analytics/employees/EMP0001/monthly", params={"month": bad}).status_code == 422
    assert api.get("/analytics/employees/EMP0001/monthly").status_code == 422


# ------------------------------------------------------------------ department summary
def test_department_summary_headcount_and_averages(api, db):
    insert_employee(db, "EMP0001", "Engineering")
    insert_employee(db, "EMP0002", "Engineering")                               # no logs at all: still counted
    insert_employee(db, "EMP0003", "Engineering", joined_on="2026-08-01")       # joins later: excluded
    insert_employee(db, "EMP0004", "Sales", joined_on="2026-07-31")             # joins on the last day: counted
    insert_employee(db, "EMP0005", "Ghost", joined_on="2026-09-01")             # headcount 0 -> department omitted
    insert_log(db, "EMP0001", "2026-07-01", work_hours=9.0, late=20)
    insert_log(db, "EMP0001", "2026-07-02", work_hours=8.0)
    insert_log(db, "EMP0001", "2026-07-03", status="WFH", work_hours=3.5, half_day=True)
    insert_log(db, "EMP0001", "2026-07-06", status="ON_DUTY")                    # no work_hours: excluded from average
    insert_log(db, "EMP0001", "2026-07-07", status="LEAVE")
    insert_log(db, "EMP0001", "2026-07-08", status="ABSENT", work_hours=9.0)     # absent: never in the average
    insert_log(db, "EMP0001", "2026-07-04", work_hours=1.0, late=5)              # Saturday: average yes, present_days no
    insert_log(db, "EMP0003", "2026-07-01", late=500)                            # not yet joined: employee not counted
    insert_log(db, "EMP0099", "2026-07-01", late=500)                            # orphan log
    r = api.get("/analytics/departments/summary", params={"month": M}).json()
    assert r["month"] == M
    assert [i["department"] for i in r["items"]] == ["Engineering", "Sales"]
    eng, sales = r["items"]
    # present: 07-01 1, 07-02 1, 07-03 0.5 (WFH half day), 07-06 1 (ON_DUTY) = 3.5 ; Saturday excluded
    # avg over records: (9 + 8 + 3.5 + 1) / 4 = 5.375 -> 5.38 (half-up)
    assert eng == {"department": "Engineering", "headcount": 2, "present_days": 3.5, "avg_work_hours": 5.38,
                   "late_count": 2, "total_late_minutes": 25, "leave_count": 1, "on_duty_count": 1}
    assert sales == {"department": "Sales", "headcount": 1, "present_days": 0, "avg_work_hours": None, "late_count": 0,
                     "total_late_minutes": 0, "leave_count": 0, "on_duty_count": 0}


def test_department_summary_filter_and_average_is_over_records(api, db):
    insert_employee(db, "EMP0001", "Engineering")
    insert_employee(db, "EMP0002", "Engineering")
    insert_employee(db, "EMP0003", "Sales")
    for day in ("2026-07-01", "2026-07-02", "2026-07-03"):
        insert_log(db, "EMP0001", day, work_hours=10.0)
    insert_log(db, "EMP0002", "2026-07-01", work_hours=4.0)
    r = api.get("/analytics/departments/summary", params={"month": M, "department": "Engineering"}).json()
    assert len(r["items"]) == 1
    assert r["items"][0]["avg_work_hours"] == 8.5      # (30 + 4) / 4 records, NOT (10 + 4) / 2 employees = 7.0
    assert api.get("/analytics/departments/summary", params={"month": M, "department": "Nope"}).json()["items"] == []
    assert api.get("/analytics/departments/summary").status_code == 422


# ------------------------------------------------------------------ leaderboard
def seed_leaderboard(db):
    for i, dept in enumerate(["Engineering", "Engineering", "Engineering", "Sales", "Engineering", "Sales"], start=1):
        insert_employee(db, f"EMP{i:04d}", dept)
    # totals: EMP1=50, EMP2=30, EMP3=30, EMP4=30, EMP5=10, EMP6=0 (zero late -> not listed)
    insert_log(db, "EMP0001", "2026-07-01", late=30)
    insert_log(db, "EMP0001", "2026-07-02", late=20)
    insert_log(db, "EMP0002", "2026-07-01", late=30)
    insert_log(db, "EMP0003", "2026-07-03", late=15)
    insert_log(db, "EMP0003", "2026-07-06", late=15)
    insert_log(db, "EMP0004", "2026-07-07", late=30)
    insert_log(db, "EMP0005", "2026-07-08", late=10)
    insert_log(db, "EMP0006", "2026-07-08", late=0)
    insert_log(db, "EMP0001", "2026-08-01", late=999)       # other month
    insert_log(db, "EMP0777", "2026-07-01", late=999)       # employee does not exist: ignored


def test_leaderboard_competition_ranking_and_tie_at_cutoff(api, db):
    seed_leaderboard(db)
    items = api.get("/analytics/leaderboard/late", params={"month": M, "limit": 10}).json()["items"]
    assert [(i["rank"], i["emp_code"], i["total_late_minutes"]) for i in items] == [
        (1, "EMP0001", 50), (2, "EMP0002", 30), (2, "EMP0003", 30), (2, "EMP0004", 30), (5, "EMP0005", 10)]
    assert items[0] == {"rank": 1, "emp_code": "EMP0001", "name": "Person EMP0001", "department": "Engineering",
                        "total_late_minutes": 50, "late_count": 2}
    assert items[2]["late_count"] == 2
    # limit applies AFTER ranking: limit=2 returns every employee whose rank <= 2, i.e. the whole 3-way tie
    two = api.get("/analytics/leaderboard/late", params={"month": M, "limit": 2}).json()["items"]
    assert [i["emp_code"] for i in two] == ["EMP0001", "EMP0002", "EMP0003", "EMP0004"]
    one = api.get("/analytics/leaderboard/late", params={"month": M, "limit": 1}).json()["items"]
    assert [i["emp_code"] for i in one] == ["EMP0001"]
    assert [i["rank"] for i in api.get("/analytics/leaderboard/late", params={"month": M, "limit": 5}).json()["items"]] \
        == [1, 2, 2, 2, 5]


def test_leaderboard_department_ranks_inside_department(api, db):
    seed_leaderboard(db)
    items = api.get("/analytics/leaderboard/late", params={"month": M, "department": "Sales"}).json()["items"]
    assert [(i["rank"], i["emp_code"]) for i in items] == [(1, "EMP0004")]
    eng = api.get("/analytics/leaderboard/late", params={"month": M, "department": "Engineering"}).json()["items"]
    assert [(i["rank"], i["emp_code"]) for i in eng] == [(1, "EMP0001"), (2, "EMP0002"), (2, "EMP0003"), (4, "EMP0005")]


def test_leaderboard_validation_and_default_limit(api, db):
    for bad in ({"limit": 0}, {"limit": 51}, {"limit": "x"}, {"month": "2026-13"}):
        params = {"month": M, **bad}
        assert api.get("/analytics/leaderboard/late", params=params).status_code == 422
    assert api.get("/analytics/leaderboard/late").status_code == 422
    for i in range(1, 16):                                                      # 15 distinct late totals
        insert_employee(db, f"EMP{i:04d}")
        insert_log(db, f"EMP{i:04d}", "2026-07-01", late=10 + i)
    assert len(api.get("/analytics/leaderboard/late", params={"month": M}).json()["items"]) == 10     # default limit
    assert len(api.get("/analytics/leaderboard/late", params={"month": M, "limit": 50}).json()["items"]) == 15


# ------------------------------------------------------------------ department trend
def test_trend_gap_filling_and_moving_average(api, db):
    insert_employee(db, "EMP0001", "Engineering", joined_on="2026-01-05")
    insert_employee(db, "EMP0002", "Engineering", joined_on="2026-07-08")       # joins mid-range
    insert_employee(db, "EMP0003", "Sales")
    insert_log(db, "EMP0001", "2026-07-06", late=15)
    insert_log(db, "EMP0001", "2026-07-07", half_day=True, work_hours=3.0)       # 0.5
    insert_log(db, "EMP0001", "2026-07-08")
    insert_log(db, "EMP0002", "2026-07-08", status="WFH")
    insert_log(db, "EMP0001", "2026-07-09", status="LEAVE")
    insert_log(db, "EMP0003", "2026-07-06")                                      # other department
    insert_log(db, "EMP0001", "2026-07-11")                                      # Saturday record
    r = api.get("/analytics/departments/Engineering/trend", params={"from": "2026-07-06", "to": "2026-07-14"})
    assert r.status_code == 200
    rows = r.json()["items"]
    assert [x["date"] for x in rows] == [f"2026-07-{d:02d}" for d in range(6, 15)]      # exactly one row per day
    by = {x["date"]: x for x in rows}
    assert by["2026-07-06"] == {"date": "2026-07-06", "is_working_day": True, "headcount": 1, "present_count": 1,
                                "late_count": 1, "attendance_rate": 1.0, "moving_avg_7d": 1.0}
    assert by["2026-07-07"]["present_count"] == 0.5 and by["2026-07-07"]["attendance_rate"] == 0.5
    assert by["2026-07-07"]["moving_avg_7d"] == 0.75                                    # (1.0 + 0.5) / 2
    assert by["2026-07-08"]["headcount"] == 2 and by["2026-07-08"]["present_count"] == 2
    assert by["2026-07-08"]["attendance_rate"] == 1.0
    assert by["2026-07-09"]["present_count"] == 0 and by["2026-07-09"]["attendance_rate"] == 0.0   # LEAVE: rate 0.0
    assert by["2026-07-10"]["attendance_rate"] == 0.0                                            # working day, no records
    sat, sun = by["2026-07-11"], by["2026-07-12"]
    assert sat["is_working_day"] is False and sat["attendance_rate"] is None and sat["present_count"] == 1
    assert sun["is_working_day"] is False and sun["present_count"] == 0 and sun["attendance_rate"] is None
    assert sat["moving_avg_7d"] == sun["moving_avg_7d"] == 0.5          # (1.0, .5, 1.0, 0, 0)/5 = 0.5: weekends add no rate
    assert by["2026-07-13"]["attendance_rate"] == 0.0


def test_trend_window_is_limited_to_requested_range(api, db):
    insert_employee(db, "EMP0001", "Engineering")
    for day in range(1, 8):
        insert_log(db, "EMP0001", f"2026-07-{day:02d}")
    # the range starts on a Saturday: first row has no rate, so its moving average is null
    rows = api.get("/analytics/departments/Engineering/trend", params={"from": "2026-07-04", "to": "2026-07-07"}).json()["items"]
    assert rows[0]["attendance_rate"] is None and rows[0]["moving_avg_7d"] is None
    assert rows[1]["is_working_day"] is False and rows[1]["moving_avg_7d"] is None
    assert rows[2]["moving_avg_7d"] == 1.0


def test_trend_errors_and_limits(api, db):
    insert_employee(db, "EMP0001", "Engineering")
    url = "/analytics/departments/Engineering/trend"
    assert api.get("/analytics/departments/Nope/trend", params={"from": "2026-07-01", "to": "2026-07-02"}).status_code == 404
    assert api.get(url, params={"from": "2026-07-05", "to": "2026-07-01"}).status_code == 422
    assert api.get(url, params={"from": "2026-07-01"}).status_code == 422
    assert api.get(url, params={"from": "2026-07-01", "to": "2026-02-30"}).status_code == 422
    ok = api.get(url, params={"from": "2026-07-01", "to": "2026-09-30"})                   # 92 days
    assert ok.status_code == 200 and len(ok.json()["items"]) == 92
    assert api.get(url, params={"from": "2026-07-01", "to": "2026-10-01"}).status_code == 422   # 93 days
    one = api.get(url, params={"from": "2026-07-01", "to": "2026-07-01"})
    assert one.status_code == 200 and len(one.json()["items"]) == 1


def test_trend_headcount_zero_gives_null_rate(api, db):
    insert_employee(db, "EMP0001", "Engineering", joined_on="2026-07-08")
    rows = api.get("/analytics/departments/Engineering/trend", params={"from": "2026-07-06", "to": "2026-07-09"}).json()["items"]
    assert [r["headcount"] for r in rows] == [0, 0, 1, 1]
    assert rows[0]["attendance_rate"] is None and rows[1]["attendance_rate"] is None
    assert rows[2]["attendance_rate"] == 0.0 and rows[2]["moving_avg_7d"] == 0.0


# ------------------------------------------------------------------ randomised comparison with the oracle
def build_random_dataset(db, seed):
    rnd = random.Random(seed)
    depts = ["Engineering", "Sales", "Ops"]
    start = date(2026, 6, 1)
    for i in range(1, 26):
        joined = rnd.choice(["2026-01-05", "2026-06-10", "2026-06-24", "2026-07-08", "2026-07-20", "2026-08-03"])
        insert_employee(db, f"EMP{i:04d}", rnd.choice(depts), joined_on=joined)
    for i in range(1, 26):
        for offset in range(0, 70):
            day = start + timedelta(days=offset)
            if rnd.random() < 0.18:
                continue                                         # missing record
            status = rnd.choices(["PRESENT", "WFH", "ON_DUTY", "ABSENT", "LEAVE"], [60, 12, 6, 12, 10])[0]
            if status in ("ABSENT", "LEAVE"):
                insert_log(db, f"EMP{i:04d}", day.isoformat(), status=status)
                continue
            late = rnd.choice([0, 0, 0, 11, 15, 30, 45, 90])
            closed = rnd.random() < 0.9
            hours = round(rnd.uniform(1, 11), 2) if closed else None
            insert_log(db, f"EMP{i:04d}", day.isoformat(), status=status, late=late,
                       overtime=rnd.choice([0, 0, 30, 45]) if closed else 0,
                       half_day=bool(closed and hours < 4.5), work_hours=hours)
    insert_log(db, "EMP0500", "2026-07-02", late=40)             # orphan log


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_randomised_analytics_match_oracle(api, db, seed):
    build_random_dataset(db, seed)
    employees, logs = dump(db)
    for month in ("2026-06", "2026-07", "2026-08"):
        got = api.get("/analytics/departments/summary", params={"month": month}).json()
        assert approx_equal(got, oracle.department_summary(employees, logs, month)), month
        got = api.get("/analytics/departments/summary", params={"month": month, "department": "Sales"}).json()
        assert approx_equal(got, oracle.department_summary(employees, logs, month, "Sales")), month
        for limit in (1, 3, 10, 50):
            for dept in (None, "Ops"):
                params = {"month": month, "limit": limit, **({"department": dept} if dept else {})}
                got = api.get("/analytics/leaderboard/late", params=params).json()
                assert approx_equal(got, oracle.leaderboard(employees, logs, month, limit, dept)), (month, limit, dept)
        for emp in employees[:8]:
            got = api.get(f"/analytics/employees/{emp['emp_code']}/monthly", params={"month": month}).json()
            assert approx_equal(got, oracle.monthly(emp, logs, month)), (emp["emp_code"], month)
    for dept in ("Engineering", "Sales", "Ops"):
        got = api.get(f"/analytics/departments/{dept}/trend", params={"from": "2026-06-01", "to": "2026-08-10"}).json()
        assert approx_equal(got, oracle.trend(employees, logs, dept, "2026-06-01", "2026-08-10")), dept
