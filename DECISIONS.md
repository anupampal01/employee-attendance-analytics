# DECISIONS.md

1. **Indexes.** `employees`: unique `emp_code`, `(department, emp_code)` for filtered sorted listing, `joined_on` for headcount. `attendance_logs`: unique `(emp_code, date)` (the one-record-per-day guarantee and monthly/lookup queries), `(date desc, emp_code)` for listing and month scans, `(status, date desc, emp_code)`, and `(emp_code, punch_in desc)` for punch-out. I rejected an index on `late_minutes`: the date range already narrows the leaderboard scan, and it would slow every write.

2. **Punch-in race.** Both requests derive the same `(emp_code, date)` and call `insert_one`. The unique index lets exactly one succeed; the other raises `DuplicateKeyError`, returned as 409. There is no read-then-write.

3. **Ties.** `$setWindowFields` with `$rank` gives 1, 2, 2, 4. The limit filters on rank after ranking, so everyone tied at the cutoff is returned, ordered by `emp_code`.

4. **Headcount.** The summary pipeline starts from `employees` (`joined_on` ≤ month end) and `$lookup`s logs, so people without logs have an empty array and are still counted.

5. **100x data.** Maintain per-employee monthly rollups, updated on punch and correction, instead of scanning logs per request.
