import json
import types

import pytest
from textual.app import App
from textual.widgets import Checkbox, Input, Label, Select, TextArea

from backend.mythic_agent import mythic_agent
from backend.mythic_agent.mythic_agent import MythicCommands, _load_config
from backend.payload_type.queries import PayloadTypeQueries
from backend.c2_profile.queries import C2ProfileQueries
from screens.forms import FieldSpec, ParamForm
from screens.prompts import BACK, ChoicePrompt
from screens.build_summary import BuildSummary
from screens.select_commands import SelectCommands
from widgets.transfer_selection import CheckSelectionList


# ----- shared helpers -----

def _args(payload_type="poseidon", config=None, output=None, background=False):
    return types.SimpleNamespace(payload_type=payload_type, config=config, output=output,
                                 background=background)


@pytest.fixture
def operation_instance():
    return types.SimpleNamespace(mythic=types.SimpleNamespace(current_operation_id=1))


@pytest.fixture
def payload_commands(operation_instance):
    return MythicCommands(operation_instance)


def _queue_prompt(monkeypatch, queue):
    """Replace mythic_agent._prompt with a stub that asserts the call order/screen types
    against `queue` (a list of (expected_type, return_value) pairs), returns the canned value,
    and records every screen it was given (in order) for inspection."""
    captured = []

    async def _fake_prompt(screen):
        captured.append(screen)
        assert queue, f"unexpected prompt: {screen!r}"
        expected_type, value = queue.pop(0)
        assert isinstance(screen, expected_type), f"expected {expected_type}, got {type(screen)}"
        return value

    monkeypatch.setattr(mythic_agent, "_prompt", _fake_prompt)
    return queue, captured


async def _no_catalog(_session, _payload_type_name, custom_return_attributes=None):
    return []


async def _bare_questionnaire_setup(monkeypatch, *, supports_multiple=True):
    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux"]}

    async def fake_query_build_parameters(_session, _name):
        return []

    async def fake_query_supported_c2_profiles(_session, _name):
        return {"supports_multiple": supports_multiple,
                "profiles": [{"name": "websocket", "c2profileparameters": []}]}

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)
    monkeypatch.setattr(PayloadTypeQueries, "query_supported_c2_profiles", fake_query_supported_c2_profiles)
    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", _no_catalog)


# ----- config-complete bypass -----

async def test_complete_config_skips_questionnaire(payload_commands, monkeypatch):
    called = []
    monkeypatch.setattr(mythic_agent, "_prompt", lambda screen: called.append(screen))

    async def fake_create_payload(*_a, **kwargs):
        return {"build_phase": "success", "uuid": "abc-123"}

    async def fake_download(self, path):
        pass

    monkeypatch.setattr(mythic_agent.mythic, "create_payload", fake_create_payload)
    monkeypatch.setattr(mythic_agent.Payload, "download", fake_download)

    resp = await payload_commands._payload_build(
        _args(config=json.dumps({"selected_os": "Linux", "filename": "payload.bin"})))

    assert called == []
    assert "Payload built and saved" in resp


# ----- _load_config -----

def test_load_config_from_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"a": 1}))
    assert _load_config(str(path)) == {"a": 1}


def test_load_config_from_json_string():
    assert _load_config('{"a": 1}') == {"a": 1}


def test_load_config_rejects_neither_file_nor_json():
    with pytest.raises(ValueError, match="neither a readable file nor valid JSON"):
        _load_config("not-a-file-or-json")


async def test_payload_build_config_payload_type_conflict(payload_commands):
    resp = await payload_commands._payload_build(_args(
        payload_type="poseidon",
        config=json.dumps({"payload_type": "arachne", "selected_os": "Linux", "filename": "x"})))
    assert "conflicts with requested payload type" in resp


# ----- pre-fill (not skip) -----

