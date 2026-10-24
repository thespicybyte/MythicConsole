import json
import os

import pytest

from utils import state


@pytest.fixture(autouse=True)
def isolated_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


def test_get_last_file_dir_is_none_when_no_state_file():
    assert state.get_last_file_dir() is None


def test_set_then_get_last_file_dir_round_trips(tmp_path):
    target = tmp_path / "picks"
    target.mkdir()

    state.set_last_file_dir(str(target))

    assert state.get_last_file_dir() == str(target)


def test_get_last_file_dir_falls_back_to_none_when_dir_no_longer_exists(tmp_path):
    target = tmp_path / "gone"
    target.mkdir()
    state.set_last_file_dir(str(target))
    target.rmdir()

    assert state.get_last_file_dir() is None


def test_get_last_file_dir_falls_back_to_none_on_corrupt_state_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    config_dir = os.path.join(str(tmp_path / "config"), "mythicconsole")
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "state.json"), "w") as f:
        f.write("not json{{{")

    assert state.get_last_file_dir() is None


def test_set_last_file_dir_preserves_other_keys(tmp_path):
    from utils.environment import Environment

    state_file = os.path.join(Environment().config_directory(), "state.json")
    with open(state_file, "w") as f:
        json.dump({"other_key": "keep-me"}, f)

    target = tmp_path / "picks"
    target.mkdir()
    state.set_last_file_dir(str(target))

    with open(state_file) as f:
        data = json.load(f)

    assert data["other_key"] == "keep-me"
    assert data["last_file_dir"] == str(target)
