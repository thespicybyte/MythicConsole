import types

import pytest

from agents.Poseidon.poseidon import Poseidon
from backend.mythic_agent.mythic_agent import AgentCommand

_agent = Poseidon(types.SimpleNamespace(mythic=None))

# Commands whose parser intentionally has no `-bg/--background` flag: they must always
# run in the foreground (e.g. `exit` forces a confirmation prompt before killing the agent).
_NO_BACKGROUND_FLAG = {"exit"}


def test_discovers_all_23_poseidon_commands():
    names = sorted(command.name for command in _agent.commands)
    assert len(names) == 23
    assert len(set(names)) == 23


@pytest.mark.parametrize("command", _agent.commands, ids=lambda c: c.name)
def test_command_parser_carries_background_flag(command):
    if command.name in _NO_BACKGROUND_FLAG:
        pytest.skip(f"{command.name} intentionally omits -bg/--background")

    parsers = list(command.subcommand_parsers.values()) or [command.command_parser]
    for parser in parsers:
        options = AgentCommand.get_parser_options(parser)
        assert "--background" in options, f"{command.name}: {parser.prog} missing -bg/--background"


@pytest.mark.parametrize("command", _agent.commands, ids=lambda c: c.name)
def test_command_parse_args_empty_yields_falsy_background(command):
    if command.subcommand_parsers:
        pytest.skip(f"{command.name} requires a subcommand to parse")
    if command.name in _NO_BACKGROUND_FLAG:
        pytest.skip(f"{command.name} has no -bg/--background flag to default")

    args = command.command_parser.parse_args([])
    assert not args.background


def test_sleep_parses_interval_and_jitter():
    sleep = _agent.get_command("sleep")
    args = sleep.command_parser.parse_args(["--interval", "5", "--jitter", "10"])
    assert args.interval == 5
    assert args.jitter == 10


def test_process_list_subcommand_parses_regex_filter():
    process = _agent.get_command("process")
    parser = process.get_subcommand_parser("list")
    args = parser.parse_args(["--regex", "chrome.*"])
    assert args.regex == "chrome.*"


def test_command_run_subcommand_parses_shell_command():
    command = _agent.get_command("command")
    parser = command.get_subcommand_parser("run")
    args = parser.parse_args(["echo", "hello"])
    assert args.command == ["echo", "hello"]
