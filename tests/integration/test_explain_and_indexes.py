import json

import pytest

from helpers import insert_employee, insert_log

pytestmark = pytest.mark.integration

CALLS = {
    "attendance_list": {"emp_code": "EMP0001", "date_from": "2026-07-01", "date_to": "2026-07-31", "page": 1, "page_size": 20},
    "employee_monthly": {"emp_code": "EMP0001", "month": "2026-07"},
    "department_summary": {"month": "2026-07"},
    "late_leaderboard": {"month": "2026-07", "limit": 5},
    "department_trend": {"department": "Engineering", "from": "2026-07-01", "to": "2026-07-31"},
}
COLLECTION = {"attendance_list": "attendance_logs", "employee_monthly": "attendance_logs",
              "department_summary": "employees", "late_leaderboard": "attendance_logs", "department_trend": "employees"}


@pytest.fixture()
def data(db):
    for i in range(1, 6):
        insert_employee(db, f"EMP{i:04d}")
        for day in range(1, 29):
            insert_log(db, f"EMP{i:04d}", f"2026-07-{day:02d}", late=day % 3 * 12)


@pytest.mark.parametrize("name", list(CALLS))
def test_explain_returns_raw_plan_with_index_scan_and_no_collscan(api, data, name):
    r = api.get(f"/admin/explain/{name}", params=CALLS[name])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["endpoint"] == name and body["collection"] == COLLECTION[name]
    text = json.dumps(body["explain"])
    assert "executionStats" in text, "explain must be run with executionStats verbosity"
    assert "IXSCAN" in text
    assert "COLLSCAN" not in text


def test_explain_attendance_list_with_status_and_no_filters(api, data):
    for params in ({}, {"status": "PRESENT"}, {"status": "WFH", "date_from": "2026-07-01"}):
        text = json.dumps(api.get("/admin/explain/attendance_list", params=params).json()["explain"])
        assert "IXSCAN" in text and "COLLSCAN" not in text, params


def test_explain_validation(api, data):
    assert api.get("/admin/explain/unknown_endpoint").status_code == 422
    assert api.get("/admin/explain/employee_monthly", params={"month": "2026-07"}).status_code == 422      # emp_code missing
    assert api.get("/admin/explain/employee_monthly", params={"emp_code": "EMP0001"}).status_code == 422   # month missing
    assert api.get("/admin/explain/department_summary").status_code == 422
    assert api.get("/admin/explain/late_leaderboard").status_code == 422
    assert api.get("/admin/explain/department_trend", params={"department": "Engineering"}).status_code == 422
    assert api.get("/admin/explain/attendance_list", params={"date_from": "2026-07-09", "date_to": "2026-07-01"}).status_code == 422


def test_indexes_created_at_startup_and_unique(db, api):
    names = {i["name"] for i in db.attendance_logs.list_indexes()}
    assert {"uq_emp_date", "ix_date_emp", "ix_status_date_emp", "ix_emp_punch_in"} <= names
    emp = {i["name"]: i for i in db.employees.list_indexes()}
    assert {"uq_emp_code", "ix_dept_emp_code", "ix_joined_on"} <= set(emp)
    assert emp["uq_emp_code"].get("unique") is True
    assert {i["name"]: i for i in db.attendance_logs.list_indexes()}["uq_emp_date"].get("unique") is True


def test_index_creation_is_idempotent(api):
    import app.main as main
    main.ensure_indexes()
    main.ensure_indexes()


def test_health_ok(api):
    r = api.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
