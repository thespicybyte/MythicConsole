import types
from io import StringIO

import pytest
from rich.console import Console

from mythic_console.backend.mythic_agent import mythic_agent
from mythic_console.backend.mythic_agent import mythic_command_parsers
from mythic_console.backend.mythic_agent.mythic_agent import MythicCommands
from mythic_console.backend.operation import queries as operation_queries_module
from mythic_console.backend.operation.operation import Operation
from mythic_console.backend.operation.queries import OperationQueries
from mythic_console.backend.user.queries import UserQueries

from conftest import completer_values


def _render(renderable) -> str:
    console = Console(file=StringIO(), width=200)
    console.print(renderable)
    return console.file.getvalue()


@pytest.fixture
def mythic_commands(fake_instance):
    fake_instance.mythic = types.SimpleNamespace(username="alice", current_operation_id=0)
    return MythicCommands(fake_instance)


def _operation(operation_id=1, name="main", lead="alice", channel=None, webhook=None,
                complete=False, deleted=False, callbacks=None, operator_roles=None):
    return {
        "id": operation_id,
        "name": name,
        "admin_id": 1,
        "alert_count": 0,
        "channel": channel,
        "webhook": webhook,
        "complete": complete,
        "deleted": deleted,
        "callbacks": [{"agent_callback_id": c} for c in (callbacks or [])],
        "operators": [{"id": 1}],
        "admin": {"id": 1, "username": lead} if lead else None,
        "operatoroperations": operator_roles or [],
    }


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_completer_lists_operation_subcommands(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("operation x"))
    assert {"list", "info", "set", "create", "update", "operator"} <= items


def test_completer_lists_operation_operator_subcommands(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("operation operator x"))
    assert {"add", "remove", "role"} <= items


def test_completer_lists_update_toggle_flags(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("operation update op1 -"))
    assert {"--complete", "--incomplete", "--delete", "--restore", "--force"} <= items


def test_completer_lists_operator_role_choices(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("operation operator role op1 bob --role "))
    assert {"operator", "spectator"} <= items


def test_update_parser_rejects_complete_and_incomplete_together():
    with pytest.raises(SystemExit):
        mythic_command_parsers.operation_update_parser.parse_args(["op1", "--complete", "--incomplete"])


def test_update_parser_rejects_delete_and_restore_together():
    with pytest.raises(SystemExit):
        mythic_command_parsers.operation_update_parser.parse_args(["op1", "--delete", "--restore"])


def test_operation_parser_wiring_through_subcommands():
    args = mythic_command_parsers.operation_parser.parse_args(["info", "op1"])
    assert args.func is MythicCommands._operation_info

    args = mythic_command_parsers.operation_parser.parse_args(["set", "op1"])
    assert args.func is MythicCommands._operation_set

    args = mythic_command_parsers.operation_parser.parse_args(["create", "op1"])
    assert args.func is MythicCommands._operation_create

    args = mythic_command_parsers.operation_parser.parse_args(["update", "op1"])
    assert args.func is MythicCommands._operation_update

    args = mythic_command_parsers.operation_parser.parse_args(["operator", "add", "op1", "bob"])
    assert args.func is MythicCommands._operation_operator_add

    args = mythic_command_parsers.operation_parser.parse_args(["operator", "remove", "op1", "bob"])
    assert args.func is MythicCommands._operation_operator_remove

    args = mythic_command_parsers.operation_parser.parse_args(["operator", "role", "op1", "bob"])
    assert args.func is MythicCommands._operation_operator_role


async def test_operation_name_completion_at_every_depth(mythic_commands):
    mythic_commands._operation_cache = ["main", "red-team"]

    assert {"main", "red-team"} <= completer_values(mythic_commands.get_completer_items("operation info "))
    assert {"main", "red-team"} <= completer_values(mythic_commands.get_completer_items("operation set "))
    assert {"main", "red-team"} <= completer_values(mythic_commands.get_completer_items("operation update "))
    assert {"main", "red-team"} <= completer_values(
        mythic_commands.get_completer_items("operation operator add "))


