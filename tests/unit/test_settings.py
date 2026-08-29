"""Smoke tests for the Milestone 1 config loader."""

import pytest

from cinis.config.settings import ConfigurationError, load_database_settings


def test_windows_auth_builds_trusted_connection_url(monkeypatch):
    monkeypatch.setenv("CINIS_DB_AUTH", "windows")
    monkeypatch.setenv("CINIS_DB_SERVER", r"localhost\SQLEXPRESS")
    monkeypatch.setenv("CINIS_DB_NAME", "CinisDev")
    monkeypatch.setenv("CINIS_DB_DRIVER", "ODBC Driver 17 for SQL Server")

    settings = load_database_settings()
    url = settings.to_sqlalchemy_url()

    assert url.startswith("mssql+pyodbc://@")
    assert "trusted_connection=yes" in url
    assert "CinisDev" in url


def test_sql_auth_requires_user_and_password(monkeypatch):
    monkeypatch.setenv("CINIS_DB_AUTH", "sql")
    monkeypatch.setenv("CINIS_DB_SERVER", "localhost")
    monkeypatch.setenv("CINIS_DB_NAME", "CinisDev")
    monkeypatch.delenv("CINIS_DB_USER", raising=False)
    monkeypatch.delenv("CINIS_DB_PASSWORD", raising=False)

    settings = load_database_settings()

    with pytest.raises(ConfigurationError):
        settings.to_sqlalchemy_url()


def test_missing_server_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("CINIS_DB_SERVER", raising=False)
    monkeypatch.setenv("CINIS_DB_NAME", "CinisDev")

    with pytest.raises(ConfigurationError):
        load_database_settings()
