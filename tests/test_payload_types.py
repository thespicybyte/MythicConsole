import types

import pytest
from textual.app import App

from mythic_console.backend.mythic_agent import mythic_agent
from mythic_console.backend.mythic_agent.mythic_agent import MythicCommands, _theme_key_and_status_styles
from mythic_console.backend.mythic_agent.mythic_command_parsers import payload_types_parser
from mythic_console.backend.payload_type.queries import PayloadTypeQueries


def test_payload_types_parser_func_is_wired():
    args = payload_types_parser.parse_args([])
    assert args.func is mythic_agent.MythicCommands._payload_types


def test_theme_key_and_status_styles_falls_back_without_running_app():
    assert _theme_key_and_status_styles() == ("bold cyan", "green", "red")


async def test_theme_key_and_status_styles_tracks_running_app_theme():
    app = App()
    async with app.run_test():
        app.theme = "nord"
        theme = app.current_theme
        assert _theme_key_and_status_styles() == (f"bold {theme.primary}", theme.success, theme.error)


@pytest.fixture
def payload_commands():
    return MythicCommands(types.SimpleNamespace(mythic=types.SimpleNamespace(current_operation_id=1)))


async def test_payload_types_renders_one_card_per_type(payload_commands, monkeypatch):
    async def fake_query_all_payload_types(_session):
        return [
            {"name": "poseidon", "agent_type": "agent", "supported_os": ["Linux", "macOS"],
             "deleted": False, "container_running": True, "note": "A Golang agent."},
            {"name": "arachne", "agent_type": "agent", "supported_os": ["Windows"],
             "deleted": False, "container_running": False, "note": ""},
        ]

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)

    group = await payload_commands._payload_types(None)

    assert [card.title for card in group.renderables] == ["poseidon", "arachne"]

    poseidon_body = group.renderables[0].renderable.plain
    assert "agent type: agent" in poseidon_body
    assert "supported OS: Linux, macOS" in poseidon_body
    assert "container running: yes" in poseidon_body
    assert "A Golang agent." in poseidon_body

    arachne_body = group.renderables[1].renderable.plain
    assert "container running: no" in arachne_body


async def test_payload_types_skips_deleted(payload_commands, monkeypatch):
    async def fake_query_all_payload_types(_session):
        return [
            {"name": "poseidon", "agent_type": "agent", "supported_os": ["Linux"],
             "deleted": False, "container_running": True, "note": ""},
            {"name": "retired", "agent_type": "agent", "supported_os": ["Linux"],
             "deleted": True, "container_running": False, "note": ""},
        ]

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)

    group = await payload_commands._payload_types(None)

    assert len(group.renderables) == 1
    assert group.renderables[0].title == "poseidon"


async def test_payload_types_handles_missing_supported_os_and_note(payload_commands, monkeypatch):
    async def fake_query_all_payload_types(_session):
        return [{"name": "poseidon", "agent_type": "agent", "supported_os": [],
                  "deleted": False, "container_running": True, "note": None}]

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)

    group = await payload_commands._payload_types(None)

    body = group.renderables[0].renderable.plain
    assert "supported OS: " in body


async def test_payload_types_no_types_returns_message(payload_commands, monkeypatch):
    async def fake_query_all_payload_types(_session):
        return []

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)

    resp = await payload_commands._payload_types(None)

    assert resp == "No payload types found"


async def test_payload_types_error_returns_error_string(payload_commands, monkeypatch):
    async def fake_query_all_payload_types(_session):
        raise Exception("network error")

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)

    resp = await payload_commands._payload_types(None)

    assert resp.plain == "Error: network error"
    assert resp.style == "red"
