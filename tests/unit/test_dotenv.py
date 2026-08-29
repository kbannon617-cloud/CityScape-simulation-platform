"""Unit tests for the minimal stdlib .env loader."""

import os

from cinis.config.dotenv import load_dotenv


def test_loads_simple_key_value_pairs(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\nBAZ=qux\n")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)

    load_dotenv(env_file)

    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "qux"


def test_ignores_comments_and_blank_lines(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("# a comment\n\nFOO=bar\n   # another comment\n")
    monkeypatch.delenv("FOO", raising=False)

    load_dotenv(env_file)

    assert os.environ["FOO"] == "bar"


def test_does_not_override_existing_env_var(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=from_file\n")
    monkeypatch.setenv("FOO", "from_real_env")

    load_dotenv(env_file)

    assert os.environ["FOO"] == "from_real_env"


def test_strips_surrounding_quotes(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('FOO="quoted value"\nBAR=\'single quoted\'\n')
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAR", raising=False)

    load_dotenv(env_file)

    assert os.environ["FOO"] == "quoted value"
    assert os.environ["BAR"] == "single quoted"


def test_missing_file_does_nothing(tmp_path):
    load_dotenv(tmp_path / "does_not_exist.env")  # should not raise
