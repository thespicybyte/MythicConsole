from io import StringIO

import pytest
from rich.console import Console

from mythic_console.backend.mythic_agent import mythic_agent
from mythic_console.backend.mythic_agent import mythic_command_parsers
from mythic_console.backend.mythic_agent.mythic_agent import MythicCommands
from mythic_console.backend.user.queries import UserQueries
from mythic_console.backend.user.user import User

from conftest import completer_values


def _render(renderable) -> str:
    console = Console(file=StringIO(), width=200)
    console.print(renderable)
    return console.file.getvalue()


@pytest.fixture
def mythic_commands(fake_instance):
    return MythicCommands(fake_instance)


def _operator(user_id=1, username="bob", admin=False, active=True, deleted=False, operation_name="main"):
    return {
        "id": user_id,
        "username": username,
        "admin": admin,
        "creation_time": "2026-01-01T00:00:00Z",
        "last_login": "2026-01-02T00:00:00Z",
        "active": active,
        "view_utc_time": False,
        "deleted": deleted,
        "current_operation_id": 1,
        "operation": {"id": 1, "name": operation_name},
    }


def test_completer_lists_user_subcommands(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("user x"))
    assert {"list", "create", "info", "set", "delete"} <= items
    assert "admin" not in items
    assert "active" not in items


def test_completer_lists_set_fields(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("user set "))
    assert {"admin", "active"} <= items


def test_completer_lists_set_admin_value_choices(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("user set admin "))
    assert {"true", "false"} <= items


def test_completer_lists_user_list_all_flag(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("user list -"))
    assert "--all" in items


def test_completer_lists_force_flag_for_set_admin(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("user set admin false bob -"))
    assert "--force" in items


def test_completer_lists_force_flag_for_set_active(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("user set active false bob -"))
    assert "--force" in items


def test_completer_lists_force_flag_for_delete(mythic_commands):
    items = completer_values(mythic_commands.get_completer_items("user delete bob -"))
    assert "--force" in items


def test_user_set_admin_parser_arg_order():
    args = mythic_command_parsers.user_set_admin_parser.parse_args(["true", "bob"])
    assert args.value == "true"
    assert args.identifier == "bob"

    with pytest.raises(SystemExit):
        mythic_command_parsers.user_set_admin_parser.parse_args(["nope", "bob"])


def test_username_completion_at_every_identifier_depth(mythic_commands):
    mythic_commands._user_cache = ["alice", "bob"]

    assert {"alice", "bob"} <= completer_values(mythic_commands.get_completer_items("user info "))
    assert {"alice", "bob"} <= completer_values(mythic_commands.get_completer_items("user delete "))
    assert {"alice", "bob"} <= completer_values(mythic_commands.get_completer_items("user set admin true "))
    assert {"alice", "bob"} <= completer_values(mythic_commands.get_completer_items("user set active true "))


async def test_cache_users_populates_from_query(mythic_commands, monkeypatch):
    async def fake_get_all_usernames(session):
        return ["alice", "bob"]

    monkeypatch.setattr(UserQueries, "get_all_usernames", fake_get_all_usernames)

    await mythic_commands.cache_users()

    assert mythic_commands._user_cache == ["alice", "bob"]


async def test_cache_users_swallows_errors(mythic_commands, monkeypatch):
    async def fake_get_all_usernames(session):
        raise Exception("boom")

    monkeypatch.setattr(UserQueries, "get_all_usernames", fake_get_all_usernames)

    await mythic_commands.cache_users()

    assert mythic_commands._user_cache == []


