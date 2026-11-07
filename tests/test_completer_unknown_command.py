"""Regression coverage: an unknown multi-token command line must complete to `[]`, never raise.

Pins the `[]`/no-crash contract across both completer classes (`MythicAgent`,
`MythicCommands`) for the trigger matrix of an unrecognized first token, the `help`
pseudo-command, and the >=3-token form. Also covers the sibling script-path guard in
`MythicAgent.get_completer_items`'s 2-token branch, where a registered script with no
subcommand parser keyed by its own name hits the same None-parser pattern.
"""
import pytest

from backend.mythic_agent.mythic_agent import AgentCommand, MythicCommands


@pytest.mark.parametrize("line", [
    "bogus_command sub extra",
    "help a b c",
    "bogus sub x y z",
    "bogus_command sub",
])
async def test_agent_unknown_command_completes_empty(arachne_agent, line):
    assert arachne_agent.get_completer_items(line) == []


async def test_agent_real_command_without_subcommands_still_completes(arachne_agent):
    items = arachne_agent.get_completer_items("ls bogus_sub extra")

    assert set(items) == {"-h", "--help", "--path", "-bg", "--background"}


async def test_agent_script_without_matching_subcommand_parser_completes_empty(arachne_agent):
    # A registered script whose subcommand_parsers has no key equal to its own name hits the
    # same None-parser pattern as the reported crash, in the sibling (2-token) branch.
    stub_script = AgentCommand(arachne_agent, name="stubscript", subcommand_parsers={})
    arachne_agent.scripts = [stub_script]

    assert arachne_agent.get_completer_items("stubscript x") == []


@pytest.mark.parametrize("line", [
    "bogus_command sub extra",
    "help a b c",
    "operation bogus_sub extra",
    "op bogus_sub extra",
    "bogus_command sub",
])
async def test_mythic_commands_unknown_command_completes_empty(fake_instance, line):
    commands = MythicCommands(fake_instance)

    assert commands.get_completer_items(line) == []
