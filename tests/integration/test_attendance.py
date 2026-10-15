from concurrent.futures import ThreadPoolExecutor

import pytest

from helpers import employee_body, insert_employee, insert_log, ist_ms

pytestmark = pytest.mark.integration


@pytest.fixture()
def emp(api):
    assert api.post("/employees", json=employee_body("EMP0001")).status_code == 201
    return "EMP0001"


def punch_in(api, code, ms=None, **kw):
    body = {"emp_code": code, **kw}
    if ms is not None:
        body["punched_at"] = ms
    return api.post("/attendance/punch-in", json=body)


# ------------------------------------------------------------------ punch-in
def test_punch_in_creates_record_with_contract_defaults(api, emp):
    r = punch_in(api, emp, ist_ms(2026, 7, 6, 9, 28))
    assert r.status_code == 201
    b = r.json()
    assert b == {"emp_code": "EMP0001", "date": "2026-07-06", "status": "PRESENT", "punch_in": ist_ms(2026, 7, 6, 9, 28),
                 "punch_out": None, "work_hours": None, "late_minutes": 0, "overtime_minutes": 0, "half_day": False,
                 "history": []}


@pytest.mark.parametrize("h,mi,s,expected", [(9, 40, 0, 0), (9, 40, 1, 10), (10, 15, 59, 45), (10, 5, 0, 35), (9, 0, 0, 0)])
def test_late_boundaries(api, emp, h, mi, s, expected):
    r = punch_in(api, emp, ist_ms(2026, 7, 6, h, mi, s))
    assert r.json()["late_minutes"] == expected


def test_milliseconds_are_truncated_and_stored_truncated(api, emp):
    r = punch_in(api, emp, ist_ms(2026, 7, 6, 9, 40, 0, ms=900))
    assert r.json()["late_minutes"] == 0
    assert r.json()["punch_in"] == ist_ms(2026, 7, 6, 9, 40, 0)


def test_status_wfh_and_on_duty_accepted(api, db):
    insert_employee(db, "EMP0002")
    insert_employee(db, "EMP0003")
    assert punch_in(api, "EMP0002", ist_ms(2026, 7, 6, 9, 0), status="WFH").json()["status"] == "WFH"
    assert punch_in(api, "EMP0003", ist_ms(2026, 7, 6, 9, 0), status="ON_DUTY").json()["status"] == "ON_DUTY"


@pytest.mark.parametrize("bad", [{"status": "ABSENT"}, {"status": "LEAVE"}, {"status": "NOPE"}, {"status": 3},
                                 {"punched_at": "1783312500000"}, {"punched_at": 1783312500000.5},
                                 {"punched_at": 1783312500.0}, {"punched_at": 1783312500},     # seconds
                                 {"punched_at": 99_999_999_999}, {"punched_at": 4_102_444_800_001},
                                 {"punched_at": True}, {"punched_at": -5}, {"punched_at": 1783312500000.0},
                                 {"punched_at": None}, {"status": None}])
def test_invalid_punch_in_bodies_are_422(api, emp, bad):
    assert api.post("/attendance/punch-in", json={"emp_code": emp, **bad}).status_code == 422


def test_unknown_employee_is_404_and_missing_emp_code_422(api):
    assert punch_in(api, "EMP9999", ist_ms(2026, 7, 6, 9, 0)).status_code == 404
    assert api.post("/attendance/punch-in", json={}).status_code == 422


def test_duplicate_punch_in_same_date_is_409(api, emp):
    assert punch_in(api, emp, ist_ms(2026, 7, 6, 9, 0)).status_code == 201
    assert punch_in(api, emp, ist_ms(2026, 7, 6, 12, 0)).status_code == 409


