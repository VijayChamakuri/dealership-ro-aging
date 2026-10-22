"""Data access for open repair order aging.

In production these queries map to the SQL Server objects in ``sql/``
(``vw_RepairOrders_Clean``, ``fn_OpenRepairOrders`` and ``usp_GetOpenROAging``).
For local development and tests, the same rules run on an in-memory SQLite
database loaded from a DMS repair order export.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

AGE_BUCKETS: tuple[str, ...] = ("0-7", "8-15", "16-30", "31-60", "61-90", "90+")
CLOSED_STATUSES = "('CLOSED', 'INVOICED', 'VOID')"

_SCHEMA = """
CREATE TABLE stg_RepairOrders (
    load_seq      INTEGER PRIMARY KEY AUTOINCREMENT,
    ro_number     TEXT NOT NULL,
    branch        TEXT NOT NULL,
    open_date     TEXT,
    status        TEXT,
    payer_type    TEXT,
    unit          TEXT,
    complaint     TEXT,
    technician    TEXT,
    labor_hours   REAL,
    labor_amount  REAL,
    parts_amount  REAL
);

CREATE VIEW vw_RepairOrders_Clean AS
WITH ranked AS (
    SELECT s.*,
           ROW_NUMBER() OVER (PARTITION BY ro_number ORDER BY load_seq DESC) AS rn
    FROM stg_RepairOrders AS s
)
SELECT ro_number,
       branch,
       NULLIF(TRIM(open_date), '')  AS open_date,
       UPPER(TRIM(status))          AS status,
       payer_type,
       unit,
       complaint,
       NULLIF(TRIM(technician), '') AS technician,
       labor_hours,
       COALESCE(labor_amount, 0)    AS labor_amount,
       COALESCE(parts_amount, 0)    AS parts_amount
FROM ranked
WHERE rn = 1;
"""

_BUCKET_CASE = """
    CASE
        WHEN age_days <= 7  THEN '0-7'
        WHEN age_days <= 15 THEN '8-15'
        WHEN age_days <= 30 THEN '16-30'
        WHEN age_days <= 60 THEN '31-60'
        WHEN age_days <= 90 THEN '61-90'
        ELSE '90+'
    END
"""

_OPEN_REPAIR_ORDERS = f"""
    SELECT c.*,
           CAST(julianday(:as_of) - julianday(c.open_date) AS INTEGER) AS age_days
    FROM vw_RepairOrders_Clean AS c
    WHERE c.status NOT IN {CLOSED_STATUSES}
      AND c.open_date IS NOT NULL
      AND (:branch IS NULL OR c.branch = :branch)
"""

_INSERT = """
    INSERT INTO stg_RepairOrders (
        ro_number, branch, open_date, status, payer_type, unit, complaint,
        technician, labor_hours, labor_amount, parts_amount
    ) VALUES (
        :ro_number, :branch, :open_date, :status, :payer_type, :unit, :complaint,
        :technician, :labor_hours, :labor_amount, :parts_amount
    )
"""


class RepairOrderRepository:
    """Read-only queries over a loaded repair order export."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._con = connection

    @classmethod
    def from_export(cls, path: Path) -> RepairOrderRepository:
        """Create an in-memory database and load a DMS CSV export into staging."""
        con = sqlite3.connect(":memory:", check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.executescript(_SCHEMA)
        with path.open(newline="", encoding="utf-8") as handle:
            con.executemany(_INSERT, csv.DictReader(handle))
        con.commit()
        return cls(con)

    def branches(self) -> list[str]:
        rows = self._con.execute(
            "SELECT DISTINCT branch FROM vw_RepairOrders_Clean ORDER BY branch"
        )
        return [row[0] for row in rows]

    def aging_summary(self, as_of: str, branch: str | None = None) -> list[dict]:
        """Open repair order count and dollars per branch and age bucket."""
        sql = f"""
            SELECT branch,
                   {_BUCKET_CASE} AS age_bucket,
                   COUNT(*) AS ro_count,
                   ROUND(SUM(labor_amount + parts_amount), 2) AS open_dollars
            FROM ({_OPEN_REPAIR_ORDERS})
            GROUP BY branch, age_bucket
            ORDER BY branch, MIN(age_days)
        """
        return self._fetch(sql, as_of=as_of, branch=branch)

    def open_repair_orders(
        self, as_of: str, branch: str | None = None, bucket: str | None = None
    ) -> list[dict]:
        """Individual open repair orders, oldest first."""
        sql = f"""
            SELECT ro_number, branch, open_date, age_days,
                   {_BUCKET_CASE} AS age_bucket,
                   status, payer_type, unit, complaint, technician,
                   ROUND(labor_amount + parts_amount, 2) AS open_dollars
            FROM ({_OPEN_REPAIR_ORDERS})
            WHERE (:bucket IS NULL OR {_BUCKET_CASE} = :bucket)
            ORDER BY age_days DESC, ro_number
        """
        return self._fetch(sql, as_of=as_of, branch=branch, bucket=bucket)

    def breakdown(self, as_of: str, branch: str | None = None) -> dict[str, list[dict]]:
        """Open repair orders grouped by status, payer type and technician."""

        def group(column: str, label: str) -> list[dict]:
            sql = f"""
                SELECT COALESCE({column}, '{label}') AS name,
                       COUNT(*) AS ro_count,
                       ROUND(SUM(labor_amount + parts_amount), 2) AS open_dollars,
                       MAX(age_days) AS oldest_days
                FROM ({_OPEN_REPAIR_ORDERS})
                GROUP BY name
                ORDER BY ro_count DESC, name
            """
            return self._fetch(sql, as_of=as_of, branch=branch)

        return {
            "status": group("status", "UNKNOWN"),
            "payer_type": group("payer_type", "Unknown"),
            "technician": group("technician", "Unassigned"),
        }

    def data_exceptions(self) -> list[dict]:
        """Records that cannot be reported correctly until fixed in the DMS."""
        sql = f"""
            SELECT ro_number, branch, status, 'Missing or invalid open date' AS issue
            FROM vw_RepairOrders_Clean
            WHERE open_date IS NULL AND status NOT IN {CLOSED_STATUSES}
            UNION ALL
            SELECT ro_number, MIN(branch), MIN(status), 'Duplicate export row (counted once)'
            FROM stg_RepairOrders
            GROUP BY ro_number
            HAVING COUNT(*) > 1
            ORDER BY ro_number
        """
        return self._fetch(sql)

    def _fetch(self, sql: str, **params: object) -> list[dict]:
        return [dict(row) for row in self._con.execute(sql, params)]
