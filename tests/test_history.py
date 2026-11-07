import json
import os

import pytest

from utils.history import PersistentCommandHistory, load_history


@pytest.fixture(autouse=True)
def isolated_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


def test_round_trip_recalls_prior_session_commands(tmp_path):
    path = tmp_path / "history.json"
    history = PersistentCommandHistory(str(path))
    history.record("whoami")
    history.record("ls -la")

    reloaded = load_history(str(path))

    assert reloaded.entries == ["whoami", "ls -la"]
    assert reloaded.previous("") == "ls -la"
    assert reloaded.previous("") == "whoami"


def test_record_persists_immediately(tmp_path):
    path = tmp_path / "history.json"
    history = PersistentCommandHistory(str(path))

    history.record("whoami")

    with open(path) as f:
        data = json.load(f)
    assert data == ["whoami"]


def test_cap_enforced_on_disk_and_in_memory(tmp_path):
    path = tmp_path / "history.json"
    history = PersistentCommandHistory(str(path), max_entries=5)

    for i in range(10):
        history.record(f"cmd{i}")

    expected = [f"cmd{i}" for i in range(5, 10)]
    assert history.entries == expected

    with open(path) as f:
        data = json.load(f)
    assert data == expected


def test_load_history_missing_file_returns_empty(tmp_path):
    path = tmp_path / "does_not_exist.json"
    history = load_history(str(path))
    assert history.entries == []


def test_load_history_corrupt_file_returns_empty(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("not json{{{")

    history = load_history(str(path))

    assert history.entries == []


def test_load_history_drops_non_string_entries(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(json.dumps([1, "ok", None]))

    history = load_history(str(path))

    assert history.entries == ["ok"]


def test_multiline_command_round_trips(tmp_path):
    path = tmp_path / "history.json"
    history = PersistentCommandHistory(str(path))

    history.record("line1\nline2")

    reloaded = load_history(str(path))
    assert reloaded.entries == ["line1\nline2"]


def test_loading_saved_entries_does_not_rewrite_file(tmp_path):
    path = tmp_path / "history.json"
    PersistentCommandHistory(str(path)).record("whoami")
    before = path.read_bytes()
    os.utime(path, (0, 0))

    load_history(str(path))

    assert path.read_bytes() == before


def test_skipped_blank_does_not_rewrite_file(tmp_path):
    path = tmp_path / "history.json"
    history = PersistentCommandHistory(str(path))
    history.record("whoami")
    before_mtime = os.path.getmtime(path)

    history.record("   ")

    assert os.path.getmtime(path) == before_mtime


def test_load_history_uses_environment_default_when_no_path_given(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    history = load_history()
    history.record("whoami")

    expected_path = tmp_path / "config" / "mythicconsole" / "history.json"
    assert expected_path.exists()
    with open(expected_path) as f:
        assert json.load(f) == ["whoami"]