async def test_prefilled_fields_populate_form_defaults(payload_commands, monkeypatch):
    """A partial config pre-fills every field's FieldSpec.initial (not skip), and pre-checks
    the profile-selection modal."""
    config = json.dumps({
        "selected_os": "Linux",
        "build_parameters": {"mode": "default"},
        "c2_profiles": [{"name": "websocket", "parameters": {"callback_port": "80"}}],
    })

    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux", "Windows"]}

    async def fake_query_build_parameters(_session, _name):
        return [
            {"name": "mode", "parameter_type": "ChooseOne", "required": False,
             "choices": ["default", "custom"], "group_name": ""},
            {"name": "debug", "parameter_type": "Boolean", "required": False, "group_name": ""},
        ]

    async def fake_query_supported_c2_profiles(_session, _name):
        return {"supports_multiple": True, "profiles": [
            {"name": "websocket", "c2profileparameters": [
                {"name": "callback_port", "parameter_type": "String", "required": False},
            ]},
        ]}

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)
    monkeypatch.setattr(PayloadTypeQueries, "query_supported_c2_profiles", fake_query_supported_c2_profiles)
    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", _no_catalog)

    queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "custom.bin", "mode": "default", "debug": True}),
        (ChoicePrompt, ["websocket"]),
        (ParamForm, {"callback_port": "80"}),
        (SelectCommands, None),
        (BuildSummary, True),
    ])

    captured_args = {}

    async def fake_run_build(self, args, payload_type_name, build_config):
        captured_args["config"] = build_config
        return "[+] ok"

    monkeypatch.setattr(MythicCommands, "_run_build", fake_run_build)

    resp = await payload_commands._payload_build(_args(config=config))

    assert resp == "[+] ok"
    assert queue == []

    payload_form = captured[0]
    specs_by_name = {spec.name: spec for spec in payload_form.specs}
    assert specs_by_name["selected_os"].initial == "Linux"
    assert specs_by_name["filename"].initial == "poseidon"
    assert specs_by_name["mode"].initial == "default"
    assert specs_by_name["debug"].initial is None

    profile_prompt = captured[1]
    assert profile_prompt.preselected == {"websocket"}

    profile_form = captured[2]
    assert profile_form.specs[0].initial == "80"

    commands_modal = captured[3]
    assert commands_modal.included == []

    assembled = captured_args["config"]
    assert assembled["filename"] == "custom.bin"
    assert assembled["build_parameters"] == {"mode": "default", "debug": True}
    assert assembled["c2_profiles"] == [{"name": "websocket", "parameters": {"callback_port": "80"}}]
    assert assembled["commands"] is None


# ----- assembly -----

async def test_full_questionnaire_assembles_canonical_config(payload_commands, monkeypatch):
    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux"]}

    async def fake_query_build_parameters(_session, _name):
        return [{"name": "mode", "parameter_type": "ChooseOne", "required": False,
                  "choices": ["default"], "group_name": ""}]

    async def fake_query_supported_c2_profiles(_session, _name):
        return {"supports_multiple": True, "profiles": [
            {"name": "websocket", "c2profileparameters": [
                {"name": "callback_port", "parameter_type": "String", "required": False},
            ]},
        ]}

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)
    monkeypatch.setattr(PayloadTypeQueries, "query_supported_c2_profiles", fake_query_supported_c2_profiles)
    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", _no_catalog)

    queue, _captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin", "mode": "default"}),
        (ChoicePrompt, ["websocket"]),
        (ParamForm, {"callback_port": "8080"}),
        (SelectCommands, None),
        (BuildSummary, True),
    ])

    captured_args = {}

    async def fake_run_build(self, args, payload_type_name, build_config):
        captured_args["config"] = build_config
        return "[+] ok"

    monkeypatch.setattr(MythicCommands, "_run_build", fake_run_build)

    resp = await payload_commands._payload_build(_args(config="{}", payload_type="poseidon"))

    assert resp == "[+] ok"
    assert queue == []
    assert captured_args["config"] == {
        "payload_type": "poseidon",
        "selected_os": "Linux",
        "filename": "payload.bin",
        "build_parameters": {"mode": "default"},
        "c2_profiles": [{"name": "websocket", "parameters": {"callback_port": "8080"}}],
        "commands": None,
        "description": "",
    }


# ----- supported-profile filtering -----

