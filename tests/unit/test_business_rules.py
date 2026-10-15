"""Unit tests for the pure business-rule helpers (R1-R10). No MongoDB, no network, no third-party packages."""
import sys
import pathlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from pure_loader import load_pure  # noqa: E402

m = load_pure()
IST = timezone(timedelta(hours=5, minutes=30))


def ist(y, mo, d, h, mi, s=0, micro=0):
    """An IST wall-clock time as an aware datetime."""
    return datetime(y, mo, d, h, mi, s, micro, tzinfo=IST)


# ------------------------------------------------------------------ epoch milliseconds / R1 truncation
def test_ms_roundtrip_and_truncation():
    ms = 1783312500123  # has a 123 ms part
    dt = m.ms_to_dt(ms)
    assert dt.microsecond == 0                      # truncated to whole seconds
    assert m.dt_to_ms(dt) == 1783312500000
    assert dt.tzinfo is not None


def test_naive_datetime_treated_as_utc():
    naive = datetime(2026, 7, 6, 3, 58, 0)
    assert m.dt_to_ms(naive) == m.dt_to_ms(naive.replace(tzinfo=timezone.utc))


def test_truncate_milliseconds_before_calculation():
    # 09:40:00.900 counts as 09:40:00 -> not late
    assert m.calc_late_minutes(ist(2026, 7, 6, 9, 40, 0, 900_000), "2026-07-06", "09:30") == 0


# ------------------------------------------------------------------ R2 late
def test_late_boundaries_from_the_contract():
    for (h, mi, s), expected in [((9, 40, 0), 0), ((9, 40, 1), 10), ((10, 15, 59), 45), ((9, 30, 0), 0),
                                 ((9, 0, 0), 0), ((9, 50, 0), 20), ((9, 41, 0), 11)]:
        assert m.calc_late_minutes(ist(2026, 7, 6, h, mi, s), "2026-07-06", "09:30") == expected, (h, mi, s)


def test_late_is_measured_from_shift_start_not_grace_end():
    assert m.calc_late_minutes(ist(2026, 7, 6, 10, 5), "2026-07-06", "09:30") == 35


# ------------------------------------------------------------------ R3 overtime
def test_overtime_threshold():
    base = "2026-07-06"
    assert m.calc_overtime_minutes(ist(2026, 7, 6, 18, 59, 59), base, "09:30", "18:30") == 0     # 29:59
    assert m.calc_overtime_minutes(ist(2026, 7, 6, 19, 0, 0), base, "09:30", "18:30") == 30      # exactly 30
    assert m.calc_overtime_minutes(ist(2026, 7, 6, 19, 10, 0), base, "09:30", "18:30") == 40
    assert m.calc_overtime_minutes(ist(2026, 7, 6, 19, 0, 59), base, "09:30", "18:30") == 30     # floor
    assert m.calc_overtime_minutes(ist(2026, 7, 6, 17, 0, 0), base, "09:30", "18:30") == 0       # early leave


def test_overtime_overnight_uses_next_day_shift_end():
    # shift 22:00-06:00 started 2026-07-06; punch-out 06:40 on the 7th -> 40 min overtime (sample document 7)
    assert m.calc_overtime_minutes(ist(2026, 7, 7, 6, 40), "2026-07-06", "22:00", "06:00") == 40
    assert m.calc_overtime_minutes(ist(2026, 7, 7, 6, 29, 59), "2026-07-06", "22:00", "06:00") == 0


# ------------------------------------------------------------------ R4 / R5 work hours, half day
def test_work_hours_values_from_samples():
    assert m.calc_work_hours(ist(2026, 7, 6, 9, 28), ist(2026, 7, 6, 18, 35)) == Decimal("9.12")
    assert m.calc_work_hours(ist(2026, 7, 6, 10, 5), ist(2026, 7, 6, 19, 10)) == Decimal("9.08")
    assert m.calc_work_hours(ist(2026, 7, 6, 21, 55), ist(2026, 7, 7, 6, 40)) == Decimal("8.75")


