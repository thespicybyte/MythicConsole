from poseidon.poseidon import Poseidon
from backend.mythic_agent.mythic_agent import AgentCommands


async def test_load_commands_populates_generated_set(fake_instance, poseidon_commands_fixture):
    agent = Poseidon(fake_instance)

    async def _fetch_server_commands():
        return poseidon_commands_fixture

    agent._fetch_server_commands = _fetch_server_commands
    await agent.load_commands()

    assert isinstance(agent.commands, AgentCommands)
    assert "directory" in agent.commands
    assert "ls" not in agent.commands
    names = {command.name for command in agent.commands}
    assert "directory" in names


async def test_poseidon_override_pops_curated_groupings_and_tweaks_exit(poseidon_agent):
    assert "ls" not in poseidon_agent.commands
    assert "cd" not in poseidon_agent.commands
    assert "mkdir" not in poseidon_agent.commands
    assert "pwd" not in poseidon_agent.commands

    directory = poseidon_agent.commands["directory"]
    alias_names = {alias.name for alias in directory.aliases}
    assert alias_names == {"ls", "cd", "mkdir", "pwd"}

    exit_command = poseidon_agent.commands["exit"]
    assert exit_command.verify_prompt is not None
    assert exit_command.force_background is True

    sleep_command = poseidon_agent.commands["sleep"]
    assert sleep_command.name == "sleep"
    assert sleep_command.command_parser.parse_args(["--interval", "1"]).interval == 1