async def test_supported_profiles_filter_choices(payload_commands, monkeypatch):
    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux"]}

    async def fake_query_build_parameters(_session, _name):
        return []

    async def fake_query_supported_c2_profiles(_session, _name):
        return {"supports_multiple": True, "profiles": [
            {"name": "websocket", "c2profileparameters": []},
            {"name": "webshell", "c2profileparameters": []},
        ]}

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)
    monkeypatch.setattr(PayloadTypeQueries, "query_supported_c2_profiles", fake_query_supported_c2_profiles)
    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", _no_catalog)

    def boom(*_a, **_kw):
        raise AssertionError("fallback must not be used when the join already returned profiles")

    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", boom)

    _queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, None),
        (BuildSummary, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})

    assert captured[1].choices == ["websocket", "webshell"]
    assert config["c2_profiles"] == [{"name": "websocket", "parameters": {}}]


async def test_supported_profiles_fallback_when_join_empty(payload_commands, monkeypatch):
    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux"]}

    async def fake_query_build_parameters(_session, _name):
        return []

    async def fake_query_supported_c2_profiles(_session, _name):
        return {"supports_multiple": True, "profiles": []}

    async def fake_query_all_c2_profiles(_session):
        return [{"name": "tcp", "c2profileparameters": []}]

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)
    monkeypatch.setattr(PayloadTypeQueries, "query_supported_c2_profiles", fake_query_supported_c2_profiles)
    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)
    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", _no_catalog)

    _queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["tcp"]),
        (SelectCommands, None),
        (BuildSummary, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})

    assert captured[1].choices == ["tcp"]
    assert config["c2_profiles"] == [{"name": "tcp", "parameters": {}}]


# ----- single vs multi C2 -----

async def test_single_c2_profile_uses_pulldown_form(payload_commands, monkeypatch):
    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux"]}

    async def fake_query_build_parameters(_session, _name):
        return []

    async def fake_query_supported_c2_profiles(_session, _name):
        return {"supports_multiple": False, "profiles": [{"name": "webshell", "c2profileparameters": []}]}

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)
    monkeypatch.setattr(PayloadTypeQueries, "query_supported_c2_profiles", fake_query_supported_c2_profiles)
    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", _no_catalog)

    _queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ParamForm, {"profile": "webshell"}),
        (SelectCommands, None),
        (BuildSummary, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})

    profile_form = captured[1]
    assert profile_form.specs == [FieldSpec(name="profile", parameter_type="ChooseOne", required=True,
                                            choices=["webshell"], initial=None)]
    assert config["c2_profiles"] == [{"name": "webshell", "parameters": {}}]


async def test_multi_c2_profile_uses_checkbox_choice_prompt(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch, supports_multiple=True)

    _queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, None),
        (BuildSummary, True),
    ])

    await payload_commands._payload_build_questionnaire("poseidon", {})

    assert isinstance(captured[1], ChoicePrompt)
    assert captured[1].mode == "multi"


# ----- back navigation -----

def _spec(form, name):
    return next(spec for spec in form.specs if spec.name == name)


async def test_back_from_profiles_returns_to_prefilled_payload_form(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch, supports_multiple=True)

    _queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "first.bin"}),   # payload
        (ChoicePrompt, BACK),                                             # profiles -> Back
        (ParamForm, {"selected_os": "Linux", "filename": "second.bin"}),  # payload (re-shown)
        (ChoicePrompt, ["websocket"]),                                    # profiles
        (SelectCommands, None),                                           # commands
        (BuildSummary, True),                                              # confirm
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})

    # The re-shown payload form keeps what was entered the first time.
    reshown = captured[2]
    assert isinstance(reshown, ParamForm)
    assert _spec(reshown, "selected_os").initial == "Linux"
    assert _spec(reshown, "filename").initial == "first.bin"
    # The second pass's edit is what wins.
    assert config["filename"] == "second.bin"


async def test_back_from_confirm_returns_to_commands(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch, supports_multiple=True)

    queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),  # payload
        (ChoicePrompt, ["websocket"]),                                     # profiles
        (SelectCommands, None),                                            # commands
        (BuildSummary, BACK),                                               # confirm -> Back
        (SelectCommands, None),                                            # commands (re-shown)
        (BuildSummary, True),                                               # confirm
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})

    assert queue == []
    assert isinstance(captured[4], SelectCommands)
    assert config["payload_type"] == "poseidon"
    assert config["c2_profiles"] == [{"name": "websocket", "parameters": {}}]


