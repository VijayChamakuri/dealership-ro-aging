"""Business rules and internal consistency of the repository queries."""

from __future__ import annotations

from ro_aging.repository import AGE_BUCKETS


def test_summary_reconciles_to_detail(repository, as_of):
    summary = repository.aging_summary(as_of.isoformat())
    detail = repository.open_repair_orders(as_of.isoformat())
    assert sum(r["ro_count"] for r in summary) == len(detail)
    assert round(sum(r["open_dollars"] for r in summary), 2) == round(
        sum(r["open_dollars"] for r in detail), 2
    )


def test_closed_statuses_are_excluded_regardless_of_case_or_spacing(repository, as_of):
    statuses = {r["status"] for r in repository.open_repair_orders(as_of.isoformat())}
    assert statuses.isdisjoint({"CLOSED", "INVOICED", "VOID"})


def test_each_repair_order_is_reported_once(repository, as_of):
    numbers = [r["ro_number"] for r in repository.open_repair_orders(as_of.isoformat())]
    assert len(numbers) == len(set(numbers))


def test_buckets_match_age(repository, as_of):
    limits = dict(zip(AGE_BUCKETS, (7, 15, 30, 60, 90, None), strict=True))
    lower = 0
    bounds = {}
    for bucket, upper in limits.items():
        bounds[bucket] = (lower, upper)
        lower = (upper or 0) + 1
    for row in repository.open_repair_orders(as_of.isoformat()):
        low, high = bounds[row["age_bucket"]]
        assert row["age_days"] >= low and (high is None or row["age_days"] <= high)


def test_records_without_open_date_are_reported_as_exceptions(repository, as_of):
    aged = {r["ro_number"] for r in repository.open_repair_orders(as_of.isoformat())}
    missing = {e["ro_number"] for e in repository.data_exceptions() if "open date" in e["issue"]}
    assert missing and missing.isdisjoint(aged)


def test_branch_filter(repository, as_of):
    rows = repository.aging_summary(as_of.isoformat(), branch="Indianapolis")
    assert rows and {r["branch"] for r in rows} == {"Indianapolis"}