async def test_username_completion_shared_with_operator_subcommands(mythic_commands):
    mythic_commands._user_cache = ["alice", "bob"]

    assert {"alice", "bob"} <= completer_values(
        mythic_commands.get_completer_items("operation operator add op1 "))
    assert {"alice", "bob"} <= completer_values(
        mythic_commands.get_completer_items("operation operator remove op1 "))
    assert {"alice", "bob"} <= completer_values(
        mythic_commands.get_completer_items("operation operator role op1 "))


async def test_operation_name_completion_shared_across_instances(fake_instance, monkeypatch):
    """Mirrors test_username_completion_shared_across_instances: a second MythicCommands
    constructed after caching must still complete from the same list, not a reassigned one."""
    async def fake_get_all_operation_names(session):
        return ["main", "red-team"]

    monkeypatch.setattr(OperationQueries, "get_all_operation_names", fake_get_all_operation_names)

    fake_instance.mythic = types.SimpleNamespace(username="alice", current_operation_id=0)
    first = MythicCommands(fake_instance)
    await first.cache_operations()

    second = MythicCommands(fake_instance)

    assert {"main", "red-team"} <= completer_values(first.get_completer_items("operation info "))
    assert {"main", "red-team"} <= completer_values(second.get_completer_items("operation info "))


async def test_cache_operations_populates_from_query(mythic_commands, monkeypatch):
    async def fake_get_all_operation_names(session):
        return ["main", "red-team"]

    monkeypatch.setattr(OperationQueries, "get_all_operation_names", fake_get_all_operation_names)

    await mythic_commands.cache_operations()

    assert mythic_commands._operation_cache == ["main", "red-team"]


async def test_get_all_operation_names_filters_deleted(monkeypatch):
    captured = {}

    async def fake_execute_custom_query(mythic, query, variables=None):
        captured["query"] = query
        return {"operation": [{"name": "main"}]}

    monkeypatch.setattr(operation_queries_module.mythic, "execute_custom_query", fake_execute_custom_query)

    await OperationQueries.get_all_operation_names(None)

    assert "where: {deleted: {_eq: false}}" in captured["query"]


async def test_cache_operations_swallows_errors(mythic_commands, monkeypatch):
    async def fake_get_all_operation_names(session):
        raise Exception("boom")

    monkeypatch.setattr(OperationQueries, "get_all_operation_names", fake_get_all_operation_names)

    await mythic_commands.cache_operations()

    assert mythic_commands._operation_cache == []


async def test_resolve_operation_by_id(mythic_commands, monkeypatch):
    async def fake_query_by_id(session, operation_id):
        return _operation(operation_id=operation_id, name="main")

    monkeypatch.setattr(OperationQueries, "query_by_id", fake_query_by_id)

    operation = await mythic_commands._resolve_operation("7")

    assert operation.id == 7
    assert operation.name == "main"


async def test_resolve_operation_by_name(mythic_commands, monkeypatch):
    async def fake_query_by_name(session, name):
        return _operation(operation_id=3, name=name)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)

    operation = await mythic_commands._resolve_operation("red-team")

    assert operation.id == 3
    assert operation.name == "red-team"


async def test_resolve_operation_not_found_raises(mythic_commands, monkeypatch):
    async def fake_query_by_name(session, name):
        raise Exception(f"failed to query operation: {name}")

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)

    with pytest.raises(Exception):
        await mythic_commands._resolve_operation("ghost")


async def test_operation_list_refreshes_operation_cache(mythic_commands, monkeypatch):
    async def fake_get_all_operations(session, include_deleted=False):
        return [1]

    async def fake_query_by_id(session, operation_id):
        return _operation(operation_id=operation_id, name="main")

    async def fake_get_all_operation_names(session):
        return ["main"]

    monkeypatch.setattr(OperationQueries, "get_all_operations", fake_get_all_operations)
    monkeypatch.setattr(OperationQueries, "query_by_id", fake_query_by_id)
    monkeypatch.setattr(OperationQueries, "get_all_operation_names", fake_get_all_operation_names)

    mythic_commands._operation_cache[:] = ["stale"]

    await mythic_commands._operation_list(_Args())

    assert mythic_commands._operation_cache == ["main"]


