"""HTTP API and web interface for open repair order aging."""

from __future__ import annotations

import csv
import io
import logging
import secrets
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Security, status
from fastapi.responses import FileResponse, Response
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from ro_aging import __version__
from ro_aging.config import settings
from ro_aging.legacy import load_export
from ro_aging.reconciliation import reconcile
from ro_aging.repository import AGE_BUCKETS, RepairOrderRepository

STATIC_DIR = Path(__file__).parent / "static"
EXPORT_COLUMNS = (
    "ro_number",
    "branch",
    "open_date",
    "age_days",
    "age_bucket",
    "status",
    "payer_type",
    "unit",
    "complaint",
    "technician",
    "open_dollars",
)

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ro_aging")

app = FastAPI(
    title="Open Repair Order Aging API",
    description="Read-only service department reporting over DMS repair order data.",
    version=__version__,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

repository = RepairOrderRepository.from_export(settings.export_path)
logger.info("Loaded repair order export from %s", settings.export_path)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    if key is None or not secrets.compare_digest(key, settings.api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid API key")


def validate_branch(branch: str | None) -> None:
    if branch is not None and branch not in repository.branches():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown branch: {branch}")


def validate_bucket(bucket: str | None) -> None:
    if bucket is not None and bucket not in AGE_BUCKETS:
        raise HTTPException(422, f"bucket must be one of {list(AGE_BUCKETS)}")


AsOf = Query(default_factory=date.today, description="Date to measure age against")
v1 = "/api/v1"
secured = [Depends(require_api_key)]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get(f"{v1}/branches", tags=["reference"], dependencies=secured)
def list_branches() -> list[str]:
    return repository.branches()


@app.get(f"{v1}/ro-aging", tags=["aging"], dependencies=secured)
def ro_aging_summary(branch: str | None = None, as_of: date = AsOf) -> dict:
    """Open repair order counts and dollars by branch and age bucket."""
    validate_branch(branch)
    return {
        "as_of": as_of.isoformat(),
        "branch": branch,
        "buckets": list(AGE_BUCKETS),
        "rows": repository.aging_summary(as_of.isoformat(), branch),
    }


@app.get(f"{v1}/ro-aging/detail", tags=["aging"], dependencies=secured)
def ro_aging_detail(
    branch: str | None = None, bucket: str | None = None, as_of: date = AsOf
) -> list[dict]:
    """Individual open repair orders behind the summary, oldest first."""
    validate_branch(branch)
    validate_bucket(bucket)
    return repository.open_repair_orders(as_of.isoformat(), branch, bucket)


@app.get(f"{v1}/ro-aging/breakdown", tags=["aging"], dependencies=secured)
def ro_aging_breakdown(branch: str | None = None, as_of: date = AsOf) -> dict:
    """Open repair orders grouped by status, payer type and technician."""
    validate_branch(branch)
    return repository.breakdown(as_of.isoformat(), branch)


@app.get(f"{v1}/ro-aging/export.csv", tags=["aging"], dependencies=secured)
def ro_aging_export(
    branch: str | None = None, bucket: str | None = None, as_of: date = AsOf
) -> Response:
    """Open repair orders as a CSV file for Excel."""
    validate_branch(branch)
    validate_bucket(bucket)
    rows = repository.open_repair_orders(as_of.isoformat(), branch, bucket)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    filename = f"open-repair-orders-{as_of.isoformat()}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get(f"{v1}/data-exceptions", tags=["data quality"], dependencies=secured)
def data_exceptions() -> list[dict]:
    """Records that need to be corrected in the DMS."""
    return repository.data_exceptions()


@app.get(f"{v1}/reconciliation", tags=["data quality"], dependencies=secured)
def reconciliation(as_of: date = AsOf) -> dict:
    """Legacy report totals compared with this service, with every difference attributed."""
    return reconcile(load_export(settings.export_path), repository, as_of)
