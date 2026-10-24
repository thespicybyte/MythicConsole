import base64
import json
import types
from pathlib import Path

import pytest
from rich.table import Table

from backend.task.task import Task
from plugins.installer import install_from_path
from plugins.registry import PluginRegistry

pytestmark = pytest.mark.reference_plugin

REFERENCE_POSEIDON = Path(__file__).parent.parent / "reference_plugins" / "poseidon"
FIXTURES = REFERENCE_POSEIDON / "tests" / "fixtures"
POSEIDON_COMMANDS = json.loads((FIXTURES / "poseidon_commands.json").read_text())


async def test_install_from_path_restores_curated_commands_and_renderer(tmp_path, monkeypatch):
    install_from_path(REFERENCE_POSEIDON, tmp_path)

    registry = PluginRegistry()
    registry.discover(tmp_path)
    agent_class = registry.agent_class_for("poseidon")
    assert agent_class is not None

    fake_instance = types.SimpleNamespace(mythic=None)
    agent = agent_class(fake_instance)

    async def _fetch_server_commands():
        return POSEIDON_COMMANDS

    agent._fetch_server_commands = _fetch_server_commands
    await agent.load_commands()

    assert "ls" not in agent.commands
    assert "directory" in agent.commands

    raw = (FIXTURES / "poseidon_ls.json").read_text()

    async def _get_responses(self):
        yield types.SimpleNamespace(response_text=base64.b64encode(raw.encode("utf8")).decode("ascii"))

    monkeypatch.setattr(Task, "get_responses", _get_responses)

    task = Task(fake_instance, command="ls", args="",
               callback=types.SimpleNamespace(display_id=1, loaded_commands=None))
    task.completed = True

    result = await agent.formatter.format_output(task)
    assert isinstance(result, Table)
