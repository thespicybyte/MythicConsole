import json
import types

import pytest

from backend.mythic_agent import mythic_agent
from backend.mythic_agent.mythic_agent import (
    MythicCommands,
    _normalize_build_parameters,
    _normalize_c2_profile_parameters,
    _normalize_c2_profiles,
)
from backend.mythic_agent.mythic_command_parsers import payload_build_parser
from backend.payload.payload import Payload
from backend.payload_type.queries import PayloadTypeQueries
from backend.c2_profile.queries import C2ProfileQueries


# ----- config translation -----

def test_normalize_build_parameters_dict_to_list():
    assert _normalize_build_parameters({"mode": "default", "debug": True}) == [
        {"name": "mode", "value": "default"},
        {"name": "debug", "value": True},
    ]


def test_normalize_build_parameters_list_passes_through():
    raw = [{"name": "mode", "value": "default"}]
    assert _normalize_build_parameters(raw) is raw


def test_normalize_build_parameters_none_is_empty_list():
    assert _normalize_build_parameters(None) == []


def test_normalize_build_parameters_rejects_bad_shape():
    with pytest.raises(ValueError):
        _normalize_build_parameters("not a dict or list")


def test_normalize_c2_profile_parameters_unwraps_crypto_echo():
    raw = {
        "AESPSK": {"dec_key": "abc", "enc_key": "abc", "value": "aes256_hmac"},
        "callback_host": "ws://127.0.0.1",
    }
    assert _normalize_c2_profile_parameters(raw) == {
        "AESPSK": "aes256_hmac",
        "callback_host": "ws://127.0.0.1",
    }


def test_normalize_c2_profiles_canonical_shape():
    raw = [{"name": "http", "parameters": {"callback_port": "80"}}]
    assert _normalize_c2_profiles(raw) == [
        {"c2_profile": "http", "c2_profile_parameters": {"callback_port": "80"}},
    ]


def test_normalize_c2_profiles_raw_export_shape():
    raw = [{"c2_profile": "websocket", "c2_profile_is_p2p": False,
            "c2_profile_parameters": {"callback_port": "8081"}}]
    assert _normalize_c2_profiles(raw) == [
        {"c2_profile": "websocket", "c2_profile_parameters": {"callback_port": "8081"}},
    ]


def test_normalize_c2_profiles_missing_name_errors():
    with pytest.raises(ValueError):
        _normalize_c2_profiles([{"parameters": {}}])


def test_normalize_c2_profiles_round_trips_representative_config():
    config = {
        "payload_type": "poseidon",
        "selected_os": "Linux",
        "filename": "payload.bin",
        "build_parameters": {"mode": "default", "static": False},
        "c2_profiles": [{"name": "websocket", "parameters": {"callback_port": "8081"}}],
        "commands": ["ls", "cat"],
    }
    build_parameters = _normalize_build_parameters(config["build_parameters"])
    c2_profiles = _normalize_c2_profiles(config["c2_profiles"])

    assert {"name": "mode", "value": "default"} in build_parameters
    assert {"name": "static", "value": False} in build_parameters
    assert c2_profiles == [
        {"c2_profile": "websocket", "c2_profile_parameters": {"callback_port": "8081"}},
    ]


# ----- parser -----

def test_payload_build_parser_parses_full_args():
    args = payload_build_parser.parse_args(["poseidon", "--config", "x.json", "-o", "out.bin"])
    assert args.payload_type == "poseidon"
    assert args.config == "x.json"
    assert args.output == "out.bin"


def test_payload_build_parser_background_flag_present():
    args = payload_build_parser.parse_args(["poseidon", "-bg"])
    assert args.background is True


def test_payload_build_parser_background_defaults_false():
    args = payload_build_parser.parse_args(["poseidon"])
    assert args.background is False


def test_payload_build_parser_func_is_wired():
    args = payload_build_parser.parse_args(["poseidon"])
    assert args.func is mythic_agent.MythicCommands._payload_build


