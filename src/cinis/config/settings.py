"""
Application configuration loaded strictly from environment variables.

No connection strings, credentials, or secrets are ever hardcoded here,
consistent with the Master Prompt's "No Hardcoded Secrets" guardrail.
Local development values come from a .env file (git-ignored) that mirrors
.env.example.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class DatabaseSettings:
    auth_mode: str  # "windows" or "sql"
    server: str
    database: str
    driver: str
    user: str | None = None
    password: str | None = None

    def to_sqlalchemy_url(self) -> str:
        """Build a mssql+pyodbc SQLAlchemy URL from these settings."""
        driver_q = self.driver.replace(" ", "+")

        if self.auth_mode == "windows":
            return (
                f"mssql+pyodbc://@{self.server}/{self.database}"
                f"?driver={driver_q}&trusted_connection=yes"
            )
        if self.auth_mode == "sql":
            if not self.user or not self.password:
                raise ConfigurationError(
                    "CINIS_DB_USER and CINIS_DB_PASSWORD are required when "
                    "CINIS_DB_AUTH=sql"
                )
            return (
                f"mssql+pyodbc://{self.user}:{self.password}@{self.server}/"
                f"{self.database}?driver={driver_q}"
            )
        raise ConfigurationError(
            f"Unsupported CINIS_DB_AUTH value: {self.auth_mode!r} "
            "(expected 'windows' or 'sql')"
        )


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value


def load_database_settings() -> DatabaseSettings:
    """Load DatabaseSettings from environment variables."""
    auth_mode = os.environ.get("CINIS_DB_AUTH", "windows").lower()

    return DatabaseSettings(
        auth_mode=auth_mode,
        server=_require("CINIS_DB_SERVER"),
        database=_require("CINIS_DB_NAME"),
        driver=os.environ.get("CINIS_DB_DRIVER", "ODBC Driver 17 for SQL Server"),
        user=os.environ.get("CINIS_DB_USER") or None,
        password=os.environ.get("CINIS_DB_PASSWORD") or None,
    )