async def test_username_completion_shared_across_instances(fake_instance, monkeypatch):
    """One MythicCommands is constructed per console panel (home tab + each callback tab), so a
    second instance is routinely constructed after the first has already cached usernames. The
    completer must keep returning the cached values from every instance, not just whichever one
    was constructed last."""
    async def fake_get_all_usernames(session):
        return ["alice", "bob"]

    monkeypatch.setattr(UserQueries, "get_all_usernames", fake_get_all_usernames)

    first = MythicCommands(fake_instance)
    await first.cache_users()

    second = MythicCommands(fake_instance)  # constructed after caching, e.g. a new callback tab

    assert {"alice", "bob"} <= completer_values(first.get_completer_items("user info "))
    assert {"alice", "bob"} <= completer_values(second.get_completer_items("user info "))


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


async def test_user_list_default_excludes_deleted_and_omits_deleted_column(mythic_commands, monkeypatch):
    calls = {}

    async def fake_get_all_users(session, include_deleted=False):
        calls["include_deleted"] = include_deleted
        return [1]

    async def fake_query_by_id(session, user_id):
        return _operator(user_id=user_id, username="bob", deleted=False)

    monkeypatch.setattr(UserQueries, "get_all_users", fake_get_all_users)
    monkeypatch.setattr(UserQueries, "query_by_id", fake_query_by_id)

    result = await mythic_commands._user_list(_Args(all=False))

    assert calls["include_deleted"] is False
    rendered = _render(result)
    assert "bob" in rendered
    assert "deleted" not in rendered.lower()


async def test_user_list_all_includes_deleted_user_and_column(mythic_commands, monkeypatch):
    calls = {}

    async def fake_get_all_users(session, include_deleted=False):
        calls["include_deleted"] = include_deleted
        return [1, 2]

    responses = {
        1: _operator(user_id=1, username="bob", deleted=False),
        2: _operator(user_id=2, username="eve", deleted=True),
    }

    async def fake_query_by_id(session, user_id):
        return responses[user_id]

    monkeypatch.setattr(UserQueries, "get_all_users", fake_get_all_users)
    monkeypatch.setattr(UserQueries, "query_by_id", fake_query_by_id)

    result = await mythic_commands._user_list(_Args(all=True))

    assert calls["include_deleted"] is True
    rendered = _render(result)
    assert "eve" in rendered
    assert "deleted" in rendered.lower()


async def test_user_list_refreshes_username_cache(mythic_commands, monkeypatch):
    async def fake_get_all_users(session, include_deleted=False):
        return [1]

    async def fake_query_by_id(session, user_id):
        return _operator(user_id=user_id, username="bob")

    async def fake_get_all_usernames(session):
        return ["alice", "bob"]

    monkeypatch.setattr(UserQueries, "get_all_users", fake_get_all_users)
    monkeypatch.setattr(UserQueries, "query_by_id", fake_query_by_id)
    monkeypatch.setattr(UserQueries, "get_all_usernames", fake_get_all_usernames)

    mythic_commands._user_cache[:] = ["stale"]

    await mythic_commands._user_list(_Args(all=False))

    assert mythic_commands._user_cache == ["alice", "bob"]


async def test_user_list_all_refreshes_cache_with_deleted_filtered_set(mythic_commands, monkeypatch):
    async def fake_get_all_users(session, include_deleted=False):
        return [1, 2]

    responses = {
        1: _operator(user_id=1, username="bob", deleted=False),
        2: _operator(user_id=2, username="eve", deleted=True),
    }

    async def fake_query_by_id(session, user_id):
        return responses[user_id]

    async def fake_get_all_usernames(session):
        return ["bob"]  # server-side deleted filter already drops eve

    monkeypatch.setattr(UserQueries, "get_all_users", fake_get_all_users)
    monkeypatch.setattr(UserQueries, "query_by_id", fake_query_by_id)
    monkeypatch.setattr(UserQueries, "get_all_usernames", fake_get_all_usernames)

    mythic_commands._user_cache[:] = ["stale"]

    result = await mythic_commands._user_list(_Args(all=True))

    assert mythic_commands._user_cache == ["bob"]
    assert "eve" in _render(result)  # --all still shows deleted users in the listing


