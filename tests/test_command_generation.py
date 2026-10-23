import types

import pytest

from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommands


def _spec(fixture, name):
    for command in fixture:
        if command["cmd"] == name:
            return command
    raise KeyError(name)


def _fake_agent():
    tasker = types.SimpleNamespace(callback=types.SimpleNamespace(display_id=1))
    return types.SimpleNamespace(instance=types.SimpleNamespace(mythic=None), tasker=tasker)


def _command(fixture, name):
    return AgentCommand.from_server(_fake_agent(), _spec(fixture, name))


def test_simple_command_parses_string_and_number(poseidon_commands_fixture):
    ls = _command(poseidon_commands_fixture, "ls")

    args = ls.command_parser.parse_args(["--path", "/etc", "--depth", "2"])

    assert args.path == "/etc"
    assert args.depth == 2
    assert isinstance(args.depth, int)


def test_choose_one_enforces_choices_and_applies_default(poseidon_commands_fixture):
    curl = _command(poseidon_commands_fixture, "curl")

    args = curl.command_parser.parse_args(["--url", "http://x", "--method", "POST"])
    assert args.method == "POST"

    args = curl.command_parser.parse_args(["--url", "http://x"])
    assert args.method == "GET"

    with pytest.raises(SystemExit):
        curl.command_parser.parse_args(["--url", "http://x", "--method", "BOGUS"])

    assert "--method" in AgentCommand.get_parser_options(curl.command_parser)


def test_parameter_group_builds_one_subparser_per_call_style(poseidon_commands_fixture):
    sshauth = _command(poseidon_commands_fixture, "sshauth")

    assert "run-command-plaintext-password" in sshauth.get_subcommands()
    assert "scp-private-key" in sshauth.get_subcommands()

    parser = sshauth.get_subcommand_parser("run-command-plaintext-password")
    args = parser.parse_args(["--username", "root", "--password", "hunter2", "--hosts", "h1",
                              "--command", "whoami"])
    assert args.username == "root"
    assert args.password == "hunter2"
    assert args.hosts == ["h1"]
    assert args.command == "whoami"


def test_array_and_number_params_required(poseidon_commands_fixture):
    portscan = _command(poseidon_commands_fixture, "portscan")

    args = portscan.command_parser.parse_args(["--hosts", "a", "b", "--ports", "22", "80"])
    assert args.hosts == ["a", "b"]
    assert args.ports == ["22", "80"]

    with pytest.raises(SystemExit):
        portscan.command_parser.parse_args([])


def test_boolean_param_is_store_true_and_omitted_when_absent(poseidon_commands_fixture):
    caffeinate = _command(poseidon_commands_fixture, "caffeinate")

    args = caffeinate.command_parser.parse_args([])
    assert not args.enable

    task = caffeinate._build_task(args)
    assert "enable" not in task.args

    args = caffeinate.command_parser.parse_args(["--enable"])
    task = caffeinate._build_task(args)
    assert task.args["enable"] is True


def test_rich_type_param_passes_through_a_raw_uuid_string(poseidon_commands_fixture):
    execute_library = _command(poseidon_commands_fixture, "execute_library")

    parser = execute_library.get_subcommand_parser("New File")
    args = parser.parse_args(["--file_id", "11111111-2222-3333-4444-555555555555",
                              "--function_name", "main", "--file_path", "/tmp/x", "--args", "a"])
    assert args.file_id == "11111111-2222-3333-4444-555555555555"


def test_dynamic_query_param_is_free_form(poseidon_commands_fixture):
    upload = _command(poseidon_commands_fixture, "upload")

    parser = upload.get_subcommand_parser("existingFile")
    args = parser.parse_args(["--existingFile", "any-name-the-server-would-have-offered"])
    assert args.existingFile == "any-name-the-server-would-have-offered"


@pytest.mark.parametrize("name", ["ls", "cd", "mkdir", "pwd", "exit", "curl", "sshauth",
                                   "portscan", "sleep", "execute_library", "caffeinate", "upload"])
def test_every_generated_command_carries_background_flag(poseidon_commands_fixture, name):
    command = _command(poseidon_commands_fixture, name)
    parsers = list(command.subcommand_parsers.values()) or [command.command_parser]
    for parser in parsers:
        assert "--background" in AgentCommand.get_parser_options(parser)


def test_agent_commands_is_name_keyed_but_iterates_as_objects():
    a = AgentCommand(_fake_agent(), name="a", description="", command_parser=None)
    b = AgentCommand(_fake_agent(), name="b", description="", command_parser=None)

    commands = AgentCommands([a, b])

    assert commands["a"] is a
    assert "b" in commands
    assert list(commands) == [a, b]

    commands.pop("a")
    assert "a" not in commands
    assert list(commands) == [b]

    commands["c"] = a
    assert commands.get("c") is a
    assert commands.get("missing") is None


def test_agent_commands_aliases_aggregate_across_commands():
    from backend.mythic_agent.mythic_agent import AgentCommandAlias

    a = AgentCommand(_fake_agent(), name="a", description="", command_parser=None,
                     aliases=[AgentCommandAlias("x", "a")])
    b = AgentCommand(_fake_agent(), name="b", description="", command_parser=None,
                     aliases=[AgentCommandAlias("y", "b")])

    commands = AgentCommands([a, b])

    assert {alias.name for alias in commands.aliases} == {"x", "y"}