async def test_operation_list_default_excludes_deleted_and_columns(mythic_commands, monkeypatch):
    captured = {}

    async def fake_get_all_operations(session, include_deleted=False):
        captured["include_deleted"] = include_deleted
        return [1]

    async def fake_query_by_id(session, operation_id):
        return _operation(operation_id=operation_id, name="main", deleted=False)

    async def fake_get_all_operation_names(session):
        return ["main"]

    monkeypatch.setattr(OperationQueries, "get_all_operations", fake_get_all_operations)
    monkeypatch.setattr(OperationQueries, "query_by_id", fake_query_by_id)
    monkeypatch.setattr(OperationQueries, "get_all_operation_names", fake_get_all_operation_names)

    result = await mythic_commands._operation_list(_Args(verbose=False))

    assert captured["include_deleted"] is False
    rendered = _render(result)
    assert "deleted" not in rendered
    assert "operators" not in rendered
    assert "lead" not in rendered
    assert "main" in rendered


async def test_operation_list_verbose_includes_deleted_and_columns(mythic_commands, monkeypatch):
    captured = {}

    async def fake_get_all_operations(session, include_deleted=False):
        captured["include_deleted"] = include_deleted
        return [1, 2]

    async def fake_query_by_id(session, operation_id):
        if operation_id == 1:
            return _operation(operation_id=1, name="main", lead="alice", channel="chan",
                              webhook="hook", complete=True, deleted=False)
        return _operation(operation_id=2, name="archived", lead="bob", deleted=True)

    async def fake_get_all_operation_names(session):
        return ["main"]

    monkeypatch.setattr(OperationQueries, "get_all_operations", fake_get_all_operations)
    monkeypatch.setattr(OperationQueries, "query_by_id", fake_query_by_id)
    monkeypatch.setattr(OperationQueries, "get_all_operation_names", fake_get_all_operation_names)

    result = await mythic_commands._operation_list(_Args(verbose=True))

    assert captured["include_deleted"] is True
    rendered = _render(result)
    for header in ("lead", "operators", "complete", "channel", "webhook", "alert count", "deleted"):
        assert header in rendered
    assert "archived" in rendered


async def test_operation_list_highlights_active_operation(mythic_commands, monkeypatch):
    async def fake_get_all_operations(session, include_deleted=False):
        return [1, 2]

    async def fake_query_by_id(session, operation_id):
        return _operation(operation_id=operation_id, name=f"op{operation_id}")

    async def fake_get_all_operation_names(session):
        return ["op1", "op2"]

    monkeypatch.setattr(OperationQueries, "get_all_operations", fake_get_all_operations)
    monkeypatch.setattr(OperationQueries, "query_by_id", fake_query_by_id)
    monkeypatch.setattr(OperationQueries, "get_all_operation_names", fake_get_all_operation_names)

    mythic_commands.instance.mythic.current_operation_id = 2

    result = await mythic_commands._operation_list(_Args(verbose=False))

    assert result.rows[0].style is None
    assert result.rows[1].style is not None


async def test_get_all_operations_filters_deleted_by_default(monkeypatch):
    captured = {}

    async def fake_execute_custom_query(mythic, query, variables=None):
        captured["query"] = query
        return {"operation": [{"id": 1}]}

    monkeypatch.setattr(operation_queries_module.mythic, "execute_custom_query", fake_execute_custom_query)

    await OperationQueries.get_all_operations(None)

    assert "where: {deleted: {_eq: false}}" in captured["query"]