async def test_back_preserves_entered_c2_profile_parameters(payload_commands, monkeypatch):
    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux"]}

    async def fake_query_build_parameters(_session, _name):
        return []

    async def fake_query_supported_c2_profiles(_session, _name):
        return {"supports_multiple": True, "profiles": [
            {"name": "websocket", "c2profileparameters": [
                {"name": "callback_port", "parameter_type": "String", "required": False},
            ]},
        ]}

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)
    monkeypatch.setattr(PayloadTypeQueries, "query_supported_c2_profiles", fake_query_supported_c2_profiles)
    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", _no_catalog)

    # Back from the commands modal returns to the profile-params form, which must be
    # pre-filled with what was just entered.
    queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),  # payload
        (ChoicePrompt, ["websocket"]),                                     # profiles
        (ParamForm, {"callback_port": "8080"}),                            # websocket params
        (SelectCommands, BACK),                                            # commands -> Back
        (ParamForm, {"callback_port": "8080"}),                            # websocket params (re-shown)
        (SelectCommands, None),                                            # commands
        (BuildSummary, True),                                               # confirm
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})

    reshown_params = captured[4]
    assert isinstance(reshown_params, ParamForm)
    assert _spec(reshown_params, "callback_port").initial == "8080"
    assert config["c2_profiles"] == [{"name": "websocket", "parameters": {"callback_port": "8080"}}]


# ----- command set -----

async def test_command_set_opens_with_builtin_and_suggested_included(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_catalog(_session, _payload_type_name, custom_return_attributes=None):
        return [
            {"cmd": "exit", "attributes": {"builtin": True}},
            {"cmd": "shell", "attributes": {"suggested_command": True}},
            {"cmd": "ls", "attributes": {}},
        ]

    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", fake_catalog)

    _queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, ["exit", "shell"]),
        (BuildSummary, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})

    commands_modal = captured[2]
    assert commands_modal.included == ["exit", "shell"]
    assert commands_modal.excluded == ["ls"]
    assert commands_modal.builtin == {"exit"}
    assert config["commands"] == ["exit", "shell"]


async def test_command_set_returns_included_list(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_catalog(_session, _payload_type_name, custom_return_attributes=None):
        return [{"cmd": "ls"}, {"cmd": "cat"}, {"cmd": "shell"}]

    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", fake_catalog)

    _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, ["cat", "ls", "shell"]),
        (BuildSummary, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert sorted(config["commands"]) == ["cat", "ls", "shell"]


async def test_command_set_custom_uses_selected_subset(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_catalog(_session, _payload_type_name, custom_return_attributes=None):
        return [{"cmd": "ls"}, {"cmd": "cat"}, {"cmd": "shell"}]

    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", fake_catalog)

    _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, ["ls"]),
        (BuildSummary, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert config["commands"] == ["ls"]


async def test_command_set_prefill_included_from_config(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_catalog(_session, _payload_type_name, custom_return_attributes=None):
        return [{"cmd": "ls"}, {"cmd": "cat"}]

    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", fake_catalog)

    _queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, ["ls"]),
        (BuildSummary, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {"commands": ["ls"]})

    commands_modal = captured[2]
    assert commands_modal.included == ["ls"]
    assert commands_modal.excluded == ["cat"]
    assert config["commands"] == ["ls"]


# ----- cancel -----

async def test_cancel_at_payload_form_aborts_without_building(payload_commands, monkeypatch):
    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux"]}

    async def fake_query_build_parameters(_session, _name):
        return []

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)
    _queue_prompt(monkeypatch, [(ParamForm, None)])

    def boom(*_a, **_kw):
        raise AssertionError("_run_build must not be called when the questionnaire is cancelled")

    monkeypatch.setattr(MythicCommands, "_run_build", boom)

    resp = await payload_commands._payload_build(_args(config="{}"))
    assert str(resp) == "[-] build cancelled"


async def test_cancel_at_profile_selection_aborts(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, None),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert config is None


async def test_cancel_at_commands_modal_aborts(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, SelectCommands.CANCELLED),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert config is None


async def test_cancel_at_final_confirm_aborts(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, None),
        (BuildSummary, False),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert config is None


# ----- -bg survives the questionnaire branch -----

async def test_background_flag_survives_questionnaire_path(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, None),
        (BuildSummary, True),
    ])

    async def fake_create_payload(*_a, **kwargs):
        assert kwargs["return_on_complete"] is False
        return {"uuid": "abc-123", "status": "building"}

    monkeypatch.setattr(mythic_agent.mythic, "create_payload", fake_create_payload)

    resp = await payload_commands._payload_build(_args(background=True))
    assert "Build started" in resp


