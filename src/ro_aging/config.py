"""Runtime settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORT = PROJECT_ROOT / "data" / "sample" / "repair_orders.csv"


@dataclass(frozen=True)
class Settings:
    api_key: str
    export_path: Path
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            api_key=os.environ.get("RO_API_KEY", "local-dev-key"),
            export_path=Path(os.environ.get("RO_EXPORT_PATH", DEFAULT_EXPORT)),
            log_level=os.environ.get("RO_LOG_LEVEL", "INFO"),
        )


settings = Settings.from_env()