async def test_user_create_returns_table(mythic_commands, monkeypatch):
    calls = []

    async def fake_create_operator(session, username, password):
        calls.append((username, password))
        return _operator(user_id=5, username=username)

    async def fake_query_by_id(session, user_id):
        return _operator(user_id=user_id, username="test2")

    monkeypatch.setattr(UserQueries, "create_operator", fake_create_operator)
    monkeypatch.setattr(UserQueries, "query_by_id", fake_query_by_id)

    result = await mythic_commands._user_create(_Args(username="test2", password="hunter2"))

    assert calls == [("test2", "hunter2")]
    assert "test2" in _render(result)


async def test_user_info_by_username(mythic_commands, monkeypatch):
    async def fake_query_by_username(session, username):
        return _operator(username=username, admin=True)

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)

    result = await mythic_commands._user_info(_Args(identifier="bob"))

    rendered = _render(result)
    assert "bob" in rendered
    assert "True" in rendered
    assert "main" in rendered


async def test_user_info_by_id(mythic_commands, monkeypatch):
    async def fake_query_by_id(session, user_id):
        return _operator(user_id=user_id, username="alice")

    monkeypatch.setattr(UserQueries, "query_by_id", fake_query_by_id)

    result = await mythic_commands._user_info(_Args(identifier="7"))

    rendered = _render(result)
    assert "alice" in rendered
    assert "7" in rendered


async def test_user_info_shows_deleted_state(mythic_commands, monkeypatch):
    async def fake_query_by_username(session, username):
        return _operator(username=username, deleted=True)

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)

    result = await mythic_commands._user_info(_Args(identifier="bob"))

    rendered = _render(result)
    assert "deleted" in rendered
    assert "True" in rendered


async def test_user_info_not_found_returns_clean_error(mythic_commands, monkeypatch):
    async def fake_query_by_username(session, username):
        raise Exception(f"failed to query user: {username}")

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)

    result = await mythic_commands._user_info(_Args(identifier="ghost"))

    assert result.startswith("Error:")


async def test_user_set_admin_true_does_not_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_set_admin_status(self, is_admin):
        calls.append(is_admin)

    async def fake_query(self):
        self.id = 1
        self.username = "bob"
        self.admin = True

    monkeypatch.setattr(User, "set_admin_status", fake_set_admin_status)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_set_admin(_Args(value="true", identifier="bob"))

    assert not prompted
    assert calls == [True]
    assert "bob" in _render(result)