# ----- ParamForm (widget-level, inline validation) -----

async def test_param_form_required_string_blank_blocks_submit_and_flags_field():
    app = App()
    async with app.run_test() as pilot:
        modal = ParamForm("Build", [FieldSpec(name="host", parameter_type="String", required=True)])
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#ok")
        await pilot.pause()

        assert "value" not in dismissed
        assert str(modal.query_one("#error_0", Label).content) == "required"


async def test_param_form_bad_number_blocks_submit_and_flags_field():
    app = App()
    async with app.run_test() as pilot:
        modal = ParamForm("Build", [FieldSpec(name="port", parameter_type="Number", required=True)])
        app.push_screen(modal)
        await pilot.pause()

        modal.query_one("#field_0", Input).value = "not-a-number"
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#ok")
        await pilot.pause()

        assert "value" not in dismissed
        assert "number" in str(modal.query_one("#error_0", Label).content)


async def test_param_form_regex_mismatch_blocks_submit():
    app = App()
    async with app.run_test() as pilot:
        modal = ParamForm("Build", [FieldSpec(
            name="version", parameter_type="String", required=True, verifier_regex=r"v\d+\.\d+\.\d+")])
        app.push_screen(modal)
        await pilot.pause()

        modal.query_one("#field_0", Input).value = "nope"
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#ok")
        await pilot.pause()

        assert "value" not in dismissed
        assert "match" in str(modal.query_one("#error_0", Label).content)


async def test_param_form_anchored_prefix_regex_accepts_valid_value():
    """Mythic's verifier_regex are anchored prefix patterns (search semantics). A value
    like `ws://127.0.0.1` must pass `^(ws|wss)://+` rather than be rejected by full-match."""
    app = App()
    async with app.run_test() as pilot:
        modal = ParamForm("Build", [FieldSpec(
            name="callback_host", parameter_type="String", required=True,
            verifier_regex=r"^(ws|wss)://+")])
        app.push_screen(modal)
        await pilot.pause()

        modal.query_one("#field_0", Input).value = "ws://127.0.0.1"
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#ok")
        await pilot.pause()

        assert dismissed.get("value") == {"callback_host": "ws://127.0.0.1"}
        assert str(modal.query_one("#error_0", Label).content) == ""


async def test_param_form_one_bad_field_does_not_block_the_rest():
    """Inline validation flags only the offending field; it does not abort the whole form."""
    app = App()
    async with app.run_test() as pilot:
        specs = [
            FieldSpec(name="port", parameter_type="Number", required=True),
            FieldSpec(name="host", parameter_type="String", required=True, initial="example.com"),
        ]
        modal = ParamForm("Build", specs)
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#ok")
        # Button.press() suppresses re-clicks for its 0.2s "active" animation window;
        # clear it before clicking again or the second click is silently swallowed.
        await pilot.pause(0.3)

        assert "value" not in dismissed
        assert str(modal.query_one("#error_0", Label).content) == "required"
        assert str(modal.query_one("#error_1", Label).content) == ""

        modal.query_one("#field_0", Input).value = "42"
        await pilot.pause()
        await pilot.click("#ok")
        await pilot.pause()

        assert dismissed["value"] == {"port": 42, "host": "example.com"}


