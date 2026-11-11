import types
from io import StringIO

import pytest
from rich.console import Console

import mythic_console.backend.disabled_commands_profile.queries as dcp_queries
from mythic_console.backend.disabled_commands_profile.disabled_commands_profile import DisabledCommandsProfile
from mythic_console.backend.disabled_commands_profile.queries import DisabledCommandsProfileQueries
from mythic_console.backend.mythic_agent import mythic_agent
from mythic_console.backend.mythic_agent.mythic_agent import MythicCommands
from mythic_console.backend.payload_type.queries import PayloadTypeQueries
from mythic_console.backend.user.queries import UserQueries

from conftest import completer_values


def _render(renderable) -> str:
    console = Console(file=StringIO(), width=200)
    console.print(renderable)
    return console.file.getvalue()


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@pytest.fixture
def mythic_commands(fake_instance):
    fake_instance.mythic = types.SimpleNamespace(username="alice", current_operation_id=7)
    return MythicCommands(fake_instance)


# ---- query helper variable shape ----


async def test_insert_command_sends_only_name_and_command_id(monkeypatch):
    captured = {}

    async def fake_execute_custom_query(mythic, query, variables=None):
        captured["variables"] = variables
        return {"insert_disabledcommandsprofile_one": {"id": 1, "name": "no-exec", "command_id": 5}}

    monkeypatch.setattr(dcp_queries.mythic, "execute_custom_query", fake_execute_custom_query)

    await DisabledCommandsProfileQueries.insert_command(None, "no-exec", 5)

    assert captured["variables"] == {"object": {"name": "no-exec", "command_id": 5}}


async def test_delete_entry_sends_row_ids(monkeypatch):
    captured = {}

    async def fake_execute_custom_query(mythic, query, variables=None):
        captured["variables"] = variables
        return {"deleteBlockListEntry": {"status": "success", "error": None, "name": "no-exec"}}

    monkeypatch.setattr(dcp_queries.mythic, "execute_custom_query", fake_execute_custom_query)

    await DisabledCommandsProfileQueries.delete_entry(None, "no-exec", [3])

    assert captured["variables"] == {"name": "no-exec", "entries": [3]}


async def test_assign_sends_profile_id_and_user_id(monkeypatch):
    captured = {}

    async def fake_execute_custom_query(mythic, query, variables=None):
        captured["variables"] = variables
        return {"updateOperatorOperation": {"status": "success", "error": None}}

    monkeypatch.setattr(dcp_queries.mythic, "execute_custom_query", fake_execute_custom_query)

    await DisabledCommandsProfileQueries.assign(None, 7, 3, 1)

    assert captured["variables"] == {
        "operation_id": 7,
        "disabled_command_map": [{"disabled_command_profile_id": 3, "user_id": 1}],
    }


async def test_unassign_sends_sentinel_profile_id_zero(monkeypatch):
    captured = {}

    async def fake_execute_custom_query(mythic, query, variables=None):
        captured["variables"] = variables
        return {"updateOperatorOperation": {"status": "success", "error": None}}

    monkeypatch.setattr(dcp_queries.mythic, "execute_custom_query", fake_execute_custom_query)

    await DisabledCommandsProfileQueries.unassign(None, 7, 1)

    assert captured["variables"] == {
        "operation_id": 7,
        "disabled_command_map": [{"disabled_command_profile_id": 0, "user_id": 1}],
    }


# ---- status/error mapping from custom actions ----


async def test_delete_entry_raises_on_status_failure(monkeypatch):
    async def fake_execute_custom_query(mythic, query, variables=None):
        return {"deleteBlockListEntry": {"status": "error", "error": "not found", "name": "no-exec"}}

    monkeypatch.setattr(dcp_queries.mythic, "execute_custom_query", fake_execute_custom_query)

    with pytest.raises(Exception, match="not found"):
        await DisabledCommandsProfileQueries.delete_entry(None, "no-exec", [3])


async def test_delete_profile_raises_on_status_failure(monkeypatch):
    async def fake_execute_custom_query(mythic, query, variables=None):
        return {"deleteBlockList": {"status": "error", "error": "not found", "name": "no-exec"}}

    monkeypatch.setattr(dcp_queries.mythic, "execute_custom_query", fake_execute_custom_query)

    with pytest.raises(Exception, match="not found"):
        await DisabledCommandsProfileQueries.delete_profile(None, "no-exec")


