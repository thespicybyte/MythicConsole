import pytest

from mythic_console.backend.mythic_agent.mythic_agent import MythicCommands
from mythic_console.backend.c2_profile.queries import C2ProfileQueries


@pytest.fixture
def mythic_commands(fake_instance):
    return MythicCommands(fake_instance)


def test_completer_lists_profiles_subcommand(mythic_commands):
    items = mythic_commands.get_completer_items("profiles x")
    assert "list" in items


def test_completer_profiles_list_options(mythic_commands):
    items = mythic_commands.get_completer_items("profiles list x")
    assert set(items) == {"-h", "--help"}


async def test_profiles_list_renders_one_card_per_profile(mythic_commands, monkeypatch):
    profiles = [
        {"name": "websocket", "container_running": True, "running": True,
         "description": "websocket profile", "is_p2p": False},
        {"name": "webshell", "container_running": True, "running": False,
         "description": "webshell profile", "is_p2p": True},
        {"name": "zzz_minimal"},
    ]

    async def fake_query_all_c2_profiles(session):
        return profiles

    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)

    group = await mythic_commands._profiles_list(None)

    assert [card.title for card in group.renderables] == ["webshell", "websocket", "zzz_minimal"]

    webshell_body = group.renderables[0].renderable.plain
    assert "container running: yes" in webshell_body
    assert "server running:" not in webshell_body
    assert "p2p: yes" in webshell_body
    assert "webshell profile" in webshell_body

    websocket_body = group.renderables[1].renderable.plain
    assert "container running: yes" in websocket_body
    assert "server running: yes" in websocket_body
    assert "p2p: no" in websocket_body
    assert "websocket profile" in websocket_body

    minimal_body = group.renderables[2].renderable.plain
    assert "container running: no" in minimal_body
    assert "server running: no" in minimal_body
    assert "p2p: no" in minimal_body


async def test_profiles_list_no_profiles_returns_message(mythic_commands, monkeypatch):
    async def fake_query_all_c2_profiles(session):
        return []

    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)

    result = await mythic_commands._profiles_list(None)

    assert result == "No c2 profiles found"


async def test_profiles_list_handles_errors(mythic_commands, monkeypatch):
    async def fake_query_all_c2_profiles(session):
        raise RuntimeError("boom")

    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)

    result = await mythic_commands._profiles_list(None)

    assert result == "Error: boom"