async def test_user_set_admin_false_prompts_and_confirms(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_set_admin_status(self, is_admin):
        calls.append(is_admin)

    async def fake_query(self):
        self.id = 1
        self.username = "bob"
        self.admin = False

    monkeypatch.setattr(User, "set_admin_status", fake_set_admin_status)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_set_admin(_Args(value="false", identifier="bob", force=False))

    assert calls == [False]
    assert "bob" in _render(result)


async def test_user_set_admin_false_force_skips_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_set_admin_status(self, is_admin):
        calls.append(is_admin)

    async def fake_query(self):
        self.id = 1
        self.username = "bob"
        self.admin = False

    monkeypatch.setattr(User, "set_admin_status", fake_set_admin_status)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_set_admin(_Args(value="false", identifier="bob", force=True))

    assert not prompted
    assert calls == [False]
    assert "bob" in _render(result)


async def test_user_set_admin_false_cancelled_skips_mutation(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return False

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_set_admin_status(self, is_admin):
        calls.append(is_admin)

    async def fake_query(self):
        self.id = 1
        self.username = "bob"
        self.admin = False

    monkeypatch.setattr(User, "set_admin_status", fake_set_admin_status)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_set_admin(_Args(value="false", identifier="bob", force=False))

    assert calls == []
    assert result == "Cancelled"


async def test_user_set_admin_by_id(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_set_admin_status(self, is_admin):
        calls.append(is_admin)

    async def fake_query(self):
        self.id = 7
        self.username = "alice"
        self.admin = True

    monkeypatch.setattr(User, "set_admin_status", fake_set_admin_status)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_set_admin(_Args(value="true", identifier="7"))

    assert calls == [True]
    assert "alice" in _render(result)


async def test_user_set_active_true_does_not_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_set_active_status(self, is_active):
        calls.append(is_active)

    async def fake_query(self):
        self.id = 1
        self.username = "bob"
        self.active = True

    monkeypatch.setattr(User, "set_active_status", fake_set_active_status)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_set_active(_Args(value="true", identifier="bob"))

    assert not prompted
    assert calls == [True]
    assert "bob" in _render(result)


async def test_user_set_active_false_prompts_and_confirms(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_set_active_status(self, is_active):
        calls.append(is_active)

    async def fake_query(self):
        self.id = 1
        self.username = "bob"
        self.active = False

    monkeypatch.setattr(User, "set_active_status", fake_set_active_status)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_set_active(_Args(value="false", identifier="bob", force=False))

    assert calls == [False]
    assert "bob" in _render(result)


async def test_user_set_active_false_force_skips_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_set_active_status(self, is_active):
        calls.append(is_active)

    async def fake_query(self):
        self.id = 1
        self.username = "bob"
        self.active = False

    monkeypatch.setattr(User, "set_active_status", fake_set_active_status)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_set_active(_Args(value="false", identifier="bob", force=True))

    assert not prompted
    assert calls == [False]
    assert "bob" in _render(result)


async def test_user_set_active_false_cancelled_skips_mutation(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return False

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_set_active_status(self, is_active):
        calls.append(is_active)

    async def fake_query(self):
        self.id = 1
        self.username = "bob"
        self.active = True

    monkeypatch.setattr(User, "set_active_status", fake_set_active_status)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_set_active(_Args(value="false", identifier="bob", force=False))

    assert calls == []
    assert result == "Cancelled"


async def test_user_set_active_by_id(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_set_active_status(self, is_active):
        calls.append(is_active)

    async def fake_query(self):
        self.id = 7
        self.username = "alice"
        self.active = True

    monkeypatch.setattr(User, "set_active_status", fake_set_active_status)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_set_active(_Args(value="true", identifier="7"))

    assert calls == [True]
    assert "alice" in _render(result)


async def test_user_delete_prompts_and_confirms(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_delete(self):
        calls.append(self.username)

    query_calls = {"count": 0}

    async def fake_query(self):
        query_calls["count"] += 1
        self.id = 1
        self.username = "bob"
        self.active = query_calls["count"] < 2
        self.deleted = query_calls["count"] >= 2

    monkeypatch.setattr(User, "delete", fake_delete)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_delete(_Args(identifier="bob", force=False))

    assert calls == ["bob"]
    rendered = _render(result)
    assert "bob" in rendered
    assert "active" in rendered
    assert "deleted" in rendered


async def test_user_delete_force_skips_prompt(mythic_commands, monkeypatch):
    prompted = False

    async def fake_prompt(screen):
        nonlocal prompted
        prompted = True
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_delete(self):
        calls.append(self.username)

    query_calls = {"count": 0}

    async def fake_query(self):
        query_calls["count"] += 1
        self.id = 1
        self.username = "bob"
        self.active = query_calls["count"] < 2
        self.deleted = query_calls["count"] >= 2

    monkeypatch.setattr(User, "delete", fake_delete)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_delete(_Args(identifier="bob", force=True))

    assert not prompted
    assert calls == ["bob"]
    rendered = _render(result)
    assert "bob" in rendered
    assert "deleted" in rendered


async def test_user_delete_cancelled_skips_mutation(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return False

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_delete(self):
        calls.append(self.username)

    async def fake_query(self):
        self.id = 1
        self.username = "bob"

    monkeypatch.setattr(User, "delete", fake_delete)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_delete(_Args(identifier="bob", force=False))

    assert calls == []
    assert result == "Cancelled"


async def test_user_delete_by_id(mythic_commands, monkeypatch):
    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    calls = []

    async def fake_delete(self):
        calls.append(self.username)

    async def fake_query(self):
        self.id = 7
        self.username = "alice"
        self.active = False
        self.deleted = True

    monkeypatch.setattr(User, "delete", fake_delete)
    monkeypatch.setattr(User, "query", fake_query)

    result = await mythic_commands._user_delete(_Args(identifier="7", force=False))

    assert calls == ["alice"]
    assert "alice" in _render(result)


async def test_user_delete_not_found_returns_clean_error(mythic_commands, monkeypatch):
    async def fake_query(self):
        raise Exception("failed to query user: ghost")

    calls = []

    async def fake_delete(self):
        calls.append(self.username)

    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(User, "query", fake_query)
    monkeypatch.setattr(User, "delete", fake_delete)
    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    result = await mythic_commands._user_delete(_Args(identifier="ghost", force=False))

    assert result.startswith("Error:")
    assert calls == []


async def test_user_delete_renders_false_fields_through_real_update(mythic_commands, monkeypatch):
    """Regression: User._update must not use truthiness on booleans, or a server-returned
    False (active after delete) gets skipped and the stale True keeps rendering. Goes through
    the real User.query/_update, only stubbing the UserQueries/_prompt boundary."""
    responses = [
        _operator(username="bob", active=True, deleted=False),
        _operator(username="bob", active=False, deleted=True),
    ]

    async def fake_query_by_username(session, username):
        return responses.pop(0)

    async def fake_query_by_id(session, user_id):
        return responses.pop(0)

    async def fake_delete_operator(session, operator_id):
        return {"id": operator_id, "active": False, "deleted": True}

    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)
    monkeypatch.setattr(UserQueries, "query_by_id", fake_query_by_id)
    monkeypatch.setattr(UserQueries, "delete_operator", fake_delete_operator)
    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    result = await mythic_commands._user_delete(_Args(identifier="bob", force=False))

    rendered = _render(result)
    assert "False" in rendered
    assert "True" in rendered


async def test_user_set_active_false_renders_through_real_update(mythic_commands, monkeypatch):
    """Regression: same truthiness bug for 'user set active false'."""
    responses = [
        _operator(username="bob", active=True),
        _operator(username="bob", active=False),
    ]

    async def fake_query_by_username(session, username):
        return responses.pop(0)

    async def fake_query_by_id(session, user_id):
        return responses.pop(0)

    async def fake_set_active_status(session, username, is_active):
        return {}

    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)
    monkeypatch.setattr(UserQueries, "query_by_id", fake_query_by_id)
    monkeypatch.setattr(UserQueries, "set_active_status", fake_set_active_status)
    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    result = await mythic_commands._user_set_active(_Args(value="false", identifier="bob", force=False))

    rendered = _render(result)
    assert "False" in rendered


async def test_user_set_admin_false_renders_through_real_update(mythic_commands, monkeypatch):
    """Regression: same truthiness bug for 'user set admin false'."""
    responses = [
        _operator(username="bob", admin=True),
        _operator(username="bob", admin=False),
    ]

    async def fake_query_by_username(session, username):
        return responses.pop(0)

    async def fake_query_by_id(session, user_id):
        return responses.pop(0)

    async def fake_set_admin_status(session, username, is_admin):
        return {}

    async def fake_prompt(screen):
        return True

    monkeypatch.setattr(UserQueries, "query_by_username", fake_query_by_username)
    monkeypatch.setattr(UserQueries, "query_by_id", fake_query_by_id)
    monkeypatch.setattr(UserQueries, "set_admin_status", fake_set_admin_status)
    monkeypatch.setattr(mythic_agent, "_prompt", fake_prompt)

    result = await mythic_commands._user_set_admin(_Args(value="false", identifier="bob", force=False))

    rendered = _render(result)
    assert "False" in rendered