async def test_param_form_valid_submit_returns_coerced_dict():
    app = App()
    async with app.run_test() as pilot:
        specs = [
            FieldSpec(name="port", parameter_type="Number", required=True),
            FieldSpec(name="hosts", parameter_type="Array", required=False),
            FieldSpec(name="env", parameter_type="Dictionary", required=False),
            FieldSpec(name="debug", parameter_type="Boolean"),
            FieldSpec(name="mode", parameter_type="ChooseOne", choices=["a", "b"], required=True),
        ]
        modal = ParamForm("Build", specs)
        app.push_screen(modal)
        await pilot.pause()

        modal.query_one("#field_0", Input).value = "42"
        modal.query_one("#field_1", TextArea).text = "one\ntwo"
        modal.query_one("#field_2", TextArea).text = '{"x": 1}'
        modal.query_one("#field_3", Checkbox).value = True
        modal.query_one("#field_4", Select).value = "b"
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#ok")
        await pilot.pause()

        assert dismissed["value"] == {
            "port": 42, "hosts": ["one", "two"], "env": {"x": 1}, "debug": True, "mode": "b",
        }


async def test_param_form_optional_choose_one_blank_is_omitted():
    app = App()
    async with app.run_test() as pilot:
        modal = ParamForm("Build", [FieldSpec(name="mode", parameter_type="ChooseOne", choices=["a", "b"])])
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#ok")
        await pilot.pause()

        assert dismissed["value"] == {}


async def test_param_form_choose_multiple_prechecks_initial():
    app = App()
    async with app.run_test() as pilot:
        modal = ParamForm("Build", [FieldSpec(
            name="flags", parameter_type="ChooseMultiple", choices=["a", "b", "c"], initial=["a", "c"])])
        app.push_screen(modal)
        await pilot.pause()

        selection_list = modal.query_one("#field_0", CheckSelectionList)
        assert set(selection_list.selected) == {"a", "c"}


async def test_param_form_cancel_returns_none():
    app = App()
    async with app.run_test() as pilot:
        modal = ParamForm("Build", [FieldSpec(name="host", parameter_type="String")])
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#cancel")
        await pilot.pause()
        assert dismissed["value"] is None


# ----- ChoicePrompt pre-selection -----

async def test_choice_prompt_preselects_given_values():
    app = App()
    async with app.run_test() as pilot:
        modal = ChoicePrompt("C2 profiles", ["websocket", "webshell"], mode="multi",
                             preselected=["webshell"])
        app.push_screen(modal)
        await pilot.pause()

        choice_list = modal.query_one("#choices", CheckSelectionList)
        assert set(choice_list.selected) == {"webshell"}


async def test_choice_prompt_cancel_returns_none():
    app = App()
    async with app.run_test() as pilot:
        modal = ChoicePrompt("OS", ["Linux"], mode="single")
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#cancel")
        await pilot.pause()
        assert dismissed["value"] is None


# ----- SelectCommands (two-pane transfer list) -----

_CATALOG_WITH_DEFAULTS = [
    {"cmd": "exit", "attributes": {"builtin": True}},
    {"cmd": "shell", "attributes": {"suggested_command": True}},
    {"cmd": "ls", "attributes": {}},
    {"cmd": "cat", "attributes": {}},
]


async def test_select_commands_opens_with_default_set_included():
    app = App()
    async with app.run_test() as pilot:
        modal = SelectCommands(_CATALOG_WITH_DEFAULTS)
        app.push_screen(modal)
        await pilot.pause()

        included = modal.query_one("#included_list", CheckSelectionList)
        excluded = modal.query_one("#excluded_list", CheckSelectionList)
        assert [o.value for o in included.options] == ["exit", "shell"]
        assert [o.value for o in excluded.options] == ["cat", "ls"]

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        modal._ok()
        assert dismissed["value"] == ["exit", "shell"]


async def test_select_commands_move_right_adds_excluded_to_included():
    app = App()
    async with app.run_test() as pilot:
        modal = SelectCommands(_CATALOG_WITH_DEFAULTS)
        app.push_screen(modal)
        await pilot.pause()

        # `>` moves from the left (Excluded) into Included.
        excluded = modal.query_one("#excluded_list", CheckSelectionList)
        excluded.select("ls")
        await pilot.pause()
        await pilot.click("#move_right")
        await pilot.pause()

        # The destination pane re-sorts alphabetically after the move.
        assert modal.included == ["exit", "ls", "shell"]
        assert modal.excluded == ["cat"]


