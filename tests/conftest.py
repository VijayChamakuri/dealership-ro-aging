from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from ro_aging.config import settings
from ro_aging.repository import RepairOrderRepository

AS_OF = date(2026, 10, 21)


@pytest.fixture(scope="session")
def as_of() -> date:
    return AS_OF


@pytest.fixture(scope="session")
def repository() -> RepairOrderRepository:
    return RepairOrderRepository.from_export(settings.export_path)


@pytest.fixture(scope="session")
def client() -> TestClient:
    from ro_aging.api import app

    return TestClient(app)


@pytest.fixture(scope="session")
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": settings.api_key}
