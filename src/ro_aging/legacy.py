"""Python reference implementation of legacy/RO_Aging_Report.bas.

Reproduces the macro's behavior, including the defects documented in
docs/legacy-analysis.md. Each correction can be enabled independently so the
reconciliation and parity tests can attribute every difference to a finding.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

LEGACY_CLOSED = ("Closed", "Invoiced", "Void")
NORMALIZED_CLOSED = ("CLOSED", "INVOICED", "VOID")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Corrections:
    normalize_status: bool = False
    exclude_blank_dates: bool = False
    deduplicate: bool = False

    @classmethod
    def all(cls) -> Corrections:
        return cls(True, True, True)


@dataclass(frozen=True)
class Contribution:
    ro_number: str
    branch: str
    age_bucket: str
    dollars: Decimal


@dataclass
class LegacyResult:
    contributions: list[Contribution] = field(default_factory=list)

    @property
    def summary(self) -> dict[tuple[str, str], tuple[int, Decimal]]:
        counts: dict[tuple[str, str], int] = defaultdict(int)
        dollars: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        for c in self.contributions:
            counts[(c.branch, c.age_bucket)] += 1
            dollars[(c.branch, c.age_bucket)] += c.dollars
        return {key: (counts[key], dollars[key].quantize(CENT)) for key in counts}

    @property
    def counted_ro_numbers(self) -> list[str]:
        return [c.ro_number for c in self.contributions]

    @property
    def total_count(self) -> int:
        return len(self.contributions)

    @property
    def total_dollars(self) -> Decimal:
        return sum((c.dollars for c in self.contributions), Decimal()).quantize(CENT)


def load_export(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def age_bucket(age_days: int) -> str:
    for limit, label in ((7, "0-7"), (15, "8-15"), (30, "16-30"), (60, "31-60"), (90, "61-90")):
        if age_days <= limit:
            return label
    return "90+"


def run_legacy(
    rows: list[dict[str, str]], as_of: date, corrections: Corrections | None = None
) -> LegacyResult:
    corrections = corrections or Corrections()
    if corrections.deduplicate:
        rows = list({row["ro_number"]: row for row in rows}.values())

    result = LegacyResult()
    age = 0  # VBA Long initializes to 0 and retains its value between iterations

    for row in rows:
        if corrections.normalize_status:
            is_closed = row["status"].strip().upper() in NORMALIZED_CLOSED
        else:
            is_closed = row["status"] in LEGACY_CLOSED
        if is_closed:
            continue

        if row["open_date"]:
            age = (as_of - date.fromisoformat(row["open_date"])).days
        elif corrections.exclude_blank_dates:
            continue
        # Otherwise On Error Resume Next leaves `age` at the previous record's value.

        result.contributions.append(
            Contribution(
                ro_number=row["ro_number"],
                branch=row["branch"],
                age_bucket=age_bucket(age),
                dollars=Decimal(row["labor_amount"]) + Decimal(row["parts_amount"]),
            )
        )
    return result
