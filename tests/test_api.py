"""HTTP contract and access control."""

from __future__ import annotations

import pytest

PROTECTED = [
    "/api/v1/ro-aging/breakdown",
    "/api/v1/ro-aging/export.csv",
    "/api/v1/reconciliation",
    "/api/v1/branches",
    "/api/v1/ro-aging",
    "/api/v1/ro-aging/detail",
    "/api/v1/data-exceptions",
]


@pytest.mark.parametrize("path", PROTECTED)
def test_requires_api_key(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", PROTECTED)
def test_rejects_invalid_api_key(client, path):
    assert client.get(path, headers={"X-API-Key": "invalid"}).status_code == 401


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_summary(client, auth_headers, as_of):
    response = client.get(
        "/api/v1/ro-aging", params={"as_of": as_of.isoformat()}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["as_of"] == as_of.isoformat()
    assert body["buckets"] == ["0-7", "8-15", "16-30", "31-60", "61-90", "90+"]
    assert sum(r["ro_count"] for r in body["rows"]) > 0


def test_detail_is_sorted_oldest_first(client, auth_headers, as_of):
    rows = client.get(
        "/api/v1/ro-aging/detail", params={"as_of": as_of.isoformat()}, headers=auth_headers
    ).json()
    ages = [r["age_days"] for r in rows]
    assert ages == sorted(ages, reverse=True)


def test_unknown_branch_returns_404(client, auth_headers):
    response = client.get("/api/v1/ro-aging", params={"branch": "Unknown"}, headers=auth_headers)
    assert response.status_code == 404


def test_invalid_bucket_returns_422(client, auth_headers):
    response = client.get(
        "/api/v1/ro-aging/detail", params={"bucket": "100+"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_invalid_date_returns_422(client, auth_headers):
    response = client.get("/api/v1/ro-aging", params={"as_of": "not-a-date"}, headers=auth_headers)
    assert response.status_code == 422


def test_breakdown_totals_match_summary(client, auth_headers, as_of):
    params = {"as_of": as_of.isoformat()}
    summary = client.get("/api/v1/ro-aging", params=params, headers=auth_headers).json()
    breakdown = client.get("/api/v1/ro-aging/breakdown", params=params, headers=auth_headers).json()
    expected = sum(r["ro_count"] for r in summary["rows"])
    for dimension in ("status", "payer_type", "technician"):
        assert sum(g["ro_count"] for g in breakdown[dimension]) == expected


def test_csv_export(client, auth_headers, as_of):
    response = client.get(
        "/api/v1/ro-aging/export.csv",
        params={"as_of": as_of.isoformat(), "branch": "Nashville"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("ro_number,branch,open_date,age_days")
    assert all(",Nashville," in line for line in lines[1:])


def test_reconciliation_explains_every_difference(client, auth_headers, as_of):
    body = client.get(
        "/api/v1/reconciliation", params={"as_of": as_of.isoformat()}, headers=auth_headers
    ).json()
    assert body["unexplained"] == []
    assert sum(f["ro_count"] for f in body["findings"]) == body["difference"]["ro_count"]
    assert (
        round(sum(f["dollars"] for f in body["findings"]), 2) == body["difference"]["open_dollars"]
    )