def test_overnight_shift_date_and_ist_utc_boundary(api, db):
    insert_employee(db, "EMP0005", shift_start="22:00", shift_end="06:00")
    r = punch_in(api, "EMP0005", ist_ms(2026, 7, 7, 1, 0))      # 01:00 IST on the 7th -> shift of the 6th
    assert r.json()["date"] == "2026-07-06"
    insert_employee(db, "EMP0006")
    # 00:30 IST on 7 July is still 6 July in UTC; the record belongs to the IST date
    assert punch_in(api, "EMP0006", ist_ms(2026, 7, 7, 0, 30)).json()["date"] == "2026-07-07"


def test_concurrent_punch_ins_exactly_one_201(api, server, emp):
    import httpx
    ms = ist_ms(2026, 7, 6, 9, 30)

    def go(_):
        with httpx.Client(base_url=server["url"], timeout=60) as c:
            return c.post("/attendance/punch-in", json={"emp_code": emp, "punched_at": ms}).status_code

    with ThreadPoolExecutor(16) as pool:
        codes = list(pool.map(go, range(16)))
    assert codes.count(201) == 1 and codes.count(409) == 15


# ------------------------------------------------------------------ punch-out
def punch_out(api, code, ms=None):
    body = {"emp_code": code}
    if ms is not None:
        body["punched_at"] = ms
    return api.post("/attendance/punch-out", json=body)


def test_punch_out_computes_everything(api, emp):
    punch_in(api, emp, ist_ms(2026, 7, 6, 10, 5))
    r = punch_out(api, emp, ist_ms(2026, 7, 6, 19, 10))
    assert r.status_code == 200
    b = r.json()
    assert (b["work_hours"], b["late_minutes"], b["overtime_minutes"], b["half_day"]) == (9.08, 35, 40, False)
    assert b["punch_out"] == ist_ms(2026, 7, 6, 19, 10)


@pytest.mark.parametrize("h,mi,s,expected", [(18, 59, 59, 0), (19, 0, 0, 30), (19, 0, 59, 30), (18, 30, 0, 0), (17, 0, 0, 0)])
def test_overtime_boundaries(api, emp, h, mi, s, expected):
    punch_in(api, emp, ist_ms(2026, 7, 6, 9, 30))
    assert punch_out(api, emp, ist_ms(2026, 7, 6, h, mi, s)).json()["overtime_minutes"] == expected


@pytest.mark.parametrize("hours,minutes,seconds,expected_hours,half", [
    (3, 30, 0, 3.5, True), (4, 29, 30, 4.49, True), (4, 29, 59, 4.5, False), (4, 30, 0, 4.5, False), (8, 0, 18, 8.01, False)])
def test_work_hours_rounding_and_half_day_threshold(api, emp, hours, minutes, seconds, expected_hours, half):
    start = ist_ms(2026, 7, 6, 9, 0)
    punch_in(api, emp, start)
    r = punch_out(api, emp, start + ((hours * 60 + minutes) * 60 + seconds) * 1000)
    assert r.json()["work_hours"] == expected_hours and r.json()["half_day"] is half


def test_overnight_punch_out_across_midnight(api, db):
    insert_employee(db, "EMP0005", shift_start="22:00", shift_end="06:00")
    assert punch_in(api, "EMP0005", ist_ms(2026, 7, 6, 21, 55)).json()["late_minutes"] == 0
    b = punch_out(api, "EMP0005", ist_ms(2026, 7, 7, 6, 40)).json()
    assert (b["date"], b["work_hours"], b["overtime_minutes"]) == ("2026-07-06", 8.75, 40)