# ----- MythicCommands._payload_build -----

@pytest.fixture
def operation_instance():
    return types.SimpleNamespace(mythic=types.SimpleNamespace(current_operation_id=1))


@pytest.fixture
def payload_commands(operation_instance):
    return MythicCommands(operation_instance)


def _args(payload_type="poseidon", config=None, output=None, background=False):
    return types.SimpleNamespace(payload_type=payload_type, config=config, output=output,
                                 background=background)


async def test_payload_build_requires_operation():
    commands = MythicCommands(types.SimpleNamespace(mythic=types.SimpleNamespace(current_operation_id=None)))
    resp = await commands._payload_build(_args())
    assert "Operation not set" in resp


async def test_payload_build_missing_config_file(payload_commands, tmp_path):
    missing = tmp_path / "missing.json"
    resp = await payload_commands._payload_build(_args(config=str(missing)))
    assert "config file not found" in resp


async def test_payload_build_missing_selected_os_errors(payload_commands, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"filename": "payload.bin"}))
    resp = await payload_commands._payload_build(_args(config=str(config_path)))
    assert "selected_os" in resp


async def test_payload_build_missing_filename_errors(payload_commands, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"selected_os": "Linux"}))
    resp = await payload_commands._payload_build(_args(config=str(config_path)))
    assert "filename" in resp


async def test_payload_build_payload_type_conflict_errors(payload_commands, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "payload_type": "arachne", "selected_os": "Linux", "filename": "payload.bin",
    }))
    resp = await payload_commands._payload_build(_args(payload_type="poseidon", config=str(config_path)))
    assert "conflicts" in resp


async def test_payload_build_background_returns_immediately_no_download(payload_commands, tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"selected_os": "Linux", "filename": "payload.bin"}))

    calls = {}

    async def fake_create_payload(*_args, **kwargs):
        calls["kwargs"] = kwargs
        return {"status": "success", "uuid": "abc-123", "error": ""}

    async def fake_download(self, path):
        calls["downloaded"] = True

    monkeypatch.setattr(mythic_agent.mythic, "create_payload", fake_create_payload)
    monkeypatch.setattr(Payload, "download", fake_download)

    resp = await payload_commands._payload_build(_args(config=str(config_path), background=True))

    assert "abc-123" in resp
    assert calls["kwargs"]["return_on_complete"] is False
    assert "downloaded" not in calls


async def test_payload_build_foreground_success_downloads(payload_commands, tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"selected_os": "Linux", "filename": "payload.bin"}))
    output_path = tmp_path / "out.bin"

    async def fake_create_payload(*_args, **kwargs):
        assert kwargs["return_on_complete"] is True
        return {"build_phase": "success", "uuid": "abc-123"}

    downloaded = {}

    async def fake_download(self, path):
        downloaded["path"] = path
        downloaded["uuid"] = self.uuid

    monkeypatch.setattr(mythic_agent.mythic, "create_payload", fake_create_payload)
    monkeypatch.setattr(Payload, "download", fake_download)

    resp = await payload_commands._payload_build(_args(config=str(config_path), output=str(output_path)))

    assert "Payload built and saved" in resp
    assert downloaded["path"] == output_path
    assert downloaded["uuid"] == "abc-123"


async def test_payload_build_foreground_failure_does_not_download(payload_commands, tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"selected_os": "Linux", "filename": "payload.bin"}))

    async def fake_create_payload(*_args, **kwargs):
        return {"build_phase": "error", "uuid": "abc-123",
                "build_message": "build failed", "build_stderr": "traceback"}

    calls = {}

    async def fake_download(self, path):
        calls["downloaded"] = True

    monkeypatch.setattr(mythic_agent.mythic, "create_payload", fake_create_payload)
    monkeypatch.setattr(Payload, "download", fake_download)

    resp = await payload_commands._payload_build(_args(config=str(config_path)))

    assert "Build failed" in resp
    assert "build failed" in resp
    assert "downloaded" not in calls