async def test_get_all_operations_include_deleted_skips_filter(monkeypatch):
    captured = {}

    async def fake_execute_custom_query(mythic, query, variables=None):
        captured["query"] = query
        return {"operation": [{"id": 1}]}

    monkeypatch.setattr(operation_queries_module.mythic, "execute_custom_query", fake_execute_custom_query)

    await OperationQueries.get_all_operations(None, include_deleted=True)

    assert "deleted" not in captured["query"]


async def test_operation_info_by_name(mythic_commands, monkeypatch):
    async def fake_query_by_name(session, name):
        return _operation(
            operation_id=5, name=name, lead="alice", channel="chan", webhook="hook",
            callbacks=["a", "b"],
            operator_roles=[{"view_mode": "operator", "operator": {"id": 1, "username": "alice"}}],
        )

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)

    result = await mythic_commands._operation_info(_Args(operation="main"))

    rendered = _render(result)
    assert "main" in rendered
    assert "alice" in rendered
    assert "chan" in rendered
    assert "hook" in rendered
    assert "2" in rendered


async def test_operation_info_not_found_returns_clean_error(mythic_commands, monkeypatch):
    async def fake_query_by_name(session, name):
        raise Exception(f"failed to query operation: {name}")

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)

    result = await mythic_commands._operation_info(_Args(operation="ghost"))

    assert result.plain.startswith("Error:")
    assert result.style == "red"


async def test_operation_set_does_not_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=9, name=name)

    calls = []

    async def fake_select(self, operator_id):
        calls.append(operator_id)

    async def fake_query_by_username(session, username):
        return {"id": 42, "username": username}

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "select", fake_select)
    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)

    result = await mythic_commands._operation_set(_Args(operation="main"))

    assert not prompted
    assert calls == [42]
    assert mythic_commands.instance.mythic.current_operation_id == 9
    assert "main" in result.plain


async def test_operation_create_does_not_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_create(self):
        self.id = 11

    monkeypatch.setattr(Operation, "create", fake_create)

    result = await mythic_commands._operation_create(_Args(name="new-op", lead=None))

    assert not prompted
    assert "new-op" in result.plain


async def test_operation_create_with_lead_calls_update(mythic_commands, monkeypatch):
    async def fake_create(self):
        self.id = 11

    calls = []

    async def fake_update(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(Operation, "create", fake_create)
    monkeypatch.setattr(Operation, "update", fake_update)

    await mythic_commands._operation_create(_Args(name="new-op", lead="bob"))

    assert calls == [{"lead_operator_username": "bob"}]


async def test_operation_create_refreshes_operation_cache(mythic_commands, monkeypatch):
    async def fake_create(self):
        self.id = 11

    async def fake_get_all_operation_names(session):
        return ["main", "new-op"]

    monkeypatch.setattr(Operation, "create", fake_create)
    monkeypatch.setattr(OperationQueries, "get_all_operation_names", fake_get_all_operation_names)

    mythic_commands._operation_cache[:] = ["stale"]

    await mythic_commands._operation_create(_Args(name="new-op", lead=None))

    assert mythic_commands._operation_cache == ["main", "new-op"]


async def test_operation_update_rename_does_not_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_update(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "update", fake_update)

    result = await mythic_commands._operation_update(_Args(
        operation="main", name="renamed", channel=None, webhook=None, lead=None,
        complete=False, incomplete=False, delete=False, restore=False, force=False,
    ))

    assert not prompted
    assert calls == [{
        "lead_operator_username": None, "new_operation_name": "renamed",
        "channel": None, "webhook": None, "complete": None, "deleted": None,
    }]
    assert "main" in result.plain


async def test_operation_update_refreshes_operation_cache(mythic_commands, monkeypatch):
    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    async def fake_update(self, **kwargs):
        pass

    async def fake_get_all_operation_names(session):
        return ["renamed"]

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "update", fake_update)
    monkeypatch.setattr(OperationQueries, "get_all_operation_names", fake_get_all_operation_names)

    mythic_commands._operation_cache[:] = ["stale"]

    await mythic_commands._operation_update(_Args(
        operation="main", name="renamed", channel=None, webhook=None, lead=None,
        complete=False, incomplete=False, delete=False, restore=False, force=False,
    ))

    assert mythic_commands._operation_cache == ["renamed"]


