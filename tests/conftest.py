import base64
import types

import pytest

from agents.Poseidon.poseidon import Poseidon
from backend.task.task import Task


@pytest.fixture
def fake_instance():
    """Stub MythicInstance: satisfies `.mythic` reads without a network connection."""
    return types.SimpleNamespace(mythic=None)


@pytest.fixture
def make_task(fake_instance):
    def _make_task(command="ls", args="", callback_display_id=1, completed=True, **extra):
        task = Task(fake_instance, command=command, args=args, callback_display_id=callback_display_id)
        task.completed = completed
        for key, value in extra.items():
            setattr(task, key, value)
        return task

    return _make_task


@pytest.fixture
def fake_responses(monkeypatch):
    """Patch Task.get_responses to yield `chunks` (plain strings) as base64-encoded response_text."""

    def _install(chunks):
        async def _get_responses(self):
            for chunk in chunks:
                encoded = base64.b64encode(chunk.encode("utf8")).decode("ascii")
                yield types.SimpleNamespace(response_text=encoded)

        monkeypatch.setattr(Task, "get_responses", _get_responses)

    return _install


@pytest.fixture
def poseidon_agent(fake_instance):
    return Poseidon(fake_instance)