# ----- tab-completion for the <payload_type> positional -----

def test_payload_build_positional_completes_cached_payload_types(payload_commands):
    payload_commands._payload_type_cache = ["poseidon", "arachne"]
    items = payload_commands.get_completer_items("payload build ")
    assert "poseidon" in items
    assert "arachne" in items
    assert "--config" in items
    assert "-bg" in items


def test_payload_build_positional_partial_token_still_completes_payload_types(payload_commands):
    payload_commands._payload_type_cache = ["poseidon", "arachne"]
    items = payload_commands.get_completer_items("payload build pos")
    assert "poseidon" in items


def test_payload_build_flags_only_once_payload_type_present(payload_commands):
    payload_commands._payload_type_cache = ["poseidon", "arachne"]
    items = payload_commands.get_completer_items("payload build poseidon ")
    assert "poseidon" not in items
    assert "arachne" not in items
    assert "--config" in items


def test_payload_build_completion_degrades_to_flags_with_empty_cache(payload_commands):
    items = payload_commands.get_completer_items("payload build ")
    assert "--config" in items
    assert "-bg" in items


# ----- cache_payload_types -----

async def test_cache_payload_types_noop_without_operation():
    commands = MythicCommands(types.SimpleNamespace(mythic=types.SimpleNamespace(current_operation_id=None)))
    await commands.cache_payload_types()
    assert commands._payload_type_cache == []


async def test_cache_payload_types_populates_from_server(payload_commands, monkeypatch):
    async def fake_query_all_payload_types(_session):
        return [{"name": "poseidon"}, {"name": "arachne"}]

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)

    await payload_commands.cache_payload_types()

    assert payload_commands._payload_type_cache == ["poseidon", "arachne"]


async def test_cache_payload_types_degrades_safely_on_error(payload_commands, monkeypatch):
    async def fake_query_all_payload_types(_session):
        raise Exception("network error")

    monkeypatch.setattr(PayloadTypeQueries, "query_all_payload_types", fake_query_all_payload_types)

    await payload_commands.cache_payload_types()

    assert payload_commands._payload_type_cache == []


# ----- introspection queries (string-level shape) -----

async def test_query_build_parameters_shape(monkeypatch):
    captured = {}

    async def fake_execute_custom_query(mythic, query, variables=None):
        captured["query"] = query
        captured["variables"] = variables
        return {"payloadtype": [{"buildparameters": [{"name": "mode", "parameter_type": "ChooseOne"}]}]}

    import backend.payload_type.queries as payload_type_queries
    monkeypatch.setattr(payload_type_queries.mythic, "execute_custom_query", fake_execute_custom_query)

    result = await PayloadTypeQueries.query_build_parameters(None, "poseidon")

    assert result == [{"name": "mode", "parameter_type": "ChooseOne"}]
    assert captured["variables"] == {"name": "poseidon"}
    assert "buildparameters" in captured["query"]
    assert "parameter_type" in captured["query"]
    assert "choices" in captured["query"]
    assert "group_name" in captured["query"]


async def test_query_all_c2_profiles_shape(monkeypatch):
    captured = {}

    async def fake_execute_custom_query(mythic, query, variables=None):
        captured["query"] = query
        captured["variables"] = variables
        return {"c2profile": [{"name": "websocket", "is_p2p": False, "c2profileparameters": []}]}

    import backend.c2_profile.queries as c2_profile_queries
    monkeypatch.setattr(c2_profile_queries.mythic, "execute_custom_query", fake_execute_custom_query)

    result = await C2ProfileQueries.query_all_c2_profiles(None)

    assert result == [{"name": "websocket", "is_p2p": False, "c2profileparameters": []}]
    assert "c2profileparameters" in captured["query"]
    assert "parameter_type" in captured["query"]
    assert "deleted: {_eq: false}" in captured["query"]