async def test_assign_raises_on_status_failure(monkeypatch):
    async def fake_execute_custom_query(mythic, query, variables=None):
        return {"updateOperatorOperation": {"status": "error", "error": "denied"}}

    monkeypatch.setattr(dcp_queries.mythic, "execute_custom_query", fake_execute_custom_query)

    with pytest.raises(Exception, match="denied"):
        await DisabledCommandsProfileQueries.assign(None, 7, 3, 1)


# ---- command resolution ----


def _payload_types(*names):
    return [{"id": i, "name": name, "deleted": False} for i, name in enumerate(names, start=1)]


async def test_resolve_command_id_unique_without_payload_type(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_query_all_payload_types(session):
        return _payload_types("poseidon", "apfell")

    async def fake_get_all_commands_for_payloadtype(session, payload_type_name, custom_return_attributes=None):
        if payload_type_name == "poseidon":
            return [{"id": 10, "cmd": "ls"}]
        return [{"id": 20, "cmd": "pwd"}]

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)
    import mythic_console.backend.disabled_commands_profile.disabled_commands_profile as dcp_module
    monkeypatch.setattr(dcp_module.mythic_lib, "get_all_commands_for_payloadtype",
                         fake_get_all_commands_for_payloadtype)

    command_id = await profile.resolve_command_id("ls")

    assert command_id == 10


async def test_resolve_command_id_ambiguous_without_payload_type_errors_with_candidates(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_query_all_payload_types(session):
        return _payload_types("poseidon", "apfell")

    async def fake_get_all_commands_for_payloadtype(session, payload_type_name, custom_return_attributes=None):
        return [{"id": 10 if payload_type_name == "poseidon" else 20, "cmd": "cd"}]

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)
    import mythic_console.backend.disabled_commands_profile.disabled_commands_profile as dcp_module
    monkeypatch.setattr(dcp_module.mythic_lib, "get_all_commands_for_payloadtype",
                         fake_get_all_commands_for_payloadtype)

    with pytest.raises(Exception) as excinfo:
        await profile.resolve_command_id("cd")

    assert "poseidon" in str(excinfo.value)
    assert "apfell" in str(excinfo.value)


