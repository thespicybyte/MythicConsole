import pytest

from agents import UnknownAgent, get_agent
from backend.formatter.formatter import DefaultFormatter
from backend.mythic_agent.mythic_agent import MythicAgent
from backend.task.task import Task, TaskError
from plugins.base import PluginAgent


def test_get_agent_returns_plugin_agent_when_one_is_installed(fake_instance, installed_testplugin):
    agent = get_agent(fake_instance, "testplugin")

    assert isinstance(agent, PluginAgent)
    assert agent.name == "testplugin"


def test_get_agent_returns_generic_for_payload_type_with_no_plugin(fake_instance, installed_testplugin):
    """A plugin being installed for one payload type must not make any other name special."""
    agent = get_agent(fake_instance, "poseidon")

    assert isinstance(agent, MythicAgent)
    assert not isinstance(agent, PluginAgent)
    assert agent.name == "poseidon"
    assert isinstance(agent.formatter, DefaultFormatter)


def test_get_agent_returns_generic_for_unknown(fake_instance):
    agent = get_agent(fake_instance, "testagent")

    assert isinstance(agent, MythicAgent)
    assert not isinstance(agent, PluginAgent)
    assert agent.name == "testagent"
    assert isinstance(agent.formatter, DefaultFormatter)


@pytest.mark.parametrize("payload_type_name", ["", None])
def test_get_agent_falsy_payload_type_raises(fake_instance, payload_type_name):
    with pytest.raises(UnknownAgent):
        get_agent(fake_instance, payload_type_name)


async def test_generic_agent_loads_generated_commands(arachne_agent, arachne_commands_fixture):
    expected_names = {spec["cmd"] for spec in arachne_commands_fixture}

    for name in expected_names:
        assert name in arachne_agent.commands

    assert "directory" not in arachne_agent.commands
    assert "process" not in arachne_agent.commands


async def test_generic_agent_missing_dir_yields_no_scripts(generic_agent):
    assert generic_agent.scripts == []


async def test_generic_agent_completer_lists_generated_commands(arachne_agent, arachne_commands_fixture):
    items = arachne_agent.get_completer_items("")

    assert "help" in items
    for spec in arachne_commands_fixture:
        assert spec["cmd"] in items

    options = arachne_agent.get_completer_items("ls ")
    assert "--path" in options
    assert "-bg" in options


async def test_generic_agent_loaded_gate_rejects_unloaded(make_task):
    task = make_task(command="echo", loaded_commands={"ls", "pwd"})

    with pytest.raises(TaskError, match="echo.*not loaded"):
        await task.execute()


async def test_generic_agent_param_types_generate_expected_arguments(generic_agent):
    echo_options = generic_agent.get_command_parser("echo")._option_string_actions
    assert "--text" in echo_options
    assert "--shout" in echo_options
    assert echo_options["--shout"].const is True or echo_options["--shout"].action == "store_true"

    connect_options = generic_agent.get_command_parser("connect")._option_string_actions
    assert connect_options["--protocol"].choices == ["tcp", "udp", "smb"]
    assert connect_options["--port"].type is int


async def test_generic_agent_multi_group_command_yields_subcommands(generic_agent):
    subcommands = generic_agent.get_subcommands("transfer")

    assert set(subcommands) == {"Push", "Pull"}
    assert "--path" in generic_agent.get_subcommand_options("transfer", "Push")
    assert "--remote_path" in generic_agent.get_subcommand_options("transfer", "Pull")
