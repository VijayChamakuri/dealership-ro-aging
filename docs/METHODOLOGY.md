# Methodology

Rules the service uses, and the settings around them. The sample figures these rules produce are in [RESULTS.md](RESULTS.md). The report date for those figures, the tests, and the screenshots is 21 October 2026.

## Open repair order

A row is open when both of these hold:

- `UPPER(TRIM(status))` is not `CLOSED`, `INVOICED`, or `VOID`.
- The open date is present. A blank open date becomes null and the row is not aged.

Open dollars are `labor_amount + parts_amount`. Null amounts are treated as zero. The SQLite summary rounds that sum to the cent with `ROUND(..., 2)`. The Python port of the macro uses `Decimal` quantized to $0.01.

The page prints dollars with JavaScript `Math.round`, so each displayed amount is a whole dollar. Counts are not rounded.

## Age and buckets

Age is the number of days from the open date to the report date (`as_of`).

| Bucket | Age in days |
| --- | --- |
| 0-7 | 0 through 7 |
| 8-15 | 8 through 15 |
| 16-30 | 16 through 30 |
| 31-60 | 31 through 60 |
| 61-90 | 61 through 90 |
| 90+ | 91 or more |

The same bounds are in `age_bucket` in [`src/ro_aging/legacy.py`](../src/ro_aging/legacy.py), in `_BUCKET_CASE` in [`src/ro_aging/repository.py`](../src/ro_aging/repository.py), and in `fn_OpenRepairOrders` in [`sql/02_views.sql`](../sql/02_views.sql).

"Open over 30 days" on the page is `age_days > 30`. That is the 31-60, 61-90, and 90+ buckets together. It changes when the report date changes. The open count and the dollar total on this file do not: every open date is on or before 21 October 2026, so a later report date only moves orders between buckets.

SQLite computes age as `CAST(julianday(as_of) - julianday(open_date) AS INTEGER)`. The SQL Server function uses `DATEDIFF(DAY, open_date, @AsOf)`. The Python port uses `(as_of - open_date).days`.

## De-duplication and exceptions

The clean view keeps one row per RO number: `ROW_NUMBER() OVER (PARTITION BY ro_number ORDER BY load_seq DESC)` and `rn = 1`. The SQL Server view orders by `load_id` the same way. The macro port's de-duplication flag keeps the last copy of an RO number in file order.

The exceptions list has two kinds of rows:

- An open RO with a missing or invalid open date.
- An RO number that appears more than once in the staging load. The note says it was counted once.

A closed status that differed only by spaces or case is not an exception. After normalization it is closed, so it ages correctly. It still shows up in the reconciliation, because the macro counted it as open. The data-quality badge is the length of the exceptions list, not the size of the reconciliation gap.

## Statuses left in the open set

After normalization the open statuses in this file are `OPEN`, `IN PROGRESS`, `WAITING ON PARTS`, and `SUBLET OUT`. The page title-cases those labels. Waiting on Parts and Sublet Out stay in the aging totals, matching the macro. That choice is still open in [legacy-analysis.md](legacy-analysis.md).

## Reconciliation flags

`Corrections` in [`src/ro_aging/legacy.py`](../src/ro_aging/legacy.py) has three independent switches:

| Flag | Off (macro behavior) | On |
| --- | --- | --- |
| `normalize_status` | Status must equal `Closed`, `Invoiced`, or `Void` exactly | Trim, upper case, then compare to `CLOSED`, `INVOICED`, `VOID` |
| `exclude_blank_dates` | A blank open date keeps the previous row's age (`On Error Resume Next`) | The row is skipped |
| `deduplicate` | Every export row counts | One row per RO number, last copy in the file |

`Corrections.all()` turns all three on. The parity test expects that mode to match the service for every branch and bucket.

## API

The application programming interface (API) is read-only. Data routes require the header `X-API-Key`. The comparison is `secrets.compare_digest` against `RO_API_KEY`.

| Method | Path | Auth | Returns |
| --- | --- | --- | --- |
| GET | `/health` | No | `status` and `version` |
| GET | `/api/v1/branches` | Yes | Branch names |
| GET | `/api/v1/ro-aging` | Yes | Open count and dollars by branch and bucket |
| GET | `/api/v1/ro-aging/detail` | Yes | Open orders, oldest first |
| GET | `/api/v1/ro-aging/breakdown` | Yes | Groups by status, payer type, and technician |
| GET | `/api/v1/ro-aging/export.csv` | Yes | The detail rows as a CSV file |
| GET | `/api/v1/data-exceptions` | Yes | Blank open dates and duplicate RO numbers |
| GET | `/api/v1/reconciliation` | Yes | Macro totals, service totals, and labeled findings |

Query parameters:

| Parameter | Where | Behavior |
| --- | --- | --- |
| `branch` | Summary, detail, breakdown, export | Omit it for all branches. An unknown branch is 404. |
| `bucket` | Detail and export | One of `0-7`, `8-15`, `16-30`, `31-60`, `61-90`, `90+`. Anything else is 422. |
| `as_of` | Summary, detail, breakdown, export, reconciliation | A calendar date, written `2026-10-21`. The API defaults to the server's current date. A value that is not a date is 422. |

The page sends `as_of=2026-10-21` unless the date field is changed. OpenAPI (the generated schema) is at `/docs`.

CSV columns, in order: `ro_number`, `branch`, `open_date`, `age_days`, `age_bucket`, `status`, `payer_type`, `unit`, `complaint`, `technician`, `open_dollars`.

## Settings

Read from the environment in [`src/ro_aging/config.py`](../src/ro_aging/config.py). `make run` does not load a `.env` file. Docker Compose does.

| Variable | Default in code | Role |
| --- | --- | --- |
| `RO_API_KEY` | `local-dev-key` | Value of the `X-API-Key` header |
| `RO_EXPORT_PATH` | `data/sample/repair_orders.csv` | CSV loaded at startup |
| `RO_LOG_LEVEL` | `INFO` | Logging level |

## SQL Server scripts

Apply them in this order against the reporting database:

1. [`sql/01_staging.sql`](../sql/01_staging.sql) creates `stg_RepairOrders` and an index on `(ro_number, load_id)`.
2. [`sql/02_views.sql`](../sql/02_views.sql) creates `vw_RepairOrders_Clean`, `fn_OpenRepairOrders`, and `vw_RO_DataExceptions`.
3. [`sql/03_procedures.sql`](../sql/03_procedures.sql) creates `usp_GetOpenROAging` and `usp_GetOpenRODetail`.

```sql
EXEC dbo.usp_GetOpenROAging
    @Branch = 'Indianapolis',
    @AsOf = '2026-10-21';
```

Two expressions differ from the SQLite text, and this repo does not run the SQL Server scripts, so the tables in [RESULTS.md](RESULTS.md) are SQLite results only.

- SQL Server parses the open date with `TRY_CONVERT(DATE, ...)`. SQLite only turns a blank string into null.
- SQL Server ages with `DATEDIFF`. SQLite ages with `julianday`, as above.
