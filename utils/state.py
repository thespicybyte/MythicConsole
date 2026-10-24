import json
import os
from typing import Optional

from utils.environment import Environment


def _state_file() -> str:
    return os.path.join(Environment().config_directory(), "state.json")


def _read_state() -> dict:
    try:
        with open(_state_file(), "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(state: dict) -> None:
    try:
        with open(_state_file(), "w") as f:
            json.dump(state, f)
    except OSError:
        pass


def get_last_file_dir() -> Optional[str]:
    value = _read_state().get("last_file_dir")
    if isinstance(value, str) and os.path.isdir(value):
        return value
    return None


def set_last_file_dir(directory: str) -> None:
    state = _read_state()
    state["last_file_dir"] = directory
    _write_state(state)