def test_punch_out_errors(api, emp):
    assert punch_out(api, "EMP9999", ist_ms(2026, 7, 6, 18, 0)).status_code == 404       # unknown employee
    assert punch_out(api, emp, ist_ms(2026, 7, 6, 18, 0)).status_code == 404              # no punch-in at all
    start = ist_ms(2026, 7, 6, 9, 30)
    punch_in(api, emp, start)
    assert punch_out(api, emp, start).status_code == 422                                  # not after punch-in
    assert punch_out(api, emp, start - 1000).status_code == 404                           # before any punch-in
    assert punch_out(api, emp, start + 24 * 3600 * 1000 + 1000).status_code == 422        # more than 24 h
    assert punch_out(api, emp, start + 9 * 3600 * 1000).status_code == 200
    assert punch_out(api, emp, start + 10 * 3600 * 1000).status_code == 409                # already punched out
    assert api.post("/attendance/punch-out", json={"emp_code": emp, "punched_at": "x"}).status_code == 422
    assert api.post("/attendance/punch-out", json={"emp_code": emp, "punched_at": None}).status_code == 422  # explicit null


def test_exactly_24_hours_is_allowed(api, emp):
    start = ist_ms(2026, 7, 6, 9, 30)
    punch_in(api, emp, start)
    assert punch_out(api, emp, start + 24 * 3600 * 1000).status_code == 200


def test_concurrent_punch_outs_exactly_one_200(api, server, emp):
    import httpx
    start = ist_ms(2026, 7, 6, 9, 30)
    punch_in(api, emp, start)

    def go(i):
        with httpx.Client(base_url=server["url"], timeout=60) as c:
            return c.post("/attendance/punch-out", json={"emp_code": emp, "punched_at": start + (8 * 3600 + i) * 1000}).status_code

    with ThreadPoolExecutor(12) as pool:
        codes = list(pool.map(go, range(12)))
    assert codes.count(200) == 1 and codes.count(409) == 11


# ------------------------------------------------------------------ listing
def test_attendance_list_filters_sort_total(api, db):
    for code in ("EMP0001", "EMP0002"):
        insert_employee(db, code)
    for day in ("2026-07-06", "2026-07-07", "2026-07-08"):
        insert_log(db, "EMP0001", day)
        insert_log(db, "EMP0002", day, status="WFH" if day == "2026-07-07" else "PRESENT")
    insert_log(db, "EMP0001", "2026-07-09", status="LEAVE")
    all_ = api.get("/attendance", params={"page_size": 100}).json()
    assert all_["total"] == 7
    keys = [(i["date"], i["emp_code"]) for i in all_["items"]]
    assert [k[0] for k in keys] == sorted((k[0] for k in keys), reverse=True)          # date descending
    day_items = [k for k in keys if k[0] == "2026-07-07"]
    assert day_items == [("2026-07-07", "EMP0001"), ("2026-07-07", "EMP0002")]          # emp_code ascending
    r = api.get("/attendance", params={"emp_code": "EMP0001", "date_from": "2026-07-07", "date_to": "2026-07-08"}).json()
    assert r["total"] == 2 and [i["date"] for i in r["items"]] == ["2026-07-08", "2026-07-07"]
    assert api.get("/attendance", params={"status": "WFH"}).json()["total"] == 1
    assert api.get("/attendance", params={"status": "LEAVE", "emp_code": "EMP0001"}).json()["total"] == 1
    p = api.get("/attendance", params={"page": 2, "page_size": 3}).json()
    assert p["total"] == 7 and len(p["items"]) == 3 and p["page"] == 2
    assert "_id" not in all_["items"][0]


def test_attendance_list_validation(api):
    assert api.get("/attendance", params={"date_from": "2026-07-09", "date_to": "2026-07-01"}).status_code == 422
    assert api.get("/attendance", params={"date_from": "2026-13-01"}).status_code == 422
    assert api.get("/attendance", params={"status": "SICK"}).status_code == 422
    assert api.get("/attendance", params={"page_size": 101}).status_code == 422


def test_legacy_records_default_missing_fields(api, db):
    insert_employee(db, "EMP0002")
    insert_log(db, "EMP0002", "2026-07-14", work_hours=8.98, legacy=True)
    rec = api.get("/attendance", params={"emp_code": "EMP0002"}).json()["items"][0]
    assert rec["history"] == [] and rec["half_day"] is False and rec["overtime_minutes"] == 0
