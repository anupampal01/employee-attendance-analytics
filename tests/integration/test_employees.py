from concurrent.futures import ThreadPoolExecutor

import pytest

from helpers import employee_body

pytestmark = pytest.mark.integration


def test_create_employee_shape_and_defaults(api):
    r = api.post("/employees", json=employee_body())
    assert r.status_code == 201
    body = r.json()
    assert "_id" not in body and "id" not in body
    assert body["shift_start"] == "09:30" and body["shift_end"] == "18:30"        # contract defaults
    assert isinstance(body["created_at"], int) and body["created_at"] > 10**12     # epoch milliseconds
    assert set(body) == {"emp_code", "name", "email", "department", "shift_start", "shift_end", "joined_on", "created_at"}


def test_client_supplied_created_at_is_ignored(api):
    r = api.post("/employees", json={**employee_body(), "created_at": 123})
    assert r.status_code == 201 and r.json()["created_at"] != 123


def test_duplicate_emp_code_is_409(api):
    assert api.post("/employees", json=employee_body()).status_code == 201
    r = api.post("/employees", json=employee_body(name="Someone Else"))
    assert r.status_code == 409 and "detail" in r.json()


def test_concurrent_duplicate_creates_yield_exactly_one_201(api, server):
    import httpx

    def create(_):
        with httpx.Client(base_url=server["url"], timeout=60) as c:
            return c.post("/employees", json=employee_body("EMP7777")).status_code

    with ThreadPoolExecutor(12) as pool:
        codes = list(pool.map(create, range(12)))
    assert codes.count(201) == 1 and codes.count(409) == 11


@pytest.mark.parametrize("patch", [
    {"emp_code": "EMP1"}, {"emp_code": "emp0001"}, {"emp_code": "EMP1234567"}, {"emp_code": "EMPABCD"},
    {"name": ""}, {"name": "x" * 101}, {"email": "not-an-email"}, {"email": "a@b"}, {"department": ""},
    {"department": "d" * 51}, {"shift_start": "9:30"}, {"shift_start": "24:00"}, {"shift_end": "18:60"},
    {"shift_start": "09:30", "shift_end": "09:30"}, {"joined_on": "2026-02-30"}, {"joined_on": "05-01-2026"},
    {"joined_on": 20260105}, {"name": 5},
])
def test_invalid_employee_bodies_are_422(api, patch):
    assert api.post("/employees", json={**employee_body(), **patch}).status_code == 422


def test_missing_required_fields_are_422(api):
    for field in ("emp_code", "name", "email", "department", "joined_on"):
        body = employee_body()
        body.pop(field)
        assert api.post("/employees", json=body).status_code == 422, field


def test_list_filters_paginates_and_totals(api):
    for i in range(1, 8):
        api.post("/employees", json=employee_body(f"EMP{i:04d}", "Engineering" if i % 2 else "Sales"))
    page = api.get("/employees", params={"page_size": 3}).json()
    assert page["total"] == 7 and page["page"] == 1 and page["page_size"] == 3
    assert [e["emp_code"] for e in page["items"]] == ["EMP0001", "EMP0002", "EMP0003"]
    page3 = api.get("/employees", params={"page": 3, "page_size": 3}).json()
    assert [e["emp_code"] for e in page3["items"]] == ["EMP0007"]
    eng = api.get("/employees", params={"department": "Engineering", "page_size": 2}).json()
    assert eng["total"] == 4 and [e["emp_code"] for e in eng["items"]] == ["EMP0001", "EMP0003"]
    assert api.get("/employees", params={"department": "engineering"}).json()["total"] == 0   # case-sensitive
    assert api.get("/employees", params={"page": 99}).json()["items"] == []


@pytest.mark.parametrize("params", [{"page": 0}, {"page": -1}, {"page_size": 0}, {"page_size": 101}, {"page": "x"}])
def test_pagination_validation_is_422(api, params):
    assert api.get("/employees", params=params).status_code == 422


def test_default_page_size_is_20_and_max_100_accepted(api, db):
    from helpers import insert_employee
    for i in range(1, 31):
        insert_employee(db, f"EMP{i:04d}")
    assert len(api.get("/employees").json()["items"]) == 20
    assert api.get("/employees", params={"page_size": 100}).json()["total"] == 30
