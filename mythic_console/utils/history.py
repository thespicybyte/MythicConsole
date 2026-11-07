import json
import os

from textual_console import CommandHistory

from mythic_console.utils.environment import Environment

MAX_HISTORY_ENTRIES = 1000


class PersistentCommandHistory(CommandHistory):
    """A CommandHistory that writes itself to disk whenever a command is recorded."""

    def __init__(self, path, entries=(), *, max_entries=MAX_HISTORY_ENTRIES):
        self._path = path
        self._loading = True
        super().__init__(entries, max_entries=max_entries)
        self._loading = False

    def record(self, command):
        before = tuple(self._entries)
        super().record(command)
        if not self._loading and tuple(self._entries) != before:
            self._save()

    def _save(self):
        try:
            tmp = f"{self._path}.tmp"
            with open(tmp, "w") as f:
                json.dump(self._entries, f)
            os.replace(tmp, self._path)
        except OSError:
            pass


def load_history(path=None, *, max_entries=MAX_HISTORY_ENTRIES):
    if path is None:
        path = Environment().history_file()
    entries = []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            entries = [e for e in data if isinstance(e, str)]
    except (OSError, ValueError):
        entries = []
    return PersistentCommandHistory(path, entries, max_entries=max_entries)
