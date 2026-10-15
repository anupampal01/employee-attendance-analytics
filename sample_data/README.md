# sample_data

**Important:** the `sample_data/` folder of the original candidate kit did not come through intact when this project was
assembled (it arrived as an empty file). These two files were therefore **reconstructed from `DATA_MODEL.md`**, which
prints all nine sample attendance documents and the EMP0001 employee document verbatim.

* `attendance_logs.json` - the nine sample attendance documents exactly as printed in DATA_MODEL.md section 5.
* `employees.json` - EMP0001 verbatim. EMP0002-EMP0006 are referenced by the sample attendance documents but their
  employee documents were not printed anywhere, so they are **reconstructed placeholders**: names and departments are
  invented, EMP0005 has the 22:00-06:00 shift implied by sample 7, the others use the default 09:30-18:30 shift.

If you have the original kit's files, copy them over these. Load with `python sample_seed.py` (see README.md).
These samples only show shapes; they are not a test of the analytics. Synthetic data for edge cases and for the
100,000-record performance check comes from `scripts/generate_test_data.py` and lives only in the database.
