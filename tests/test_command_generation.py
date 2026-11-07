import types

import pytest

from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, AgentCommands


def _param(name, param_type, required=False, default_value=None, group="Default",
          position=0, choices=None, **extra):
    return {
        "name": name, "cli_name": name, "type": param_type, "required": required,
        "default_value": default_value, "description": "", "parameter_group_name": group,
        "ui_position": position, "choices": choices or [],
        "choices_are_all_commands": False, "choices_are_loaded_commands": False,
        "dynamic_query_function": extra.get("dynamic_query_function", ""),
    }


SIMPLE_SPEC = {"cmd": "simple", "description": "", "commandparameters": [
    _param("path", "String", required=True, position=0),
    _param("depth", "Number", position=1),
]}

CHOOSE_ONE_SPEC = {"cmd": "fetch", "description": "", "commandparameters": [
    _param("url", "String", required=True, position=0),
    _param("method", "ChooseOne", default_value="GET", choices=["GET", "POST"], position=1),
]}

PARAMETER_GROUP_SPEC = {"cmd": "transfer", "description": "", "commandparameters": [
    _param("path", "String", required=True, group="Push", position=0),
    _param("remote_path", "String", required=True, group="Pull", position=0),
]}

ARRAY_SPEC = {"cmd": "portscan", "description": "", "commandparameters": [
    _param("hosts", "Array", required=True, position=0),
    _param("ports", "Array", required=True, position=1),
]}

BOOLEAN_SPEC = {"cmd": "caffeinate", "description": "", "commandparameters": [
    _param("enable", "Boolean", default_value="false", position=0),
]}

RICH_TYPE_SPEC = {"cmd": "execute_library", "description": "", "commandparameters": [
    _param("file_id", "File", required=True, group="New File", position=0),
    _param("function_name", "String", required=True, group="New File", position=1),
    _param("existing_id", "File", required=True, group="Existing File", position=0),
]}

DYNAMIC_QUERY_SPEC = {"cmd": "upload", "description": "", "commandparameters": [
    _param("existingFile", "String", dynamic_query_function="get_existing_files", position=0),
]}

GENERATED_SPECS = [SIMPLE_SPEC, CHOOSE_ONE_SPEC, PARAMETER_GROUP_SPEC, ARRAY_SPEC,
                   BOOLEAN_SPEC, RICH_TYPE_SPEC, DYNAMIC_QUERY_SPEC]


def _fake_agent():
    tasker = types.SimpleNamespace(callback=types.SimpleNamespace(display_id=1))
    return types.SimpleNamespace(instance=types.SimpleNamespace(mythic=None), tasker=tasker)


def _command(spec):
    return AgentCommand.from_server(_fake_agent(), spec)


def test_simple_command_parses_string_and_number():
    simple = _command(SIMPLE_SPEC)

    args = simple.command_parser.parse_args(["--path", "/etc", "--depth", "2"])

    assert args.path == "/etc"
    assert args.depth == 2
    assert isinstance(args.depth, int)


def test_choose_one_enforces_choices_and_applies_default():
    fetch = _command(CHOOSE_ONE_SPEC)

    args = fetch.command_parser.parse_args(["--url", "http://x", "--method", "POST"])
    assert args.method == "POST"

    args = fetch.command_parser.parse_args(["--url", "http://x"])
    assert args.method == "GET"

    with pytest.raises(SystemExit):
        fetch.command_parser.parse_args(["--url", "http://x", "--method", "BOGUS"])

    assert "--method" in AgentCommand.get_parser_options(fetch.command_parser)


def test_parameter_group_builds_one_subparser_per_call_style():
    transfer = _command(PARAMETER_GROUP_SPEC)

    assert set(transfer.get_subcommands()) == {"Push", "Pull"}

    push_parser = transfer.get_subcommand_parser("Push")
    args = push_parser.parse_args(["--path", "/local"])
    assert args.path == "/local"

    pull_parser = transfer.get_subcommand_parser("Pull")
    args = pull_parser.parse_args(["--remote_path", "/remote"])
    assert args.remote_path == "/remote"


def test_array_and_number_params_required():
    portscan = _command(ARRAY_SPEC)

    args = portscan.command_parser.parse_args(["--hosts", "a", "b", "--ports", "22", "80"])
    assert args.hosts == ["a", "b"]
    assert args.ports == ["22", "80"]

    with pytest.raises(SystemExit):
        portscan.command_parser.parse_args([])


def test_boolean_param_is_store_true_and_omitted_when_absent():
    caffeinate = _command(BOOLEAN_SPEC)

    args = caffeinate.command_parser.parse_args([])
    assert not args.enable

    task = caffeinate._build_task(args)
    assert "enable" not in task.args

    args = caffeinate.command_parser.parse_args(["--enable"])
    task = caffeinate._build_task(args)
    assert task.args["enable"] is True


def test_rich_type_param_passes_through_a_raw_uuid_string():
    execute_library = _command(RICH_TYPE_SPEC)

    parser = execute_library.get_subcommand_parser("New File")
    args = parser.parse_args(["--file_id", "11111111-2222-3333-4444-555555555555",
                              "--function_name", "main"])
    assert args.file_id == "11111111-2222-3333-4444-555555555555"


def test_dynamic_query_param_is_free_form():
    upload = _command(DYNAMIC_QUERY_SPEC)

    args = upload.command_parser.parse_args(["--existingFile", "any-name-the-server-would-have-offered"])
    assert args.existingFile == "any-name-the-server-would-have-offered"


@pytest.mark.parametrize("spec", GENERATED_SPECS, ids=[spec["cmd"] for spec in GENERATED_SPECS])
def test_every_generated_command_carries_background_flag(spec):
    command = _command(spec)
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
    a = AgentCommand(_fake_agent(), name="a", description="", command_parser=None,
                     aliases=[AgentCommandAlias("x", "a")])
    b = AgentCommand(_fake_agent(), name="b", description="", command_parser=None,
                     aliases=[AgentCommandAlias("y", "b")])

    commands = AgentCommands([a, b])

    assert {alias.name for alias in commands.aliases} == {"x", "y"}
