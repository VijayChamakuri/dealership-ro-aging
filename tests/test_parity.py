"""Parity between the legacy macro and the replacement service."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from ro_aging.config import settings
from ro_aging.legacy import Corrections, load_export, run_legacy


def service_summary(repository, as_of):
    return {
        (row["branch"], row["age_bucket"]): (
            row["ro_count"],
            Decimal(str(row["open_dollars"])).quantize(Decimal("0.01")),
        )
        for row in repository.aging_summary(as_of.isoformat())
    }


def test_matches_legacy_exactly_with_approved_corrections(repository, as_of):
    legacy = run_legacy(load_export(settings.export_path), as_of, Corrections.all())
    assert service_summary(repository, as_of) == legacy.summary


def test_every_difference_is_attributed_to_a_documented_finding(repository, as_of):
    rows = load_export(settings.export_path)
    legacy = run_legacy(rows, as_of)
    service_ros = Counter(r["ro_number"] for r in repository.open_repair_orders(as_of.isoformat()))
    only_in_legacy = set((Counter(legacy.counted_ro_numbers) - service_ros).elements())

    status_findings = {
        r["ro_number"]
        for r in rows
        if r["status"] not in ("Closed", "Invoiced", "Void")
        and r["status"].strip().upper() in ("CLOSED", "INVOICED", "VOID")
    }
    exceptions = repository.data_exceptions()
    date_findings = {e["ro_number"] for e in exceptions if "open date" in e["issue"]}
    duplicate_findings = {e["ro_number"] for e in exceptions if "Duplicate" in e["issue"]}

    assert only_in_legacy == status_findings | date_findings | duplicate_findings
    extra_in_service = service_ros - Counter(legacy.counted_ro_numbers)
    assert not extra_in_service, "service reports repair orders the macro does not"


def test_each_correction_moves_results_toward_the_service(repository, as_of):
    rows = load_export(settings.export_path)
    target = sum(count for count, _ in service_summary(repository, as_of).values())

    def total(corrections: Corrections) -> int:
        return sum(count for count, _ in run_legacy(rows, as_of, corrections).summary.values())

    uncorrected = total(Corrections())
    for single in (
        Corrections(normalize_status=True),
        Corrections(exclude_blank_dates=True),
        Corrections(deduplicate=True),
    ):
        assert target <= total(single) < uncorrected
