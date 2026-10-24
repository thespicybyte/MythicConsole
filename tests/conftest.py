import base64
import json
import types
from pathlib import Path

import pytest

from backend.formatter.formatter import DefaultFormatter
from backend.mythic_agent.mythic_agent import MythicAgent
from backend.task.task import Task
from plugins import registry
from plugins.installer import install_from_path
from plugins.registry import get_plugin_registry

FIXTURES = Path(__file__).parent / "fixtures"
TESTPLUGIN_DIR = FIXTURES / "plugins" / "testplugin"


@pytest.fixture(autouse=True)
def isolated_plugin_registry(tmp_path):
    """Every test's default (lazy) plugin registry points at an empty temp dir, never the real
    machine's plugins dir -- so no test can accidentally discover (or create) real installed
    plugins. Tests that need a specific plugins dir override it explicitly (see `installed_testplugin`)."""
    registry.reset()
    registry.set_plugins_dir(str(tmp_path / "empty_plugins_dir"))
    yield
    registry.reset()


@pytest.fixture
def fake_instance():
    """Stub MythicInstance: satisfies `.mythic` reads without a network connection."""
    return types.SimpleNamespace(mythic=None)


@pytest.fixture
def generic_commands_fixture():
    """Synthetic `get_all_commands_for_payloadtype("testagent", ...)` response."""
    return json.loads((FIXTURES / "generic_commands.json").read_text())


@pytest.fixture
def arachne_commands_fixture():
    """Captured `get_all_commands_for_payloadtype("arachne", ...)` response (a real, non-Poseidon agent)."""
    return json.loads((FIXTURES / "arachne_commands.json").read_text())


@pytest.fixture
def richtype_commands_fixture():
    """Synthetic `get_all_commands_for_payloadtype("richagent", ...)` response exercising every rich
    type (File, PayloadList, CredentialJson, AgentConnect, LinkInfo, TypedArray) and every dynamic
    kind (choices_are_all_commands, choices_are_loaded_commands, dynamic_query_function), plus a
    static-choices param and a grouped command."""
    return json.loads((FIXTURES / "richtype_commands.json").read_text())


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
def temp_plugins_dir(tmp_path):
    """An isolated plugins dir for the registry singleton; reset after the test."""
    yield tmp_path
    registry.reset()


@pytest.fixture
def installed_testplugin(temp_plugins_dir):
    """Copies the synthetic testplugin fixture into a temp plugins dir and loads the registry from it."""
    install_from_path(TESTPLUGIN_DIR, temp_plugins_dir)
    registry.set_plugins_dir(str(temp_plugins_dir))
    registry.load_installed_plugins()
    return temp_plugins_dir


@pytest.fixture
async def test_plugin_agent(fake_instance, generic_commands_fixture, installed_testplugin):
    """A loaded test-plugin agent, fed the synthetic fixture instead of the network."""
    agent_class = get_plugin_registry().agent_class_for("testplugin")
    agent = agent_class(fake_instance)

    async def _fetch_server_commands():
        return generic_commands_fixture

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


@pytest.fixture
async def richtype_agent(fake_instance, richtype_commands_fixture):
    """A loaded base MythicAgent, fed the synthetic rich/dynamic-param fixture."""
    agent = MythicAgent("richagent", fake_instance, DefaultFormatter())

    async def _fetch_server_commands():
        return richtype_commands_fixture

    agent._fetch_server_commands = _fetch_server_commands
    await agent.load_commands()
    return agent
