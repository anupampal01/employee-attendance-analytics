from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from helpers import employee_body, insert_employee, insert_log, ist_ms

pytestmark = pytest.mark.integration

DAY = "2026-07-07"


@pytest.fixture()
def closed(api):
    """EMP0001 punched in 10:05 and out 19:10 on DAY (late 35, overtime 40, work_hours 9.08)."""
    api.post("/employees", json=employee_body("EMP0001"))
    api.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": ist_ms(2026, 7, 7, 10, 5)})
    api.post("/attendance/punch-out", json={"emp_code": "EMP0001", "punched_at": ist_ms(2026, 7, 7, 19, 10)})
    return "EMP0001"


def patch(api, code, body, date=DAY):
    return api.patch(f"/attendance/{code}/{date}", json={"reason": "biometric glitch", "regularized_by": "hr.admin", **body})


def test_regularize_punch_in_recomputes_and_appends_one_history_entry(api, closed):
    r = patch(api, closed, {"punch_in": ist_ms(2026, 7, 7, 9, 28)})
    assert r.status_code == 200
    b = r.json()
    assert (b["late_minutes"], b["work_hours"], b["overtime_minutes"], b["half_day"]) == (0, 9.7, 40, False)
    assert len(b["history"]) == 1
    h = b["history"][0]
    assert h["by"] == "hr.admin" and h["reason"] == "biometric glitch" and isinstance(h["at"], int)
    assert h["changes"] == {
        "punch_in": {"from": ist_ms(2026, 7, 7, 10, 5), "to": ist_ms(2026, 7, 7, 9, 28)},
        "late_minutes": {"from": 35, "to": 0},
        "work_hours": {"from": 9.08, "to": 9.7},
    }                                           # only fields that actually changed, instants as epoch ms


def test_punch_in_and_punch_out_do_not_write_history(api, closed):
    rec = api.get("/attendance", params={"emp_code": closed}).json()["items"][0]
    assert rec["history"] == []


def test_history_is_append_only_and_ordered(api, closed):
    first = patch(api, closed, {"punch_in": ist_ms(2026, 7, 7, 9, 28)}).json()["history"]
    second = patch(api, closed, {"punch_out": ist_ms(2026, 7, 7, 17, 0)}).json()["history"]
    assert len(second) == 2 and second[0] == first[0]
    assert set(second[1]["changes"]) == {"punch_out", "work_hours", "overtime_minutes"}


def test_status_to_absent_clears_times_and_derived(api, closed):
    b = patch(api, closed, {"status": "ABSENT"}).json()
    assert (b["status"], b["punch_in"], b["punch_out"], b["work_hours"], b["late_minutes"], b["overtime_minutes"],
            b["half_day"]) == ("ABSENT", None, None, None, 0, 0, False)
    assert set(b["history"][0]["changes"]) == {"status", "punch_in", "punch_out", "work_hours", "late_minutes",
                                               "overtime_minutes"}
    assert b["history"][0]["changes"]["punch_in"]["to"] is None


def test_absent_to_present_requires_punch_in(api, db):
    insert_employee(db, "EMP0004")
    insert_log(db, "EMP0004", DAY, status="ABSENT")
    assert patch(api, "EMP0004", {"status": "PRESENT"}).status_code == 422
    r = patch(api, "EMP0004", {"status": "WFH", "punch_in": ist_ms(2026, 7, 7, 9, 0)})
    assert r.status_code == 200 and r.json()["status"] == "WFH" and r.json()["punch_in"] == ist_ms(2026, 7, 7, 9, 0)


def test_leave_or_absent_with_punch_times_is_422(api, closed):
    assert patch(api, closed, {"status": "LEAVE", "punch_in": ist_ms(2026, 7, 7, 9, 0)}).status_code == 422
    assert patch(api, closed, {"status": "ABSENT", "punch_out": ist_ms(2026, 7, 7, 17, 0)}).status_code == 422