async def test_resolve_command_id_with_payload_type_disambiguates(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_get_all_commands_for_payloadtype(session, payload_type_name, custom_return_attributes=None):
        assert payload_type_name == "poseidon"
        return [{"id": 10, "cmd": "cd"}]

    import mythic_console.backend.disabled_commands_profile.disabled_commands_profile as dcp_module
    monkeypatch.setattr(dcp_module.mythic_lib, "get_all_commands_for_payloadtype",
                         fake_get_all_commands_for_payloadtype)

    command_id = await profile.resolve_command_id("cd", payload_type="poseidon")

    assert command_id == 10


async def test_resolve_command_id_unknown_command_errors(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_query_all_payload_types(session):
        return _payload_types("poseidon")

    async def fake_get_all_commands_for_payloadtype(session, payload_type_name, custom_return_attributes=None):
        return [{"id": 10, "cmd": "ls"}]

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)
    import mythic_console.backend.disabled_commands_profile.disabled_commands_profile as dcp_module
    monkeypatch.setattr(dcp_module.mythic_lib, "get_all_commands_for_payloadtype",
                         fake_get_all_commands_for_payloadtype)

    with pytest.raises(Exception, match="not found"):
        await profile.resolve_command_id("ghost")


# ---- create / add semantics ----


async def test_create_rejects_duplicate_name(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_get_by_name(session, operation_id, name):
        return [{"id": 1, "name": name, "command_id": 9}]

    monkeypatch.setattr(DisabledCommandsProfileQueries, "get_by_name", fake_get_by_name)

    with pytest.raises(Exception, match="already exists"):
        await profile.create("no-exec", [9])


async def test_create_with_no_command_rejected_by_argparse():
    from mythic_console.backend.mythic_agent import mythic_command_parsers

    with pytest.raises(SystemExit):
        mythic_command_parsers.operation_blocklist_create_parser.parse_args(["no-exec"])


async def test_create_inserts_each_command_id(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_get_by_name(session, operation_id, name):
        return []

    inserted = []

    async def fake_insert_command(session, name, command_id):
        inserted.append((name, command_id))
        return {"id": len(inserted), "name": name, "command_id": command_id}

    monkeypatch.setattr(DisabledCommandsProfileQueries, "get_by_name", fake_get_by_name)
    monkeypatch.setattr(DisabledCommandsProfileQueries, "insert_command", fake_insert_command)

    await profile.create("no-exec", [1, 2])

    assert inserted == [("no-exec", 1), ("no-exec", 2)]


async def test_remove_resolves_row_id_then_deletes_entry(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_get_by_name(session, operation_id, name):
        return [{"id": 11, "name": name, "command_id": 5}, {"id": 12, "name": name, "command_id": 6}]

    calls = []

    async def fake_delete_entry(session, name, row_ids):
        calls.append((name, row_ids))

    monkeypatch.setattr(DisabledCommandsProfileQueries, "get_by_name", fake_get_by_name)
    monkeypatch.setattr(DisabledCommandsProfileQueries, "delete_entry", fake_delete_entry)

    await profile.remove("no-exec", 6)

    assert calls == [("no-exec", [12])]


async def test_remove_unknown_command_in_profile_errors(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_get_by_name(session, operation_id, name):
        return [{"id": 11, "name": name, "command_id": 5}]

    monkeypatch.setattr(DisabledCommandsProfileQueries, "get_by_name", fake_get_by_name)

    with pytest.raises(Exception, match="not in block list"):
        await profile.remove("no-exec", 999)


async def test_assign_uses_lowest_row_id_as_anchor(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_get_by_name(session, operation_id, name):
        return [{"id": 15, "name": name, "command_id": 5}, {"id": 11, "name": name, "command_id": 6}]

    calls = []

    async def fake_assign(session, operation_id, profile_row_id, user_id):
        calls.append((operation_id, profile_row_id, user_id))

    monkeypatch.setattr(DisabledCommandsProfileQueries, "get_by_name", fake_get_by_name)
    monkeypatch.setattr(DisabledCommandsProfileQueries, "assign", fake_assign)

    await profile.assign("no-exec", 3)

    assert calls == [(7, 11, 3)]


async def test_assign_unknown_profile_errors(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_get_by_name(session, operation_id, name):
        return []

    monkeypatch.setattr(DisabledCommandsProfileQueries, "get_by_name", fake_get_by_name)

    with pytest.raises(Exception, match="not found"):
        await profile.assign("ghost", 3)


# ---- confirm gating + severity on command handlers ----


async def test_blocklist_remove_prompts_and_cancels_without_mutation(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return False

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_resolve_command_id(self, cmd_name, payload_type=None):
        calls.append("resolved")
        return 9

    async def fake_remove(self, name, command_id):
        calls.append("removed")

    monkeypatch.setattr(DisabledCommandsProfile, "resolve_command_id", fake_resolve_command_id)
    monkeypatch.setattr(DisabledCommandsProfile, "remove", fake_remove)

    result = await mythic_commands._blocklist_remove(
        _Args(name="no-exec", command="shell", payload_type=None, force=False))

    assert calls == []
    assert result.plain == "Cancelled"
    assert result.style == "yellow"


async def test_blocklist_remove_force_skips_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_resolve_command_id(self, cmd_name, payload_type=None):
        return 9

    removed = []

    async def fake_remove(self, name, command_id):
        removed.append((name, command_id))

    monkeypatch.setattr(DisabledCommandsProfile, "resolve_command_id", fake_resolve_command_id)
    monkeypatch.setattr(DisabledCommandsProfile, "remove", fake_remove)

    result = await mythic_commands._blocklist_remove(
        _Args(name="no-exec", command="shell", payload_type=None, force=True))

    assert not prompted
    assert removed == [("no-exec", 9)]
    assert "shell" in result.plain
    assert result.style == "green"


async def test_blocklist_unassign_prompts_and_cancels_without_mutation(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return False

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_query_by_username(session, username):
        calls.append(username)
        return {"id": 2, "username": username}

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)

    result = await mythic_commands._blocklist_unassign(_Args(name="no-exec", operator=["bob"], force=False))

    assert calls == []
    assert result.plain == "Cancelled"
    assert result.style == "yellow"


async def test_blocklist_unassign_force_skips_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_username(session, username):
        return {"id": 2, "username": username}

    calls = []

    async def fake_unassign(self, user_id):
        calls.append(user_id)

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)
    monkeypatch.setattr(DisabledCommandsProfile, "unassign", fake_unassign)

    result = await mythic_commands._blocklist_unassign(_Args(name="no-exec", operator=["bob"], force=True))

    assert not prompted
    assert calls == [2]
    assert "bob" in result.plain
    assert result.style == "green"


async def test_blocklist_delete_prompts_and_cancels_without_mutation(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return False

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_delete(self, name):
        calls.append(name)

    monkeypatch.setattr(DisabledCommandsProfile, "delete", fake_delete)

    result = await mythic_commands._blocklist_delete(_Args(name="no-exec", force=False))

    assert calls == []
    assert result.plain == "Cancelled"
    assert result.style == "yellow"


async def test_blocklist_delete_force_skips_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_delete(self, name):
        calls.append(name)

    monkeypatch.setattr(DisabledCommandsProfile, "delete", fake_delete)

    result = await mythic_commands._blocklist_delete(_Args(name="no-exec", force=True))

    assert not prompted
    assert calls == ["no-exec"]
    assert result.style == "green"


async def test_blocklist_assign_does_not_prompt_even_with_force_flag(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_username(session, username):
        return {"id": 2, "username": username}

    calls = []

    async def fake_assign(self, name, user_id):
        calls.append((name, user_id))

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)
    monkeypatch.setattr(DisabledCommandsProfile, "assign", fake_assign)

    result = await mythic_commands._blocklist_assign(_Args(name="no-exec", operator=["bob"], force=False))

    assert not prompted
    assert calls == [("no-exec", 2)]
    assert result.style == "green"


async def test_blocklist_list_without_operation_returns_clean_error(fake_instance):
    fake_instance.mythic = types.SimpleNamespace(username="alice", current_operation_id=0)
    mythic_commands = MythicCommands(fake_instance)

    result = await mythic_commands._blocklist_list(_Args())

    assert result.plain.startswith("Error:")
    assert result.style == "red"


async def test_blocklist_list_builds_table_and_caches_names(mythic_commands, monkeypatch):
    async def fake_list_for_operation(session, operation_id):
        return [
            {"id": 1, "name": "no-exec", "command_id": 5,
             "command": {"id": 5, "cmd": "shell", "payloadtype": {"name": "poseidon"}},
             "operatoroperations": [{"id": 1, "operator": {"id": 2, "username": "bob"}}]},
            {"id": 2, "name": "no-exec", "command_id": 6,
             "command": {"id": 6, "cmd": "download", "payloadtype": {"name": "poseidon"}},
             "operatoroperations": []},
        ]

    monkeypatch.setattr(DisabledCommandsProfileQueries, "list_for_operation", fake_list_for_operation)

    async def fake_get_all_profile_names(session, operation_id):
        return ["no-exec"]

    monkeypatch.setattr(DisabledCommandsProfileQueries, "get_all_profile_names", fake_get_all_profile_names)

    result = await mythic_commands._blocklist_list(_Args())
    rendered = _render(result)

    assert "no-exec" in rendered
    assert "2" in rendered
    assert "bob" in rendered
    assert mythic_commands._blocklist_cache == ["no-exec"]


async def test_blocklist_name_completion(mythic_commands):
    mythic_commands._blocklist_cache = ["no-exec", "no-download"]

    assert {"no-exec", "no-download"} <= completer_values(
        mythic_commands.get_completer_items("operation blocklist show "))
    assert {"no-exec", "no-download"} <= completer_values(
        mythic_commands.get_completer_items("operation blocklist delete "))


async def test_blocklist_operator_completion_reuses_user_cache(mythic_commands):
    mythic_commands._user_cache = ["alice", "bob"]

    assert {"alice", "bob"} <= completer_values(
        mythic_commands.get_completer_items("operation blocklist assign no-exec "))
    assert {"alice", "bob"} <= completer_values(
        mythic_commands.get_completer_items("operation blocklist unassign no-exec "))


async def test_blocklist_operator_completion_per_token_with_nargs(mythic_commands):
    mythic_commands._user_cache = ["alice", "bob"]

    assert {"alice", "bob"} <= completer_values(
        mythic_commands.get_completer_items("operation blocklist assign no-exec alice "))


# ---- part 1: --payload-type completion for blocklist/whitelist ----


async def test_blocklist_and_whitelist_payload_type_completion(mythic_commands):
    mythic_commands._payload_type_cache = ["poseidon", "apfell"]

    for cmdline in (
        "operation blocklist create no-exec shell --payload-type ",
        "operation blocklist add no-exec shell --payload-type ",
        "operation blocklist remove no-exec shell --payload-type ",
        "operation whitelist create allow-basic ls --payload-type ",
        "operation whitelist add allow-basic ls --payload-type ",
        "operation whitelist remove allow-basic ls --payload-type ",
    ):
        assert {"poseidon", "apfell"} <= completer_values(mythic_commands.get_completer_items(cmdline))


# ---- part 2/3: whitelist parser group ----


def test_whitelist_help_states_snapshot_limitation():
    from mythic_console.backend.mythic_agent import mythic_command_parsers as p

    assert "point-in-time" in p.operation_whitelist_parser.format_help()
    assert "point-in-time" in p.operation_whitelist_create_parser.format_help()


def test_whitelist_shares_blocklist_handlers_for_list_show_assign_unassign_delete():
    from mythic_console.backend.mythic_agent import mythic_command_parsers as p

    pairs = [
        (p.operation_whitelist_list_parser, MythicCommands._blocklist_list),
        (p.operation_whitelist_show_parser, MythicCommands._blocklist_show),
        (p.operation_whitelist_assign_parser, MythicCommands._blocklist_assign),
        (p.operation_whitelist_unassign_parser, MythicCommands._blocklist_unassign),
        (p.operation_whitelist_delete_parser, MythicCommands._blocklist_delete),
    ]
    for parser, handler in pairs:
        assert parser.get_default("func") is handler


async def test_whitelist_name_completion(mythic_commands):
    mythic_commands._blocklist_cache = ["allow-basic"]

    assert {"allow-basic"} <= completer_values(
        mythic_commands.get_completer_items("operation whitelist show "))


async def test_whitelist_command_completion_reuses_blocklist_command_cache(mythic_commands):
    mythic_commands._blocklist_command_cache = ["ls", "shell"]

    assert {"ls", "shell"} <= completer_values(
        mythic_commands.get_completer_items("operation whitelist create allow-basic "))


# ---- part 4: complement computation ----


async def test_complement_command_ids_scoped_to_payload_type(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_get_all_commands_for_payloadtype(session, payload_type_name, custom_return_attributes=None):
        assert payload_type_name == "poseidon"
        return [{"id": 10, "cmd": "ls"}, {"id": 11, "cmd": "pwd"}, {"id": 12, "cmd": "shell"}]

    import mythic_console.backend.disabled_commands_profile.disabled_commands_profile as dcp_module
    monkeypatch.setattr(dcp_module.mythic_lib, "get_all_commands_for_payloadtype",
                         fake_get_all_commands_for_payloadtype)

    blocked_ids, unknown = await profile.complement_command_ids(["ls"], payload_type="poseidon")

    assert sorted(blocked_ids) == [11, 12]
    assert unknown == []


async def test_complement_command_ids_all_types_excludes_shared_name_and_skips_deleted(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_query_all_payload_types(session):
        return [
            {"id": 1, "name": "poseidon", "deleted": False},
            {"id": 2, "name": "apfell", "deleted": False},
            {"id": 3, "name": "retired", "deleted": True},
        ]

    async def fake_get_all_commands_for_payloadtype(session, payload_type_name, custom_return_attributes=None):
        if payload_type_name == "poseidon":
            return [{"id": 10, "cmd": "ls"}, {"id": 11, "cmd": "shell"}]
        if payload_type_name == "apfell":
            return [{"id": 20, "cmd": "ls"}, {"id": 21, "cmd": "download"}]
        raise AssertionError(f"should not query deleted payload type '{payload_type_name}'")

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)
    import mythic_console.backend.disabled_commands_profile.disabled_commands_profile as dcp_module
    monkeypatch.setattr(dcp_module.mythic_lib, "get_all_commands_for_payloadtype",
                         fake_get_all_commands_for_payloadtype)

    blocked_ids, unknown = await profile.complement_command_ids(["ls"])

    assert sorted(blocked_ids) == [11, 21]
    assert unknown == []


async def test_complement_command_ids_reports_unknown_allowed_name(monkeypatch):
    profile = DisabledCommandsProfile(types.SimpleNamespace(mythic=None), operation_id=7)

    async def fake_get_all_commands_for_payloadtype(session, payload_type_name, custom_return_attributes=None):
        return [{"id": 10, "cmd": "ls"}]

    import mythic_console.backend.disabled_commands_profile.disabled_commands_profile as dcp_module
    monkeypatch.setattr(dcp_module.mythic_lib, "get_all_commands_for_payloadtype",
                         fake_get_all_commands_for_payloadtype)

    blocked_ids, unknown = await profile.complement_command_ids(["ls", "ghost"], payload_type="poseidon")

    assert blocked_ids == []
    assert unknown == ["ghost"]


# ---- part 4: whitelist handlers ----


async def test_whitelist_create_creates_complement_and_caches(mythic_commands, monkeypatch):
    calls = {}

    async def fake_complement_command_ids(self, allowed, payload_type=None):
        calls["allowed"] = allowed
        calls["payload_type"] = payload_type
        return [5, 6], []

    created = []

    async def fake_create(self, name, command_ids):
        created.append((name, command_ids))

    cached = []

    async def fake_cache_blocklists(self):
        cached.append(True)

    monkeypatch.setattr(DisabledCommandsProfile, "complement_command_ids", fake_complement_command_ids)
    monkeypatch.setattr(DisabledCommandsProfile, "create", fake_create)
    monkeypatch.setattr(MythicCommands, "cache_blocklists", fake_cache_blocklists)

    result = await mythic_commands._whitelist_create(
        _Args(name="allow-basic", command=["ls", "pwd"], payload_type=None))

    assert calls == {"allowed": ["ls", "pwd"], "payload_type": None}
    assert created == [("allow-basic", [5, 6])]
    assert cached == [True]
    assert result.style == "green"


async def test_whitelist_create_rejects_unknown_command_without_creating(mythic_commands, monkeypatch):
    async def fake_complement_command_ids(self, allowed, payload_type=None):
        return [5, 6], ["ghost"]

    created = []

    async def fake_create(self, name, command_ids):
        created.append((name, command_ids))

    monkeypatch.setattr(DisabledCommandsProfile, "complement_command_ids", fake_complement_command_ids)
    monkeypatch.setattr(DisabledCommandsProfile, "create", fake_create)

    result = await mythic_commands._whitelist_create(
        _Args(name="allow-basic", command=["ghost"], payload_type=None))

    assert created == []
    assert "ghost" in result.plain
    assert result.style == "red"


async def test_whitelist_add_allows_via_remove_with_no_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_resolve_command_id(self, cmd_name, payload_type=None):
        return 9

    removed = []

    async def fake_remove(self, name, command_id):
        removed.append((name, command_id))

    monkeypatch.setattr(DisabledCommandsProfile, "resolve_command_id", fake_resolve_command_id)
    monkeypatch.setattr(DisabledCommandsProfile, "remove", fake_remove)

    result = await mythic_commands._whitelist_add(
        _Args(name="allow-basic", command="shell", payload_type=None))

    assert not prompted
    assert removed == [("allow-basic", 9)]
    assert result.style == "green"


async def test_whitelist_remove_prompts_and_cancels_without_mutation(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return False

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_resolve_command_id(self, cmd_name, payload_type=None):
        calls.append("resolved")
        return 9

    async def fake_add(self, name, command_id):
        calls.append("added")

    monkeypatch.setattr(DisabledCommandsProfile, "resolve_command_id", fake_resolve_command_id)
    monkeypatch.setattr(DisabledCommandsProfile, "add", fake_add)

    result = await mythic_commands._whitelist_remove(
        _Args(name="allow-basic", command="shell", payload_type=None, force=False))

    assert calls == []
    assert result.plain == "Cancelled"
    assert result.style == "yellow"


async def test_whitelist_remove_force_skips_prompt_and_adds_to_blocklist(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_resolve_command_id(self, cmd_name, payload_type=None):
        return 9

    added = []

    async def fake_add(self, name, command_id):
        added.append((name, command_id))

    monkeypatch.setattr(DisabledCommandsProfile, "resolve_command_id", fake_resolve_command_id)
    monkeypatch.setattr(DisabledCommandsProfile, "add", fake_add)

    result = await mythic_commands._whitelist_remove(
        _Args(name="allow-basic", command="shell", payload_type=None, force=True))

    assert not prompted
    assert added == [("allow-basic", 9)]
    assert result.style == "green"


# ---- part 5: multi-operator assign / unassign ----


def test_blocklist_assign_unassign_parsers_accept_multiple_operators():
    from mythic_console.backend.mythic_agent import mythic_command_parsers as p

    args = p.operation_blocklist_assign_parser.parse_args(["no-exec", "alice", "bob", "carol"])
    assert args.operator == ["alice", "bob", "carol"]

    args = p.operation_blocklist_unassign_parser.parse_args(["no-exec", "alice", "bob", "carol"])
    assert args.operator == ["alice", "bob", "carol"]


def test_whitelist_assign_unassign_parsers_accept_multiple_operators():
    from mythic_console.backend.mythic_agent import mythic_command_parsers as p

    args = p.operation_whitelist_assign_parser.parse_args(["allow-basic", "alice", "bob"])
    assert args.operator == ["alice", "bob"]
    assert args.func is MythicCommands._blocklist_assign

    args = p.operation_whitelist_unassign_parser.parse_args(["allow-basic", "alice", "bob"])
    assert args.operator == ["alice", "bob"]
    assert args.func is MythicCommands._blocklist_unassign


async def test_blocklist_assign_multi_operator_all_succeed(mythic_commands, monkeypatch):
    ids = {"alice": 1, "bob": 2, "carol": 3}

    async def fake_query_by_username(session, username):
        return {"id": ids[username], "username": username}

    calls = []

    async def fake_assign(self, name, user_id):
        calls.append((name, user_id))

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)
    monkeypatch.setattr(DisabledCommandsProfile, "assign", fake_assign)

    result = await mythic_commands._blocklist_assign(
        _Args(name="no-exec", operator=["alice", "bob", "carol"], force=False))

    assert calls == [("no-exec", 1), ("no-exec", 2), ("no-exec", 3)]
    assert result.style == "green"
    for username in ("alice", "bob", "carol"):
        assert username in result.plain


async def test_blocklist_assign_multi_operator_partial_failure_is_warning(mythic_commands, monkeypatch):
    async def fake_query_by_username(session, username):
        if username == "ghost":
            return {"username": username}
        return {"id": 1, "username": username}

    calls = []

    async def fake_assign(self, name, user_id):
        calls.append((name, user_id))

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)
    monkeypatch.setattr(DisabledCommandsProfile, "assign", fake_assign)

    result = await mythic_commands._blocklist_assign(
        _Args(name="no-exec", operator=["alice", "ghost"], force=False))

    assert calls == [("no-exec", 1)]
    assert result.style == "yellow"
    assert "alice" in result.plain
    assert "ghost" in result.plain


async def test_blocklist_unassign_multi_operator_prompts_once_naming_all(mythic_commands, monkeypatch):
    prompts = []

    async def fake_prompt(screen):
        prompts.append(screen.question)
        return False

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_query_by_username(session, username):
        calls.append(username)
        return {"id": 1, "username": username}

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)

    result = await mythic_commands._blocklist_unassign(
        _Args(name="no-exec", operator=["alice", "bob"], force=False))

    assert len(prompts) == 1
    assert "alice" in prompts[0]
    assert "bob" in prompts[0]
    assert calls == []
    assert result.plain == "Cancelled"
    assert result.style == "yellow"


async def test_blocklist_unassign_multi_operator_force_skips_prompt_and_unassigns_each(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    ids = {"alice": 1, "bob": 2}

    async def fake_query_by_username(session, username):
        return {"id": ids[username], "username": username}

    calls = []

    async def fake_unassign(self, user_id):
        calls.append(user_id)

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)
    monkeypatch.setattr(DisabledCommandsProfile, "unassign", fake_unassign)

    result = await mythic_commands._blocklist_unassign(
        _Args(name="no-exec", operator=["alice", "bob"], force=True))

    assert not prompted
    assert calls == [1, 2]
    assert result.style == "green"


async def test_blocklist_unassign_multi_operator_partial_failure_is_warning(mythic_commands, monkeypatch):
    async def fake_query_by_username(session, username):
        if username == "ghost":
            return {"username": username}
        return {"id": 1, "username": username}

    calls = []

    async def fake_unassign(self, user_id):
        calls.append(user_id)

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)
    monkeypatch.setattr(DisabledCommandsProfile, "unassign", fake_unassign)

    result = await mythic_commands._blocklist_unassign(
        _Args(name="no-exec", operator=["alice", "ghost"], force=True))

    assert calls == [1]
    assert result.style == "yellow"
    assert "alice" in result.plain
    assert "ghost" in result.plain
