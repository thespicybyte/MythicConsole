from backend.mythic_agent.mythic_agent import AgentCommands
from plugins.registry import get_plugin_registry


async def test_load_commands_populates_generated_set(fake_instance, generic_commands_fixture,
                                                      installed_testplugin):
    agent_class = get_plugin_registry().agent_class_for("testplugin")
    agent = agent_class(fake_instance)

    async def _fetch_server_commands():
        return generic_commands_fixture

    agent._fetch_server_commands = _fetch_server_commands
    await agent.load_commands()

    assert isinstance(agent.commands, AgentCommands)
    assert "net" in agent.commands
    assert "echo" not in agent.commands
    names = {command.name for command in agent.commands}
    assert "net" in names


async def test_plugin_override_pops_generated_commands_and_adds_grouped_alias(test_plugin_agent):
    assert "echo" not in test_plugin_agent.commands
    assert "connect" not in test_plugin_agent.commands
    assert "transfer" in test_plugin_agent.commands

    net = test_plugin_agent.commands["net"]
    alias_names = {alias.name for alias in net.aliases}
    assert alias_names == {"echo", "connect"}

    assert test_plugin_agent.get_script("ping") is not None
