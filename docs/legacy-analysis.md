# Legacy Tool Analysis: RO_Aging_Report

This review documents what the legacy Excel macro calculates, where its results differ from the intended business rules, and how each difference is handled in the replacement service. It was completed before any replacement code was written.

## Purpose

Service managers use the Aging sheet to see how many repair orders are open at each branch, how long they have been open, and how much labor and parts value is not yet invoiced.

## Current behavior

1. Opens an ADODB connection directly to the DMS reporting database and reads every repair order.
2. Treats a repair order as open unless its status is exactly `Closed`, `Invoiced` or `Void`.
3. Calculates age as the current date minus the open date, in days.
4. Assigns each open repair order to a bucket: 0-7, 8-15, 16-30, 31-60, 61-90, 90+.
5. Writes the count and the sum of labor and parts amounts for each branch and bucket.

## Findings

| # | Finding | Effect | Resolution |
|---|---|---|---|
| 1 | Connection string with credentials is stored in the workbook, and each user connects to the database directly | Database credentials are distributed with the file | Data is served through an authenticated API; no client connects to the database |
| 2 | Status comparison is exact and case sensitive | `Closed `, `closed` and `INVOICED` are reported as open | Status is trimmed and compared case insensitively |
| 3 | `On Error Resume Next` hides the conversion error on a blank open date | The record silently inherits the previous record's age and lands in an unrelated bucket | Record is excluded from aging and reported as a data exception |
| 4 | No de-duplication | A repair order exported twice is counted twice | One row per repair order number, latest load wins |

Findings 2 to 4 change reported figures and require sign-off from the service manager before cutover.

## Impact on the sample export (as of 2026-10-21)

| Measure | Legacy macro | Replacement | Difference |
|---|---:|---:|---:|
| Open repair orders | 75 | 70 | 5 |
| Open labor and parts | $221,133.92 | $207,447.95 | $13,685.97 |

Every difference is attributed to a specific finding by `tests/test_parity.py`, and the same reconciliation is available in the Data quality view and at `/api/v1/reconciliation`.

## Verification approach

`src/ro_aging/legacy.py` reproduces the macro's logic in Python, including the defects above. Each correction can be enabled independently.

- With all corrections enabled, the legacy logic and the new service must produce identical results for every branch and bucket, to the cent.
- With corrections disabled, the only repair orders allowed to differ are those attributed to findings 2 to 4. Any other difference fails the build.

## Open question for the business

Repair orders in `Waiting on Parts` and `Sublet Out` status are included in aging, matching the legacy behavior. Confirm whether these should remain in the main view or be reported separately.
