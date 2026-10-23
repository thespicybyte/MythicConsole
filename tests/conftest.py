import base64
import json
import types
from pathlib import Path

import pytest

from agents.Poseidon.poseidon import Poseidon
from backend.formatter.formatter import DefaultFormatter
from backend.mythic_agent.mythic_agent import MythicAgent
from backend.task.task import Task

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_instance():
    """Stub MythicInstance: satisfies `.mythic` reads without a network connection."""
    return types.SimpleNamespace(mythic=None)


@pytest.fixture
def poseidon_commands_fixture():
    """Trimmed, captured `get_all_commands_for_payloadtype("poseidon", ...)` response."""
    return json.loads((FIXTURES / "poseidon_commands.json").read_text())


@pytest.fixture
def generic_commands_fixture():
    """Synthetic `get_all_commands_for_payloadtype("testagent", ...)` response."""
    return json.loads((FIXTURES / "generic_commands.json").read_text())


@pytest.fixture
def arachne_commands_fixture():
    """Captured `get_all_commands_for_payloadtype("arachne", ...)` response (a real, non-Poseidon agent)."""
    return json.loads((FIXTURES / "arachne_commands.json").read_text())


@pytest.fixture
def make_task(fake_instance):
    def _make_task(command="ls", args="", callback_display_id=1, loaded_commands=None,
                   completed=True, **extra):
        callback = types.SimpleNamespace(display_id=callback_display_id,
                                          loaded_commands=loaded_commands)
        task = Task(fake_instance, command=command, args=args, callback=callback)
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
async def poseidon_agent(fake_instance, poseidon_commands_fixture):
    """A loaded Poseidon agent, fed the captured fixture instead of the network."""
    agent = Poseidon(fake_instance)

    async def _fetch_server_commands():
        return poseidon_commands_fixture

    agent._fetch_server_commands = _fetch_server_commands
    await agent.load_commands()
    return agent


@pytest.fixture
async def generic_agent(fake_instance, generic_commands_fixture):
    """A loaded base MythicAgent (no curated overrides), fed the synthetic fixture."""
    agent = MythicAgent("testagent", fake_instance, DefaultFormatter())

    async def _fetch_server_commands():
        return generic_commands_fixture

    agent._fetch_server_commands = _fetch_server_commands
    await agent.load_commands()
    return agent


@pytest.fixture
async def arachne_agent(fake_instance, arachne_commands_fixture):
    """A loaded base MythicAgent, fed the captured arachne dump (a real, non-Poseidon agent)."""
    agent = MythicAgent("arachne", fake_instance, DefaultFormatter())

    async def _fetch_server_commands():
        return arachne_commands_fixture

    agent._fetch_server_commands = _fetch_server_commands
    await agent.load_commands()
    return agent
