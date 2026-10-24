import types

import pytest


def _parser(agent, command_name):
    return agent.get_command(command_name).command_parser


# --- JSON object rich types (CredentialJson, AgentConnect, LinkInfo): double-encode fix ---

def test_credential_json_parses_into_a_dict(richtype_agent):
    args = _parser(richtype_agent, "creds").parse_args(
        ["--cred", '{"realm": "CORP", "account": "bob", "credential": "hunter2", "type": "plaintext"}'])

    assert isinstance(args.cred, dict)
    assert args.cred["account"] == "bob"


def test_agent_connect_parses_into_a_dict(richtype_agent):
    args = _parser(richtype_agent, "link").parse_args(
        ["--target", '{"host": "h", "agent_uuid": "11111111-2222-3333-4444-555555555555"}'])

    assert isinstance(args.target, dict)
    assert args.target["host"] == "h"


def test_link_info_parses_into_a_dict(richtype_agent):
    args = _parser(richtype_agent, "p2p_connect").parse_args(
        ["--peer", '{"host": "h", "callback_uuid": "11111111-2222-3333-4444-555555555555"}'])

    assert isinstance(args.peer, dict)


@pytest.mark.parametrize("command,flag", [("creds", "--cred"), ("link", "--target"), ("p2p_connect", "--peer")])
def test_json_object_type_rejects_malformed_json(richtype_agent, command, flag):
    with pytest.raises(SystemExit):
        _parser(richtype_agent, command).parse_args([flag, "not json"])


def test_json_object_type_rejects_a_non_object(richtype_agent):
    with pytest.raises(SystemExit):
        _parser(richtype_agent, "creds").parse_args(["--cred", '["not", "an", "object"]'])


def test_json_object_help_mentions_a_template(richtype_agent):
    action = _parser(richtype_agent, "creds")._option_string_actions["--cred"]
    assert "realm" in action.help
    assert action.metavar == "JSON"


# --- TypedArray ---

def test_typed_array_parses_pairs_with_an_allowed_type(richtype_agent):
    args = _parser(richtype_agent, "tag").parse_args(["--items", '[["string", "a"], ["int", "1"]]'])

    assert args.items == [["string", "a"], ["int", "1"]]


def test_typed_array_rejects_a_disallowed_type(richtype_agent):
    with pytest.raises(SystemExit):
        _parser(richtype_agent, "tag").parse_args(["--items", '[["bogus", "a"]]'])


def test_typed_array_rejects_a_non_list(richtype_agent):
    with pytest.raises(SystemExit):
        _parser(richtype_agent, "tag").parse_args(["--items", '"not a list"'])


def test_typed_array_rejects_malformed_elements(richtype_agent):
    with pytest.raises(SystemExit):
        _parser(richtype_agent, "tag").parse_args(["--items", '[["string"]]'])


# --- File: local-path vs UUID classification, metavar/help ---

def test_file_param_records_an_existing_local_path_on_the_task(richtype_agent, tmp_path):
    local_file = tmp_path / "payload.bin"
    local_file.write_bytes(b"data")

    command = richtype_agent.get_command("stash")
    ns = command.command_parser.parse_args(["--file", str(local_file)])
    task = command._build_task(ns)

    assert task.file_params == {"file": str(local_file)}
    assert task.args["file"] == str(local_file)


def test_file_param_leaves_a_uuid_untouched(richtype_agent):
    command = richtype_agent.get_command("stash")
    ns = command.command_parser.parse_args(["--file", "11111111-2222-3333-4444-555555555555"])
    task = command._build_task(ns)

    assert task.file_params == {}
    assert task.args["file"] == "11111111-2222-3333-4444-555555555555"


def test_file_param_metavar_and_help(richtype_agent):
    action = _parser(richtype_agent, "stash")._option_string_actions["--file"]
    assert action.metavar == "PATH|UUID"
    assert "UUID" in action.help