def test_work_hours_half_up_not_bankers_not_float():
    a = ist(2026, 7, 6, 9, 0, 0)
    # 18 s = 0.005 h exactly -> half-up gives 0.01 (banker's rounding would give 0.00)
    assert m.calc_work_hours(a, a + timedelta(seconds=18)) == Decimal("0.01")
    # 54 s = 0.015 h -> 0.02 (banker's gives 0.02, float round gives 0.01 or 0.02 depending on repr)
    assert m.calc_work_hours(a, a + timedelta(seconds=54)) == Decimal("0.02")
    # 90 s = 0.025 h -> 0.03 (banker's would give 0.02)
    assert m.calc_work_hours(a, a + timedelta(seconds=90)) == Decimal("0.03")
    # 3 h 29 m 59 s = 3.49972.. -> 3.50 and 3 h 30 m = 3.50 exactly
    assert m.calc_work_hours(a, a + timedelta(hours=3, minutes=29, seconds=59)) == Decimal("3.50")


def test_half_day_threshold_uses_rounded_hours():
    a = ist(2026, 7, 6, 9, 0, 0)
    # 4 h 29 m 30 s = 4.49166.. -> rounded 4.49 -> half day
    assert m.calc_half_day(m.calc_work_hours(a, a + timedelta(hours=4, minutes=29, seconds=30))) is True
    # 4 h 29 m 59 s = 4.49972.. -> rounds to 4.50 -> NOT a half day (the rounded value is judged)
    assert m.calc_half_day(m.calc_work_hours(a, a + timedelta(hours=4, minutes=29, seconds=59))) is False
    assert m.calc_half_day(m.calc_work_hours(a, a + timedelta(hours=4, minutes=30))) is False
    assert m.calc_half_day(m.calc_work_hours(a, a + timedelta(hours=3, minutes=30))) is True  # sample document 4


# ------------------------------------------------------------------ R1 attendance date / overnight shifts
def test_attendance_date_day_shift_uses_ist_date_not_utc_date():
    # 00:30 IST on 7 July is 19:00 UTC on 6 July -> the IST date wins
    assert m.attendance_date(ist(2026, 7, 7, 0, 30), "09:30", "18:30") == "2026-07-07"
    # 23:59:59 IST on the 6th is 18:29:59 UTC on the 6th
    assert m.attendance_date(ist(2026, 7, 6, 23, 59, 59), "09:30", "18:30") == "2026-07-06"


def test_attendance_date_overnight_shift():
    s, e = "22:00", "06:00"
    assert m.attendance_date(ist(2026, 7, 6, 21, 55), s, e) == "2026-07-06"
    assert m.attendance_date(ist(2026, 7, 6, 22, 5), s, e) == "2026-07-06"
    assert m.attendance_date(ist(2026, 7, 7, 1, 0), s, e) == "2026-07-06"          # earlier than 06:00 -> previous day
    assert m.attendance_date(ist(2026, 7, 7, 5, 59, 59), s, e) == "2026-07-06"
    assert m.attendance_date(ist(2026, 7, 7, 6, 0, 0), s, e) == "2026-07-07"       # not earlier than shift_end
    assert m.attendance_date(ist(2026, 7, 7, 12, 0), s, e) == "2026-07-07"


def test_is_overnight():
    assert m.is_overnight("22:00", "06:00")
    assert m.is_overnight("09:00", "09:00") is True      # shift_end <= shift_start
    assert not m.is_overnight("09:30", "18:30")


def test_overnight_late_minutes_use_previous_day_shift_start():
    # punch-in 22:20 IST for a 22:00 shift -> 20 min late
    d = m.attendance_date(ist(2026, 7, 6, 22, 20), "22:00", "06:00")
    assert m.calc_late_minutes(ist(2026, 7, 6, 22, 20), d, "22:00") == 20