async def test_select_commands_move_left_removes_from_included():
    app = App()
    async with app.run_test() as pilot:
        modal = SelectCommands(_CATALOG_WITH_DEFAULTS)
        app.push_screen(modal)
        await pilot.pause()

        # `<` moves from the right (Included) into Excluded.
        included = modal.query_one("#included_list", CheckSelectionList)
        included.select("shell")
        await pilot.pause()
        await pilot.click("#move_left")
        await pilot.pause()

        # The destination pane re-sorts alphabetically after the move.
        assert modal.included == ["exit"]
        assert modal.excluded == ["cat", "ls", "shell"]


async def test_select_commands_builtin_cannot_be_removed():
    app = App()
    async with app.run_test() as pilot:
        modal = SelectCommands(_CATALOG_WITH_DEFAULTS)
        app.push_screen(modal)
        await pilot.pause()

        # Select-all in the Included pane, then try to move everything to Excluded:
        # the builtin (exit) stays put.
        included = modal.query_one("#included_list", CheckSelectionList)
        included.select_all()
        await pilot.pause()
        await pilot.click("#move_left")
        await pilot.pause()

        assert modal.included == ["exit"]
        assert "exit" not in modal.excluded


async def test_select_commands_filter_narrows_a_pane():
    app = App()
    async with app.run_test() as pilot:
        modal = SelectCommands(_CATALOG_WITH_DEFAULTS)
        app.push_screen(modal)
        await pilot.pause()

        filt = modal.query_one("#excluded_filter", Input)
        filt.value = "ca"
        filt.post_message(Input.Changed(filt, "ca"))
        await pilot.pause()

        excluded = modal.query_one("#excluded_list", CheckSelectionList)
        assert [o.value for o in excluded.options] == ["cat"]


async def test_select_commands_included_prefill_overrides_default():
    app = App()
    async with app.run_test() as pilot:
        modal = SelectCommands(_CATALOG_WITH_DEFAULTS, included=["ls"])
        app.push_screen(modal)
        await pilot.pause()

        # The explicit set wins, but builtins are always folded in.
        assert modal.included == ["exit", "ls"]
        assert sorted(modal.excluded) == ["cat", "shell"]

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        modal._ok()
        assert dismissed["value"] == ["exit", "ls"]


async def test_select_commands_cancel_returns_cancelled_sentinel():
    app = App()
    async with app.run_test() as pilot:
        modal = SelectCommands([{"cmd": "ls"}])
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#cancel")
        await pilot.pause()
        assert dismissed["value"] is SelectCommands.CANCELLED


_OS_CATALOG = [
    {"cmd": "shell", "attributes": {"suggested_command": True}},                       # all OSes
    {"cmd": "powershell", "attributes": {"supported_os": ["Windows"], "suggested_command": True}},
    {"cmd": "sudo", "attributes": {"supported_os": ["Linux", "macOS"]}},
]


async def test_select_commands_os_incompatible_is_locked_in_excluded():
    app = App()
    async with app.run_test() as pilot:
        modal = SelectCommands(_OS_CATALOG, selected_os="Linux")
        app.push_screen(modal)
        await pilot.pause()

        # powershell is Windows-only: excluded, locked, with a tooltip explaining why.
        assert "powershell" in modal.reasons
        assert "sudo" not in modal.reasons
        # It stays out of the default set even though it's a suggested command.
        assert modal.included == ["shell"]
        assert "powershell" in modal.excluded

        excluded = modal.query_one("#excluded_list", CheckSelectionList)
        locked = next(o for o in excluded.options if o.value == "powershell")
        assert locked.disabled is True
        assert "Windows" in excluded.option_tooltips["powershell"]

        # Even force-selected, an incompatible command can't be moved into Included.
        modal.excluded_selected = {"powershell"}
        modal._move_right()
        assert "powershell" not in modal.included


async def test_select_commands_filters_by_build_parameter():
    app = App()
    async with app.run_test() as pilot:
        catalog = [
            {"cmd": "keylog", "attributes": {"filter_by_build_parameter": {"mode": "advanced"}}},
            {"cmd": "ls", "attributes": {}},
        ]

        blocked = SelectCommands(catalog, build_parameters={"mode": "basic"})
        app.push_screen(blocked)
        await pilot.pause()
        assert "keylog" in blocked.reasons
        assert "mode = advanced" in blocked.reasons["keylog"]
        assert "keylog" in blocked.excluded

        allowed = SelectCommands(catalog, build_parameters={"mode": "advanced"})
        assert "keylog" not in allowed.reasons