def test_rule_violations_are_422(api, closed):
    assert patch(api, closed, {"punch_in": ist_ms(2026, 7, 8, 9, 0)}).status_code == 422          # other attendance date
    assert patch(api, closed, {"punch_out": ist_ms(2026, 7, 7, 9, 0)}).status_code == 422          # before punch_in
    assert patch(api, closed, {"punch_out": ist_ms(2026, 7, 8, 10, 6)}).status_code == 422          # > 24 h
    assert patch(api, closed, {"punch_in": ist_ms(2026, 7, 7, 20, 0)}).status_code == 422          # after existing punch_out
    assert patch(api, closed, {}).status_code == 422                                              # changes nothing
    assert patch(api, closed, {"punch_in": ist_ms(2026, 7, 7, 10, 5)}).status_code == 422          # same value
    assert patch(api, closed, {"status": "PRESENT"}).status_code == 422                            # same status


@pytest.mark.parametrize("body", [{"reason": "abcd"}, {"reason": "x" * 201}, {"regularized_by": ""},
                                  {"regularized_by": "y" * 51}, {"punch_in": "1783312500000"},
                                  {"punch_in": 1783312500.0}, {"punch_in": 1783312500}, {"status": "SICK"},
                                  {"punch_in": None}, {"punch_out": None}, {"status": None}])
def test_invalid_patch_bodies_are_422(api, closed, body):
    base = {"reason": "valid reason", "regularized_by": "hr", "punch_out": ist_ms(2026, 7, 7, 18, 0)}
    assert api.patch(f"/attendance/{closed}/{DAY}", json={**base, **body}).status_code == 422


def test_missing_reason_or_actor_is_422(api, closed):
    assert api.patch(f"/attendance/{closed}/{DAY}", json={"regularized_by": "hr"}).status_code == 422
    assert api.patch(f"/attendance/{closed}/{DAY}", json={"reason": "valid reason"}).status_code == 422


def test_404s(api, closed):
    assert patch(api, "EMP9999", {"status": "LEAVE"}).status_code == 404
    assert patch(api, closed, {"status": "LEAVE"}, date="2026-07-20").status_code == 404
    assert patch(api, closed, {"status": "LEAVE"}, date="2026-02-30").status_code == 422        # malformed date


def test_derived_fields_in_body_are_ignored(api, closed):
    b = patch(api, closed, {"punch_in": ist_ms(2026, 7, 7, 9, 28), "late_minutes": 99, "work_hours": 1.0,
                            "half_day": True, "history": []}).json()
    assert b["late_minutes"] == 0 and b["work_hours"] == 9.7 and b["half_day"] is False and len(b["history"]) == 1


def test_half_day_after_correction(api, closed):
    b = patch(api, closed, {"punch_out": ist_ms(2026, 7, 7, 13, 0)}).json()       # 10:05 -> 13:00 = 2.92 h
    assert b["work_hours"] == 2.92 and b["half_day"] is True and b["overtime_minutes"] == 0


def test_legacy_record_without_history_gets_one_entry(api, db):
    insert_employee(db, "EMP0002")
    insert_log(db, "EMP0002", DAY, status="PRESENT", work_hours=None, legacy=True,
               punch_in=datetime(2026, 7, 7, 4, 35, tzinfo=timezone.utc))
    b = patch(api, "EMP0002", {"punch_in": ist_ms(2026, 7, 7, 9, 28)}).json()
    assert len(b["history"]) == 1 and b["late_minutes"] == 0


def test_concurrent_regularizations_never_lose_history(api, server, closed):
    import httpx
    # every request sets a different punch_out, so each one is a genuine change
    def go(i):
        with httpx.Client(base_url=server["url"], timeout=60) as c:
            r = c.patch(f"/attendance/{closed}/{DAY}", json={
                "reason": f"concurrent edit {i}", "regularized_by": f"hr{i}",
                "punch_out": ist_ms(2026, 7, 7, 12, 0) + i * 60_000})
            return r.status_code

    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(go, range(8)))
    assert set(codes) <= {200, 409}
    final = api.get("/attendance", params={"emp_code": closed}).json()["items"][0]
    assert len(final["history"]) == codes.count(200) >= 1             # every success is recorded exactly once
    reasons = [h["reason"] for h in final["history"]]
    assert len(set(reasons)) == len(reasons)
    # the chain of from/to values is consistent (no entry was computed against a stale record)
    outs = [h["changes"]["punch_out"] for h in final["history"]]
    for earlier, later in zip(outs, outs[1:]):
        assert earlier["to"] == later["from"]
