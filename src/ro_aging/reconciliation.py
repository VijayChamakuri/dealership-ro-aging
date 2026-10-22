"""Reconciliation of the replacement service against the legacy report."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from ro_aging.legacy import CENT, NORMALIZED_CLOSED, run_legacy
from ro_aging.repository import RepairOrderRepository

FINDINGS = {
    "status": (
        "Closed status not recognized",
        "Status differs from Closed, Invoiced or Void only by spacing or case",
    ),
    "open_date": (
        "Missing open date",
        "Record inherited the previous record's age instead of being flagged",
    ),
    "duplicate": (
        "Duplicate export row",
        "Repair order appears more than once in the export and was counted each time",
    ),
}


def _classify(ro_rows: list[dict[str, str]]) -> str | None:
    if len(ro_rows) > 1:
        return "duplicate"
    row = ro_rows[0]
    if not row["open_date"].strip():
        return "open_date"
    if row["status"].strip().upper() in NORMALIZED_CLOSED:
        return "status"
    return None


def reconcile(rows: list[dict[str, str]], repository: RepairOrderRepository, as_of: date) -> dict:
    """Compare legacy and service totals and attribute every difference."""
    legacy = run_legacy(rows, as_of)
    service = repository.open_repair_orders(as_of.isoformat())

    service_count = len(service)
    service_dollars = sum((Decimal(str(r["open_dollars"])) for r in service), Decimal())

    raw_by_ro: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        raw_by_ro[row["ro_number"]].append(row)

    excess = Counter(legacy.counted_ro_numbers) - Counter(r["ro_number"] for r in service)
    grouped: dict[str, dict] = {}
    unexplained: list[str] = []

    for contribution in legacy.contributions:
        if excess[contribution.ro_number] <= 0:
            continue
        excess[contribution.ro_number] -= 1
        key = _classify(raw_by_ro[contribution.ro_number])
        if key is None:
            unexplained.append(contribution.ro_number)
            continue
        title, description = FINDINGS[key]
        entry = grouped.setdefault(
            key,
            {
                "finding": title,
                "description": description,
                "ro_count": 0,
                "dollars": Decimal(),
                "ro_numbers": [],
            },
        )
        entry["ro_count"] += 1
        entry["dollars"] += contribution.dollars
        if contribution.ro_number not in entry["ro_numbers"]:
            entry["ro_numbers"].append(contribution.ro_number)

    findings = [
        {**entry, "dollars": float(entry["dollars"].quantize(CENT))}
        for key in FINDINGS
        if (entry := grouped.get(key))
    ]
    return {
        "as_of": as_of.isoformat(),
        "legacy": {"ro_count": legacy.total_count, "open_dollars": float(legacy.total_dollars)},
        "service": {
            "ro_count": service_count,
            "open_dollars": float(service_dollars.quantize(CENT)),
        },
        "difference": {
            "ro_count": legacy.total_count - service_count,
            "open_dollars": float((legacy.total_dollars - service_dollars).quantize(CENT)),
        },
        "findings": findings,
        "unexplained": unexplained,
    }
