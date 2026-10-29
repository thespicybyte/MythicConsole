import json
import types

import pytest

from backend.mythic_agent import mythic_command_parsers
from backend.mythic_agent.mythic_agent import MythicCommands
from backend.callback.callback import Callback
from backend.callback.queries import CallbackQueries


@pytest.fixture
def mythic_commands(fake_instance):
    return MythicCommands(fake_instance)


def _parser_options(parser):
    options = []
    for action in parser._actions:
        options.extend(action.option_strings)
    return options


def test_callback_export_parser_parses_id_and_optional_path():
    args = mythic_command_parsers.callback_export_parser.parse_args(["5"])
    assert args.id == 5
    assert args.path == []

    args = mythic_command_parsers.callback_export_parser.parse_args(["5", "/tmp/x.json"])
    assert args.path == ["/tmp/x.json"]


def test_callback_import_parser_parses_path():
    args = mythic_command_parsers.callback_import_parser.parse_args(["/tmp/x.json"])
    assert args.path == ["/tmp/x.json"]


def test_callback_export_and_import_parsers_omit_background_flag():
    assert "--background" not in _parser_options(mythic_command_parsers.callback_export_parser)
    assert "--background" not in _parser_options(mythic_command_parsers.callback_import_parser)

    with pytest.raises(SystemExit):
        mythic_command_parsers.callback_export_parser.parse_args(["5", "--background"])
    with pytest.raises(SystemExit):
        mythic_command_parsers.callback_import_parser.parse_args(["/tmp/x.json", "--background"])


def test_completer_lists_callback_subcommands(mythic_commands):
    items = mythic_commands.get_completer_items("callback x")
    assert "export" in items
    assert "import" in items


def test_completer_callback_export_options_omit_background(mythic_commands):
    items = mythic_commands.get_completer_items("callback export x")
    assert set(items) == {"-h", "--help"}


async def test_callback_export_default_path(mythic_commands, monkeypatch, tmp_path):
    monkeypatch.setenv("DOWNLOAD_DIRECTORY", str(tmp_path))
    recorded = {}

    async def fake_export(self, path=None):
        recorded["path"] = path

    monkeypatch.setattr(Callback, "export", fake_export)

    args = types.SimpleNamespace(id=5, path=[])
    result = await mythic_commands._callback_export(args)

    expected_path = str(tmp_path / "callback_5_export.json")
    assert result == f"[+] Callback 5 config exported to {expected_path}"
    assert recorded["path"] == expected_path


async def test_callback_export_explicit_path(mythic_commands, monkeypatch, tmp_path):
    async def fake_export(self, path=None):
        pass

    monkeypatch.setattr(Callback, "export", fake_export)

    explicit_path = str(tmp_path / "custom.json")
    args = types.SimpleNamespace(id=5, path=[explicit_path])
    result = await mythic_commands._callback_export(args)

    assert result == f"[+] Callback 5 config exported to {explicit_path}"


async def test_callback_export_handles_errors(mythic_commands, monkeypatch, tmp_path):
    async def fake_export(self, path=None):
        raise Exception("boom")

    monkeypatch.setattr(Callback, "export", fake_export)

    args = types.SimpleNamespace(id=5, path=[str(tmp_path / "x.json")])
    result = await mythic_commands._callback_export(args)

    assert result == "[-] Error: boom"


async def test_callback_import_missing_file(mythic_commands, tmp_path):
    missing_path = str(tmp_path / "missing.json")
    args = types.SimpleNamespace(path=[missing_path])

    result = await mythic_commands._callback_import(args)

    assert result == f"[-] Error: file not found: {missing_path}"


async def test_callback_import_malformed_json(mythic_commands, tmp_path):
    config_path = tmp_path / "bad.json"
    config_path.write_text("{")

    args = types.SimpleNamespace(path=[str(config_path)])
    result = await mythic_commands._callback_import(args)

    assert result.startswith(f"[-] Error: invalid config JSON in {config_path}:")


async def test_callback_import_success_does_not_requery(mythic_commands, monkeypatch, tmp_path):
    config_path = tmp_path / "good.json"
    config_path.write_text(json.dumps({"callback": {"id": 999}}))

    recorded = {}

    async def fake_import_callback(session, config):
        recorded["config"] = config

    monkeypatch.setattr(CallbackQueries, "import_callback", fake_import_callback)

    args = types.SimpleNamespace(path=[str(config_path)])
    result = await mythic_commands._callback_import(args)

    assert result == f"[+] Callback config imported from {config_path}"
    assert recorded["config"] == {"callback": {"id": 999}}


async def test_callback_import_handles_mutation_errors(mythic_commands, monkeypatch, tmp_path):
    config_path = tmp_path / "good.json"
    config_path.write_text(json.dumps({"callback": {"id": 999}}))

    async def fake_import_callback(session, config):
        raise Exception("server rejected import")

    monkeypatch.setattr(CallbackQueries, "import_callback", fake_import_callback)

    args = types.SimpleNamespace(path=[str(config_path)])
    result = await mythic_commands._callback_import(args)

    assert result == "[-] Error: server rejected import"
