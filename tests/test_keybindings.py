import json
import os

import pytest

from mythic_console.utils import keybindings
from mythic_console.utils.environment import Environment


@pytest.fixture(autouse=True)
def isolated_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


@pytest.mark.parametrize("key", ["ctrl+s", "f2", "m", "alt+shift+tab", "ctrl+shift+full_stop", "escape"])
def test_is_valid_key_accepts(key):
    assert keybindings.is_valid_key(key) is True


@pytest.mark.parametrize("key", ["", "ctrl+", "notakey", "ctrl+notakey", "foo+s"])
def test_is_valid_key_rejects(key):
    assert keybindings.is_valid_key(key) is False


def test_is_reserved_key_matches_command_palette_binding():
    assert keybindings.is_reserved_key("ctrl+p") is True
    assert keybindings.is_reserved_key("ctrl+s") is False


def _write_config(data: dict) -> None:
    with open(Environment().keybindings_file(), "w") as f:
        json.dump(data, f)


def _assert_no_duplicate_keys_within_any_namespace(overrides: dict) -> None:
    effective = keybindings.effective_keymap(overrides)
    by_namespace: dict[str, list[str]] = {}
    for action_id, key in effective.items():
        namespace = keybindings.ACTIONS_BY_ID[action_id].namespace
        by_namespace.setdefault(namespace, []).append(key)
    for keys in by_namespace.values():
        assert len(keys) == len(set(keys))


def test_load_keymap_valid_file_returns_expected_overrides():
    _write_config({"toggle_sidebar": "ctrl+g", "manage_callbacks": "n"})

    overrides, messages = keybindings.load_keymap()

    assert overrides == {"toggle_sidebar": "ctrl+g", "manage_callbacks": "n"}
    assert messages == []


def test_load_keymap_unknown_id_ignored_with_message():
    _write_config({"not_a_real_action": "ctrl+g"})

    overrides, messages = keybindings.load_keymap()

    assert overrides == {}
    assert any("not_a_real_action" in message for message in messages)


def test_load_keymap_invalid_key_dropped_with_message_and_default_kept():
    _write_config({"toggle_sidebar": "notakey"})

    overrides, messages = keybindings.load_keymap()

    assert "toggle_sidebar" not in overrides
    assert any("toggle_sidebar" in message for message in messages)


def test_load_keymap_duplicate_key_rejected_with_message():
    _write_config({"toggle_sidebar": "ctrl+z", "background_current_task": "ctrl+z"})

    overrides, messages = keybindings.load_keymap()

    assert "toggle_sidebar" not in overrides
    assert any("toggle_sidebar" in message for message in messages)
    _assert_no_duplicate_keys_within_any_namespace(overrides)


def test_load_keymap_override_colliding_with_untouched_default_is_rejected_with_message():
    _write_config({"toggle_sidebar": "ctrl+z"})

    overrides, messages = keybindings.load_keymap()

    assert "toggle_sidebar" not in overrides
    assert any("toggle_sidebar" in message for message in messages)
    _assert_no_duplicate_keys_within_any_namespace(overrides)


def test_load_keymap_two_overrides_that_would_swap_onto_each_others_default_are_both_rejected():
    _write_config({"toggle_sidebar": "m", "background_current_task": "ctrl+s"})

    overrides, messages = keybindings.load_keymap()

    assert "toggle_sidebar" not in overrides
    assert "background_current_task" not in overrides
    assert len(messages) == 2
    _assert_no_duplicate_keys_within_any_namespace(overrides)


def test_load_keymap_reserved_key_rejected_with_message():
    _write_config({"toggle_sidebar": "ctrl+p"})

    overrides, messages = keybindings.load_keymap()

    assert "toggle_sidebar" not in overrides
    assert any("toggle_sidebar" in message for message in messages)


def test_load_keymap_missing_file_returns_empty_with_no_exception():
    overrides, messages = keybindings.load_keymap()

    assert overrides == {}
    assert messages == []


def test_load_keymap_malformed_json_returns_empty_with_no_exception():
    with open(Environment().keybindings_file(), "w") as f:
        f.write("not json{{{")

    overrides, messages = keybindings.load_keymap()

    assert overrides == {}
    assert messages == []


def test_save_overrides_round_trips_and_persists_only_non_default_entries():
    effective = keybindings.effective_keymap({"toggle_sidebar": "ctrl+g"})
    overrides = keybindings.diff_from_defaults(effective)

    keybindings.save_overrides(overrides)

    with open(Environment().keybindings_file()) as f:
        written = json.load(f)
    assert written == {"toggle_sidebar": "ctrl+g"}

    loaded_overrides, messages = keybindings.load_keymap()
    assert loaded_overrides == {"toggle_sidebar": "ctrl+g"}
    assert messages == []


def test_save_overrides_writes_in_config_directory():
    keybindings.save_overrides({"toggle_sidebar": "ctrl+g"})

    assert os.path.isfile(os.path.join(Environment().config_directory(), "keybindings.json"))
