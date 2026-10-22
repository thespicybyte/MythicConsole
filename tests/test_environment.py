import logging
import os

import pytest

from utils.environment import Environment


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    """Every test runs in an empty tmp dir so `.env` / env vars from the real repo never leak in."""
    monkeypatch.chdir(tmp_path)
    for key in ("MYTHIC_CONSOLE_USER", "MYTHIC_CONSOLE_PASSWORD", "MYTHIC_SERVER_URL",
                "DOWNLOAD_DIRECTORY", "LOG_DIRECTORY", "LOG_FILE", "LOG_LEVEL"):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize("value,expected", [
    ("debug", logging.DEBUG),
    ("DEBUG", logging.DEBUG),
    ("info", logging.INFO),
    ("warn", logging.WARNING),
    ("warning", logging.WARNING),
    ("error", logging.ERROR),
    ("bogus", logging.NOTSET),
])
def test_log_level_mapping(monkeypatch, value, expected):
    monkeypatch.setenv("LOG_LEVEL", value)
    assert Environment().log_level() == expected


def test_log_level_unset_defaults_to_info():
    assert Environment().log_level() == logging.INFO


def test_get_value_from_config_no_env_file():
    assert Environment.get_value_from_config("MYTHIC_CONSOLE_USER") is None


def test_get_value_from_config_parses_key_value(tmp_path):
    (tmp_path / ".env").write_text("MYTHIC_CONSOLE_USER=operator\n")
    assert Environment.get_value_from_config("MYTHIC_CONSOLE_USER") == "operator"


def test_get_value_from_config_preserves_equals_in_value(tmp_path):
    (tmp_path / ".env").write_text("MYTHIC_SERVER_URL=https://host?a=b\n")
    assert Environment.get_value_from_config("MYTHIC_SERVER_URL") == "https://host?a=b"


def test_get_value_from_config_skips_malformed_lines(tmp_path):
    (tmp_path / ".env").write_text("NOTANASSIGNMENT\nMYTHIC_CONSOLE_USER=operator\n")
    assert Environment.get_value_from_config("MYTHIC_CONSOLE_USER") == "operator"


def test_get_value_from_config_missing_key_returns_none(tmp_path):
    (tmp_path / ".env").write_text("SOME_OTHER_KEY=value\n")
    assert Environment.get_value_from_config("MYTHIC_CONSOLE_USER") is None


def test_username_env_var_wins_over_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("MYTHIC_CONSOLE_USER=from_dotenv\n")
    monkeypatch.setenv("MYTHIC_CONSOLE_USER", "from_env")
    assert Environment().username() == "from_env"


def test_username_falls_back_to_dotenv(tmp_path):
    (tmp_path / ".env").write_text("MYTHIC_CONSOLE_USER=from_dotenv\n")
    assert Environment().username() == "from_dotenv"


def test_username_none_when_unset():
    assert Environment().username() is None


def test_password_env_var_wins_over_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("MYTHIC_CONSOLE_PASSWORD=from_dotenv\n")
    monkeypatch.setenv("MYTHIC_CONSOLE_PASSWORD", "from_env")
    assert Environment().password() == "from_env"


def test_server_url_falls_back_to_dotenv(tmp_path):
    (tmp_path / ".env").write_text("MYTHIC_SERVER_URL=https://mythic.local\n")
    assert Environment().server_url() == "https://mythic.local"


def test_server_url_none_when_unset():
    assert Environment().server_url() is None


def test_log_file_default():
    assert Environment().log_file() == ".console.log"


def test_log_file_env_override(monkeypatch):
    monkeypatch.setenv("LOG_FILE", "custom.log")
    assert Environment().log_file() == "custom.log"


def test_download_directory_default(tmp_path):
    assert Environment().download_directory() == os.path.join(os.getcwd(), "downloads")


def test_download_directory_env_creates_dir(tmp_path, monkeypatch):
    target = tmp_path / "dl"
    monkeypatch.setenv("DOWNLOAD_DIRECTORY", str(target))
    result = Environment().download_directory()
    assert result == str(target)
    assert os.path.isdir(target)


def test_log_directory_default(tmp_path):
    assert Environment().log_directory() == os.getcwd()


def test_log_directory_env_creates_dir(tmp_path, monkeypatch):
    target = tmp_path / "logs"
    monkeypatch.setenv("LOG_DIRECTORY", str(target))
    result = Environment().log_directory()
    assert result == str(target)
    assert os.path.isdir(target)