async def test_task_execute_registers_a_pending_file_before_issuing(richtype_agent, tmp_path, monkeypatch):
    from backend.task.queries import TaskQueries
    from backend.task.task import Task
    import mythic.mythic

    local_file = tmp_path / "payload.bin"
    local_file.write_bytes(b"data")

    command = richtype_agent.get_command("stash")
    ns = command.command_parser.parse_args(["--file", str(local_file)])
    task = command._build_task(ns)
    task.callback = types.SimpleNamespace(display_id=1, loaded_commands=None)
    task.callback_display_id = 1

    async def _register_file(_mythic, filename, contents):
        assert filename == "payload.bin"
        assert contents == b"data"
        return "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    captured = {}

    async def _issue(_mythic, command_name, args, callback_display_id):
        captured["args"] = dict(args)
        return 42

    async def _query(self):
        self.completed = True

    monkeypatch.setattr(mythic.mythic, "register_file", _register_file)
    monkeypatch.setattr(TaskQueries, "execute", _issue)
    monkeypatch.setattr(Task, "query", _query)

    await task.execute()

    assert captured["args"]["file"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert task.id == 42


# --- choices_are_all_commands ---

def test_all_commands_choices_match_the_catalog(richtype_agent, richtype_commands_fixture):
    expected = {spec["cmd"] for spec in richtype_commands_fixture}
    action = _parser(richtype_agent, "run")._option_string_actions["--target_cmd"]

    assert set(action.choices) == expected


def test_all_commands_rejects_an_unknown_command_name(richtype_agent):
    with pytest.raises(SystemExit):
        _parser(richtype_agent, "run").parse_args(["--target_cmd", "not-a-real-command"])


def test_all_commands_completion_lists_the_catalog(richtype_agent, richtype_commands_fixture):
    items = richtype_agent.get_completer_items("run --target_cmd ")

    for spec in richtype_commands_fixture:
        assert spec["cmd"] in items


# --- choices_are_loaded_commands ---

def test_loaded_commands_fail_open_when_loaded_set_unknown(richtype_agent):
    # richtype_agent.tasker.callback is None by default: loaded set is unknown, so any value passes.
    args = _parser(richtype_agent, "unload").parse_args(["--loaded_cmd", "anything"])
    assert args.loaded_cmd == "anything"


def test_loaded_commands_rejects_a_value_outside_the_known_loaded_set(richtype_agent):
    richtype_agent.tasker.callback = types.SimpleNamespace(display_id=1, loaded_commands={"stash", "tag"})

    with pytest.raises(SystemExit):
        _parser(richtype_agent, "unload").parse_args(["--loaded_cmd", "not-loaded"])

    args = _parser(richtype_agent, "unload").parse_args(["--loaded_cmd", "stash"])
    assert args.loaded_cmd == "stash"


def test_loaded_commands_completion_reflects_the_live_loaded_set(richtype_agent):
    richtype_agent.tasker.callback = types.SimpleNamespace(display_id=1, loaded_commands={"stash", "tag"})

    items = richtype_agent.get_completer_items("unload --loaded_cmd ")

    assert set(items) == {"stash", "tag"}


def test_loaded_commands_completion_degrades_to_no_candidates_when_unknown(richtype_agent):
    items = richtype_agent.get_completer_items("unload --loaded_cmd ")
    assert items == []


# --- dynamic_query_function ---

def test_dynamic_query_param_still_parses_as_free_form(richtype_agent):
    args = _parser(richtype_agent, "probe").parse_args(["--target", "anything-the-agent-offers"])
    assert args.target == "anything-the-agent-offers"


def test_dynamic_query_help_mentions_runtime_options(richtype_agent):
    action = _parser(richtype_agent, "probe")._option_string_actions["--target"]
    assert "runtime" in action.help


def test_dynamic_query_completion_degrades_to_empty_offline(richtype_agent):
    items = richtype_agent.get_completer_items("probe --target ")
    assert items == []


# --- Static choices (ChooseOne) are now a completion source too ---

def test_static_choices_completion(richtype_agent):
    items = richtype_agent.get_completer_items("mode --level ")
    assert set(items) == {"low", "medium", "high"}


def test_static_choices_still_validated_by_argparse(richtype_agent):
    with pytest.raises(SystemExit):
        _parser(richtype_agent, "mode").parse_args(["--level", "extreme"])


# --- Grouped commands: flag->param map is keyed per group ---

def test_grouped_command_same_flag_resolves_to_its_own_group_param(richtype_agent):
    richtype_agent._payload_uuid_cache = ["cccccccc-dddd-eeee-ffff-000000000000"]

    push_items = richtype_agent.get_completer_items("deliver Push --target ")
    pull_items = richtype_agent.get_completer_items("deliver Pull --target ")

    # Push's --target is a File param (no completion source -> falls through to flag/subcommand options).
    assert "cccccccc-dddd-eeee-ffff-000000000000" not in push_items
    # Pull's --target is a PayloadList param -> served from the warmed cache.
    assert pull_items == ["cccccccc-dddd-eeee-ffff-000000000000"]


# --- PayloadList ---

def test_payload_list_metavar_and_help(richtype_agent):
    action = _parser(richtype_agent, "relay")._option_string_actions["--payload"]
    assert action.metavar == "PAYLOAD_UUID"
    assert "payload list" in action.help


def test_payload_list_completion_served_from_the_warmed_cache(richtype_agent):
    richtype_agent._payload_uuid_cache = ["11111111-1111-1111-1111-111111111111"]

    items = richtype_agent.get_completer_items("relay --payload ")

    assert items == ["11111111-1111-1111-1111-111111111111"]


def test_payload_list_accepts_a_raw_uuid_string(richtype_agent):
    args = _parser(richtype_agent, "relay").parse_args(["--payload", "11111111-1111-1111-1111-111111111111"])
    assert args.payload == "11111111-1111-1111-1111-111111111111"