# ------------------------------------------------------------------ derive_fields (what gets stored)
def test_derive_open_record_and_absent_leave():
    pin = ist(2026, 7, 6, 10, 5)
    d = m.derive_fields("PRESENT", pin, None, "2026-07-06", "09:30", "18:30")
    assert d == {"work_hours": None, "late_minutes": 35, "overtime_minutes": 0, "half_day": False}
    for status in ("ABSENT", "LEAVE"):
        assert m.derive_fields(status, None, None, "2026-07-06", "09:30", "18:30") == {
            "work_hours": None, "late_minutes": 0, "overtime_minutes": 0, "half_day": False}


def test_derive_closed_record_matches_sample_document_2():
    d = m.derive_fields("PRESENT", ist(2026, 7, 6, 10, 5), ist(2026, 7, 6, 19, 10), "2026-07-06", "09:30", "18:30")
    assert d == {"work_hours": 9.08, "late_minutes": 35, "overtime_minutes": 40, "half_day": False}


# ------------------------------------------------------------------ R7 working days, R8 rounding
def test_working_days_full_month_and_mid_month_joiner():
    assert m.count_working_days("2026-07", "2026-01-05") == 23          # July 2026: 23 weekdays
    assert m.count_working_days("2026-07", "2026-07-15") == 13          # Wed 15th .. Fri 31st
    assert m.count_working_days("2026-07", "2026-07-04") == 20          # joined on a Saturday: 6th..31st
    assert m.count_working_days("2026-07", "2026-07-31") == 1
    assert m.count_working_days("2026-07", "2026-08-01") == 0          # joins after the month
    assert m.count_working_days("2026-02", "2020-01-01") == 20


def test_attendance_pct_rounding_and_null():
    assert m.attendance_pct(0, 0) is None
    assert m.attendance_pct(20, 23) == 86.96            # 86.9565...
    assert m.attendance_pct(1, 8) == 12.5
    assert m.attendance_pct(0.5, 16) == 3.13           # 3.125 exactly -> half-up 3.13 (banker's: 3.12)
    assert m.attendance_pct(23, 23) == 100.0


def test_round_half_up():
    assert m.round_half_up(1.005, 2) == Decimal("1.01")
    assert m.round_half_up(2.5, 0) == Decimal("3")
    assert m.round_half_up(0.12345, 4) == Decimal("0.1235")


# ------------------------------------------------------------------ validators and month helpers
def test_month_bounds():
    assert m.month_bounds("2026-07") == ("2026-07-01", "2026-07-31")
    assert m.month_bounds("2026-02") == ("2026-02-01", "2026-02-28")
    assert m.month_bounds("2028-02") == ("2028-02-01", "2028-02-29")


def test_date_and_month_validators():
    assert m.validate_date_str("2026-07-06") == "2026-07-06"
    for bad in ("2026-7-6", "2026-02-30", "20260706", "2026-13-01", "", "2026-07-06T00:00", "abcd-ef-gh"):
        try:
            m.validate_date_str(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted bad date {bad!r}")
    assert m.validate_month_str("2026-07") == "2026-07"
    for bad in ("2026-13", "2026-00", "2026-7", "26-07", "0000-01", "2026-07-01"):
        try:
            m.validate_month_str(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted bad month {bad!r}")


def test_days_in_range():
    assert m.days_in_range("2026-07-01", "2026-07-01") == 1
    assert m.days_in_range("2026-07-01", "2026-09-30") == 92       # allowed by the 92-day limit
    assert m.days_in_range("2026-07-01", "2026-10-01") == 93       # exceeds it


def test_status_constants():
    assert set(m.PRESENCE_STATUSES) == {"PRESENT", "WFH", "ON_DUTY"}
    assert set(m.NO_PUNCH_STATUSES) == {"ABSENT", "LEAVE"}
    assert m.EPOCH_MS_MIN == 100_000_000_000