async def test_command_set_filters_commands_for_selected_os(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_catalog(_session, _payload_type_name, custom_return_attributes=None):
        return _OS_CATALOG

    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", fake_catalog)

    _queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, ["shell"]),
        (BuildSummary, True),
    ])

    await payload_commands._payload_build_questionnaire("poseidon", {})

    commands_modal = captured[2]
    assert "powershell" in commands_modal.reasons


# ----- BuildSummary (final review) -----

async def test_build_summary_shows_collapsible_sections_and_builds():
    from textual.widgets import Collapsible, Static

    app = App()
    async with app.run_test() as pilot:
        modal = BuildSummary(
            payload_type="poseidon", selected_os="Linux", filename="imp.bin",
            build_parameters={"mode": "default"},
            c2_profiles=[{"name": "websocket", "parameters": {"callback_port": "8080"}}],
            commands=["shell", "ls"], description="demo", show_back=True)
        app.push_screen(modal)
        await pilot.pause()

        titles = [c.title for c in modal.query(Collapsible)]
        assert titles == ["Payload", "C2 profile: websocket", "Commands (2)"]

        # Payload section carries the core fields (CollapsibleTitle subclasses Static, so
        # restrict to the plain-Static section bodies).
        bodies = " ".join(str(s.render()) for s in modal.query(Static) if type(s) is Static)
        assert "poseidon" in bodies and "imp.bin" in bodies and "callback_port" in bodies

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#build")
        await pilot.pause()
        assert dismissed["value"] is True


async def test_build_summary_back_returns_sentinel():
    app = App()
    async with app.run_test() as pilot:
        modal = BuildSummary(payload_type="p", selected_os="Linux", filename="f", show_back=True)
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#back")
        await pilot.pause()
        assert dismissed["value"] is BACK


async def test_build_summary_cancel_returns_false():
    app = App()
    async with app.run_test() as pilot:
        modal = BuildSummary(payload_type="p", selected_os="Linux", filename="f", show_back=True)
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#cancel")
        await pilot.pause()
        assert dismissed["value"] is False


# ----- colored output + quick-build line -----

def test_quick_build_command_roundtrips_to_complete_config():
    config = {
        "selected_os": "Linux", "filename": "imp.bin",
        "build_parameters": {"mode": "default"},
        "c2_profiles": [{"name": "websocket", "parameters": {"callback_port": "443"}}],
        "commands": ["ls", "shell"], "description": "x",
    }
    line = mythic_agent._quick_build_command("poseidon", config)

    assert line.startswith("payload build poseidon --config '")
    assert "\n" not in line  # single line
    json_part = line[len("payload build poseidon --config '"):-1]
    # compact separators, not pretty-printed
    assert ", " not in json_part and '": ' not in json_part

    parsed = _load_config(json_part)
    assert mythic_agent._config_is_complete(parsed)
    assert parsed["payload_type"] == "poseidon"
    assert parsed["commands"] == ["ls", "shell"]
    assert parsed["c2_profiles"] == [{"name": "websocket", "parameters": {"callback_port": "443"}}]


async def test_successful_build_output_is_green_with_quick_build(payload_commands, monkeypatch):
    async def fake_create_payload(*_a, **_kw):
        return {"build_phase": "success", "uuid": "abc-123"}

    async def fake_download(self, path):
        pass

    monkeypatch.setattr(mythic_agent.mythic, "create_payload", fake_create_payload)
    monkeypatch.setattr(mythic_agent.Payload, "download", fake_download)

    resp = await payload_commands._payload_build(
        _args(config=json.dumps({"selected_os": "Linux", "filename": "payload.bin"})))

    styles = {span.style for span in resp.spans}
    assert "green" in styles and "dim" in styles
    assert "Payload built and saved" in str(resp)
    assert "quick build: payload build poseidon --config" in str(resp)


async def test_cancelled_build_output_is_red(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)
    _queue_prompt(monkeypatch, [(ParamForm, None)])

    resp = await payload_commands._payload_build(_args(config="{}"))
    assert str(resp) == "[-] build cancelled"
    assert resp.style == "red"