async def test_operation_update_restore_does_not_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_update(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "update", fake_update)

    await mythic_commands._operation_update(_Args(
        operation="main", name=None, channel=None, webhook=None, lead=None,
        complete=False, incomplete=False, delete=False, restore=True, force=False,
    ))

    assert not prompted
    assert calls[0]["deleted"] is False


async def test_operation_update_incomplete_does_not_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_update(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "update", fake_update)

    await mythic_commands._operation_update(_Args(
        operation="main", name=None, channel=None, webhook=None, lead=None,
        complete=False, incomplete=True, delete=False, restore=False, force=False,
    ))

    assert not prompted
    assert calls[0]["complete"] is False


async def test_operation_update_delete_prompts_and_confirms(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_update(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "update", fake_update)

    result = await mythic_commands._operation_update(_Args(
        operation="main", name=None, channel=None, webhook=None, lead=None,
        complete=False, incomplete=False, delete=True, restore=False, force=False,
    ))

    assert calls[0]["deleted"] is True
    assert "main" in result.plain


async def test_operation_update_complete_prompts_and_confirms(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_update(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "update", fake_update)

    await mythic_commands._operation_update(_Args(
        operation="main", name=None, channel=None, webhook=None, lead=None,
        complete=True, incomplete=False, delete=False, restore=False, force=False,
    ))

    assert calls[0]["complete"] is True


async def test_operation_update_delete_force_skips_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_update(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "update", fake_update)

    await mythic_commands._operation_update(_Args(
        operation="main", name=None, channel=None, webhook=None, lead=None,
        complete=False, incomplete=False, delete=True, restore=False, force=True,
    ))

    assert not prompted
    assert calls[0]["deleted"] is True


async def test_operation_update_delete_cancelled_skips_mutation(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return False

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_update(self, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "update", fake_update)

    result = await mythic_commands._operation_update(_Args(
        operation="main", name=None, channel=None, webhook=None, lead=None,
        complete=False, incomplete=False, delete=True, restore=False, force=False,
    ))

    assert calls == []
    assert result.plain == "Cancelled"
    assert result.style == "yellow"


async def test_operation_operator_add_does_not_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_add_operator(self, username):
        calls.append(username)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "add_operator", fake_add_operator)

    result = await mythic_commands._operation_operator_add(_Args(operation="main", username="bob"))

    assert not prompted
    assert calls == ["bob"]
    assert "bob" in result.plain


async def test_operation_operator_role_does_not_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_update_operator(self, username, role):
        calls.append((username, role))

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "update_operator", fake_update_operator)

    result = await mythic_commands._operation_operator_role(
        _Args(operation="main", username="bob", role="spectator"))

    assert not prompted
    assert calls == [("bob", "spectator")]
    assert "bob" in result.plain


async def test_operation_operator_remove_prompts_and_confirms(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_remove_operator(self, username):
        calls.append(username)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "remove_operator", fake_remove_operator)

    result = await mythic_commands._operation_operator_remove(_Args(operation="main", username="bob", force=False))

    assert calls == ["bob"]
    assert "bob" in result.plain


async def test_operation_operator_remove_force_skips_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_remove_operator(self, username):
        calls.append(username)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "remove_operator", fake_remove_operator)

    result = await mythic_commands._operation_operator_remove(_Args(operation="main", username="bob", force=True))

    assert not prompted
    assert calls == ["bob"]


async def test_operation_operator_remove_cancelled_skips_mutation(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return False

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    async def fake_query_by_name(session, name):
        return _operation(operation_id=1, name=name)

    calls = []

    async def fake_remove_operator(self, username):
        calls.append(username)

    monkeypatch.setattr(OperationQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(Operation, "remove_operator", fake_remove_operator)

    result = await mythic_commands._operation_operator_remove(_Args(operation="main", username="bob", force=False))

    assert calls == []
    assert result.plain == "Cancelled"
