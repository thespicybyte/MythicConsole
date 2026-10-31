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
from screens.prompts import ChoicePrompt, YesNoPrompt
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
        (YesNoPrompt, True),
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
    assert commands_modal.mode == "default"

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
        (YesNoPrompt, True),
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
        (YesNoPrompt, True),
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
        (YesNoPrompt, True),
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
        (YesNoPrompt, True),
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
        (YesNoPrompt, True),
    ])

    await payload_commands._payload_build_questionnaire("poseidon", {})

    assert isinstance(captured[1], ChoicePrompt)
    assert captured[1].mode == "multi"


# ----- command set -----

async def test_command_set_default_leaves_commands_none(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, None),
        (YesNoPrompt, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert config["commands"] is None


async def test_command_set_all_uses_full_catalog(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_catalog(_session, _payload_type_name, custom_return_attributes=None):
        return [{"cmd": "ls"}, {"cmd": "cat"}, {"cmd": "shell"}]

    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", fake_catalog)

    _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, SelectCommands.ALL),
        (YesNoPrompt, True),
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
        (YesNoPrompt, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert config["commands"] == ["ls"]


async def test_command_set_prefill_opens_custom_mode_prechecked(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_catalog(_session, _payload_type_name, custom_return_attributes=None):
        return [{"cmd": "ls"}, {"cmd": "cat"}]

    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", fake_catalog)

    _queue, captured = _queue_prompt(monkeypatch, [
        (ParamForm, {"selected_os": "Linux", "filename": "payload.bin"}),
        (ChoicePrompt, ["websocket"]),
        (SelectCommands, ["ls"]),
        (YesNoPrompt, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {"commands": ["ls"]})

    commands_modal = captured[2]
    assert commands_modal.mode == "custom"
    assert commands_modal.selected == {"ls"}
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
    assert resp == "[-] build cancelled"


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
        (YesNoPrompt, False),
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
        (YesNoPrompt, True),
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


# ----- SelectCommands (mode selector) -----

async def test_select_commands_default_mode_hides_catalog_and_returns_none():
    app = App()
    async with app.run_test() as pilot:
        catalog = [{"cmd": "ls"}, {"cmd": "cat"}]
        modal = SelectCommands(catalog)
        app.push_screen(modal)
        await pilot.pause()

        assert modal.query_one("#commands", CheckSelectionList).display is False

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#ok")
        await pilot.pause()
        assert dismissed["value"] is None


async def test_select_commands_all_mode_returns_all_marker():
    app = App()
    async with app.run_test() as pilot:
        catalog = [{"cmd": "ls"}, {"cmd": "cat"}]
        modal = SelectCommands(catalog, mode="all")
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#ok")
        await pilot.pause()
        assert dismissed["value"] is SelectCommands.ALL


async def test_select_commands_custom_mode_shows_catalog_and_filters():
    app = App()
    async with app.run_test() as pilot:
        catalog = [{"cmd": "ls"}, {"cmd": "cat"}, {"cmd": "shell"}]
        modal = SelectCommands(catalog, mode="custom")
        app.push_screen(modal)
        await pilot.pause()

        assert modal.query_one("#commands", CheckSelectionList).display is True

        filt = modal.query_one("#filter", Input)
        filt.value = "sh"
        filt.post_message(Input.Changed(filt, "sh"))
        await pilot.pause()

        commands_list = modal.query_one("#commands", CheckSelectionList)
        assert [o.value for o in commands_list.options] == ["shell"]

        filt.value = ""
        filt.post_message(Input.Changed(filt, ""))
        await pilot.pause()

        commands_list.select_all()
        await pilot.pause()
        assert modal.selected == {"cat", "ls", "shell"}

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        modal._ok()
        assert dismissed["value"] == ["cat", "ls", "shell"]


async def test_select_commands_custom_mode_preselected():
    app = App()
    async with app.run_test() as pilot:
        catalog = [{"cmd": "ls"}, {"cmd": "cat"}]
        modal = SelectCommands(catalog, mode="custom", preselected=["cat"])
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        modal._ok()
        assert dismissed["value"] == ["cat"]


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
