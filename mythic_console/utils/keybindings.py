import json
from dataclasses import dataclass

from textual.app import App
from textual.keys import Keys, key_to_character

from mythic_console.utils.environment import Environment

_MODIFIERS = frozenset({"ctrl", "shift", "alt", "meta", "super", "hyper"})
_KEY_VALUES = {key.value for key in Keys}


@dataclass(frozen=True)
class RebindableAction:
    """One operator-rebindable key binding: a stable id, its default key string, a
    Settings panel label, a display group, and the namespace it resolves in."""
    id: str
    default_key: str
    label: str
    group: str
    namespace: str = "home"


REBINDABLE_ACTIONS: tuple[RebindableAction, ...] = (
    RebindableAction("toggle_sidebar", "ctrl+s", "Toggle sidebar", "Sidebar"),
    RebindableAction("shrink_sidebar", "ctrl+shift+comma", "Shrink sidebar", "Sidebar"),
    RebindableAction("grow_sidebar", "ctrl+shift+full_stop", "Grow sidebar", "Sidebar"),
    RebindableAction("shrink_sidebar_alt", "alt+left", "Shrink sidebar (alternate)", "Sidebar"),
    RebindableAction("grow_sidebar_alt", "alt+right", "Grow sidebar (alternate)", "Sidebar"),
    RebindableAction("next_tab", "ctrl+pageup", "Next tab", "Tabs"),
    RebindableAction("previous_tab", "ctrl+pagedown", "Previous tab", "Tabs"),
    RebindableAction("next_tab_alt", "alt+tab", "Next tab (alternate)", "Tabs"),
    RebindableAction("previous_tab_alt", "alt+shift+tab", "Previous tab (alternate)", "Tabs"),
    RebindableAction("close_tab", "ctrl+q", "Close tab", "Tabs"),
    RebindableAction("background_current_task", "ctrl+z", "Background task", "Tasks"),
    RebindableAction("manage_callbacks", "m", "Manage callbacks", "Callbacks"),
    RebindableAction("toggle_autoscroll", "ctrl+shift+a", "Toggle autoscroll", "Console"),
    RebindableAction("toggle_log_viewer", "f2", "Log viewer", "Console"),
    RebindableAction("toggle_word_wrap", "f3", "Toggle word wrap", "Console"),
    RebindableAction("logout", "ctrl+l", "Logout", "Session"),
    RebindableAction("login_quit", "ctrl+q", "Quit (login screen)", "Session", namespace="login"),
)

DEFAULTS: dict[str, str] = {action.id: action.default_key for action in REBINDABLE_ACTIONS}
ACTIONS_BY_ID: dict[str, RebindableAction] = {action.id: action for action in REBINDABLE_ACTIONS}


def _reserved_key() -> str:
    return App.COMMAND_PALETTE_BINDING


def is_valid_key(key: str) -> bool:
    """A key string is valid when every token before the final `+` is a recognized
    modifier and the final token is a known Textual key name or a single character."""
    if not key:
        return False

    *modifiers, final = key.split("+")
    if any(modifier not in _MODIFIERS for modifier in modifiers):
        return False
    if not final:
        return False

    if final in _KEY_VALUES:
        return True

    return key_to_character(final) is not None


def is_reserved_key(key: str) -> bool:
    return key == _reserved_key()


def find_conflicts(values: dict[str, str]) -> dict[str, str]:
    """Given an id -> key map covering some or all registry ids (missing ids fall back to
    their default), returns id -> clashing id for every id whose key collides with another
    id in the same namespace."""
    conflicts: dict[str, str] = {}
    by_namespace: dict[str, dict[str, str]] = {}
    for action in REBINDABLE_ACTIONS:
        key = values.get(action.id, action.default_key)
        namespace_map = by_namespace.setdefault(action.namespace, {})
        clash_id = next((other_id for other_id, other_key in namespace_map.items() if other_key == key), None)
        if clash_id is not None:
            conflicts[action.id] = clash_id
            conflicts.setdefault(clash_id, action.id)
        namespace_map[action.id] = key
    return conflicts


def effective_keymap(overrides: dict[str, str]) -> dict[str, str]:
    """The full id -> key map: every registry id, using its override when present
    and its default otherwise."""
    return {action.id: overrides.get(action.id, action.default_key) for action in REBINDABLE_ACTIONS}


def diff_from_defaults(effective: dict[str, str]) -> dict[str, str]:
    """The subset of an effective id -> key map that differs from the registry defaults."""
    return {action_id: key for action_id, key in effective.items() if DEFAULTS.get(action_id) != key}


def _config_file() -> str:
    return Environment().keybindings_file()


def _read_config() -> dict:
    try:
        with open(_config_file(), "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _resolve_overrides(candidate: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Seed every id's default key into its namespace map. Then, for each candidate
    override in registry order: free that id's own (default) slot, and if the proposed
    key is not held by any other id in the namespace, move it there and accept the
    override; otherwise restore the id's default and produce a feedback message. This
    guarantees the final map (accepted overrides plus every other id's default) never
    holds a duplicate key within a namespace, whichever side of the clash is the one
    actually sitting on the contested key."""
    messages: list[str] = []
    accepted: dict[str, str] = {}
    by_namespace: dict[str, dict[str, str]] = {}

    for action in REBINDABLE_ACTIONS:
        by_namespace.setdefault(action.namespace, {})[action.id] = action.default_key

    for action in REBINDABLE_ACTIONS:
        if action.id not in candidate:
            continue
        key = candidate[action.id]
        namespace_map = by_namespace[action.namespace]
        del namespace_map[action.id]
        clash_id = next((other_id for other_id, other_key in namespace_map.items()
                          if other_key == key), None)
        if clash_id is not None:
            namespace_map[action.id] = action.default_key
            messages.append(f"key '{key}' for '{action.id}' conflicts with '{clash_id}'; default kept")
            continue
        namespace_map[action.id] = key
        accepted[action.id] = key

    return accepted, messages


def load_keymap() -> tuple[dict[str, str], list[str]]:
    """Read and validate the keybindings config file. Returns the accepted id -> key
    overrides (unlisted ids keep their default) and a list of feedback messages for
    anything that was ignored or rejected. Never raises."""
    messages: list[str] = []
    raw = _read_config()

    candidate: dict[str, str] = {}
    for action_id, key in raw.items():
        if action_id not in DEFAULTS:
            messages.append(f"unknown key binding id '{action_id}' ignored")
            continue
        if not isinstance(key, str) or not is_valid_key(key):
            messages.append(f"invalid key for '{action_id}' ignored; default kept")
            continue
        if is_reserved_key(key):
            messages.append(f"key '{key}' for '{action_id}' is reserved for the command palette; default kept")
            continue
        candidate[action_id] = key

    accepted, conflict_messages = _resolve_overrides(candidate)
    messages.extend(conflict_messages)
    return accepted, messages


def save_overrides(overrides: dict[str, str]) -> None:
    try:
        with open(_config_file(), "w") as f:
            json.dump(overrides, f)
    except OSError:
        pass
