import json
import types

import pytest
from textual.app import App

from backend.mythic_agent import mythic_agent
from backend.mythic_agent.mythic_agent import MythicCommands, _CANCELLED, _SKIPPED
from backend.payload_type.queries import PayloadTypeQueries
from backend.c2_profile.queries import C2ProfileQueries
from screens.prompts import ChoicePrompt, FilePrompt, TextPrompt, YesNoPrompt
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
    against `queue` (a list of (expected_type, return_value) pairs) and returns the canned value."""

    async def _fake_prompt(screen):
        assert queue, f"unexpected prompt: {screen!r}"
        expected_type, value = queue.pop(0)
        assert isinstance(screen, expected_type), f"expected {expected_type}, got {type(screen)}"
        return value

    monkeypatch.setattr(mythic_agent, "_prompt", _fake_prompt)
    return queue


# ----- config-complete bypass -----

async def test_complete_config_skips_questionnaire(payload_commands, tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"selected_os": "Linux", "filename": "payload.bin"}))

    called = []
    monkeypatch.setattr(mythic_agent, "_prompt", lambda screen: called.append(screen))

    async def fake_create_payload(*_a, **kwargs):
        return {"build_phase": "success", "uuid": "abc-123"}

    async def fake_download(self, path):
        pass

    monkeypatch.setattr(mythic_agent.mythic, "create_payload", fake_create_payload)
    monkeypatch.setattr(mythic_agent.Payload, "download", fake_download)

    resp = await payload_commands._payload_build(_args(config=str(config_path)))

    assert called == []
    assert "Payload built and saved" in resp


# ----- pre-fill / skip -----

async def test_prefilled_fields_are_not_reasked(payload_commands, tmp_path, monkeypatch):
    """selected_os and c2_profiles are already answered; only filename and the one unanswered
    build parameter should prompt. commands is left unset so the command-set step still runs."""
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "selected_os": "Linux",
        "build_parameters": {"mode": "default"},
        "c2_profiles": [{"name": "websocket", "parameters": {"callback_port": "80"}}],
    }))

    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux", "Windows"]}

    async def fake_query_build_parameters(_session, _name):
        return [
            {"name": "mode", "parameter_type": "ChooseOne", "required": False,
             "choices": ["default", "custom"], "group_name": ""},
            {"name": "debug", "parameter_type": "Boolean", "required": False, "group_name": ""},
        ]

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)

    def boom(*_a, **_kw):
        raise AssertionError("c2 profiles already answered; should not be queried")

    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", boom)

    queue = _queue_prompt(monkeypatch, [
        (TextPrompt, "custom.bin"),     # filename
        (YesNoPrompt, True),            # debug
        (ChoicePrompt, "default"),      # command set
        (YesNoPrompt, True),            # final confirm
    ])

    captured = {}

    async def fake_run_build(self, args, payload_type_name, config):
        captured["args"] = args
        captured["payload_type_name"] = payload_type_name
        captured["config"] = config
        return "[+] ok"

    monkeypatch.setattr(MythicCommands, "_run_build", fake_run_build)

    resp = await payload_commands._payload_build(_args(config=str(config_path)))

    assert resp == "[+] ok"
    assert queue == []
    assembled = captured["config"]
    assert assembled["selected_os"] == "Linux"
    assert assembled["filename"] == "custom.bin"
    assert assembled["build_parameters"] == {"mode": "default", "debug": True}
    assert assembled["c2_profiles"] == [{"name": "websocket", "parameters": {"callback_port": "80"}}]
    assert assembled["commands"] is None


# ----- assembly -----

async def test_full_questionnaire_assembles_canonical_config(payload_commands, tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({}))

    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux"]}

    async def fake_query_build_parameters(_session, _name):
        return [{"name": "mode", "parameter_type": "ChooseOne", "required": False,
                  "choices": ["default"], "group_name": ""}]

    async def fake_query_all_c2_profiles(_session):
        return [{"name": "websocket", "c2profileparameters": [
            {"name": "callback_port", "parameter_type": "String", "required": False},
        ]}]

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)
    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)

    queue = _queue_prompt(monkeypatch, [
        (ChoicePrompt, "Linux"),        # selected_os
        (TextPrompt, "payload.bin"),    # filename
        (ChoicePrompt, "default"),      # mode build param
        (ChoicePrompt, ["websocket"]),  # c2 profile selection
        (TextPrompt, "8080"),           # websocket callback_port
        (ChoicePrompt, "default"),      # command set
        (YesNoPrompt, True),            # final confirm
    ])

    captured = {}

    async def fake_run_build(self, args, payload_type_name, config):
        captured["config"] = config
        return "[+] ok"

    monkeypatch.setattr(MythicCommands, "_run_build", fake_run_build)

    resp = await payload_commands._payload_build(_args(config=str(config_path), payload_type="poseidon"))

    assert resp == "[+] ok"
    assert queue == []
    assert captured["config"] == {
        "payload_type": "poseidon",
        "selected_os": "Linux",
        "filename": "payload.bin",
        "build_parameters": {"mode": "default"},
        "c2_profiles": [{"name": "websocket", "parameters": {"callback_port": "8080"}}],
        "commands": None,
        "description": "",
    }


# ----- command set -----

async def _bare_questionnaire_setup(monkeypatch):
    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux"]}

    async def fake_query_build_parameters(_session, _name):
        return []

    async def fake_query_all_c2_profiles(_session):
        return []

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    monkeypatch.setattr(PayloadTypeQueries, "query_build_parameters", fake_query_build_parameters)
    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)


async def test_command_set_default_leaves_commands_none(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_query_all_c2_profiles(_session):
        return [{"name": "websocket", "c2profileparameters": []}]

    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)

    _queue_prompt(monkeypatch, [
        (ChoicePrompt, "Linux"), (TextPrompt, "payload.bin"), (ChoicePrompt, ["websocket"]),
        (ChoicePrompt, "default"), (YesNoPrompt, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert config["commands"] is None


async def test_command_set_all_uses_full_catalog(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_query_all_c2_profiles(_session):
        return [{"name": "websocket", "c2profileparameters": []}]

    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)

    async def fake_catalog(_session, _payload_type_name, custom_return_attributes=None):
        return [{"cmd": "ls"}, {"cmd": "cat"}, {"cmd": "shell"}]

    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", fake_catalog)

    _queue_prompt(monkeypatch, [
        (ChoicePrompt, "Linux"), (TextPrompt, "payload.bin"), (ChoicePrompt, ["websocket"]),
        (ChoicePrompt, "all"), (YesNoPrompt, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert sorted(config["commands"]) == ["cat", "ls", "shell"]


async def test_command_set_custom_uses_select_commands_modal(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_query_all_c2_profiles(_session):
        return [{"name": "websocket", "c2profileparameters": []}]

    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)

    async def fake_catalog(_session, _payload_type_name, custom_return_attributes=None):
        return [{"cmd": "ls"}, {"cmd": "cat"}, {"cmd": "shell"}]

    monkeypatch.setattr(mythic_agent.mythic, "get_all_commands_for_payloadtype", fake_catalog)

    _queue_prompt(monkeypatch, [
        (ChoicePrompt, "Linux"), (TextPrompt, "payload.bin"), (ChoicePrompt, ["websocket"]),
        (ChoicePrompt, "custom"), (SelectCommands, ["ls"]), (YesNoPrompt, True),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert config["commands"] == ["ls"]


# ----- cancel -----

async def test_cancel_at_os_prompt_aborts_without_building(payload_commands, tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({}))

    async def fake_query_by_name(_session, _name):
        return {"supported_os": ["Linux"]}

    monkeypatch.setattr(PayloadTypeQueries, "query_by_name", fake_query_by_name)
    _queue_prompt(monkeypatch, [(ChoicePrompt, None)])

    def boom(*_a, **_kw):
        raise AssertionError("_run_build must not be called when the questionnaire is cancelled")

    monkeypatch.setattr(MythicCommands, "_run_build", boom)

    resp = await payload_commands._payload_build(_args(config=str(config_path)))
    assert resp == "[-] build cancelled"


async def test_cancel_at_final_confirm_aborts_with_profile(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_query_all_c2_profiles(_session):
        return [{"name": "websocket", "c2profileparameters": []}]

    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)

    _queue_prompt(monkeypatch, [
        (ChoicePrompt, "Linux"), (TextPrompt, "payload.bin"), (ChoicePrompt, ["websocket"]),
        (ChoicePrompt, "default"), (YesNoPrompt, False),
    ])

    config = await payload_commands._payload_build_questionnaire("poseidon", {})
    assert config is None


# ----- -bg survives the questionnaire branch -----

async def test_background_flag_survives_questionnaire_path(payload_commands, monkeypatch):
    await _bare_questionnaire_setup(monkeypatch)

    async def fake_query_all_c2_profiles(_session):
        return [{"name": "websocket", "c2profileparameters": []}]

    monkeypatch.setattr(C2ProfileQueries, "query_all_c2_profiles", fake_query_all_c2_profiles)

    _queue_prompt(monkeypatch, [
        (ChoicePrompt, "Linux"), (TextPrompt, "payload.bin"), (ChoicePrompt, ["websocket"]),
        (ChoicePrompt, "default"), (YesNoPrompt, True),
    ])

    async def fake_create_payload(*_a, **kwargs):
        assert kwargs["return_on_complete"] is False
        return {"uuid": "abc-123", "status": "building"}

    monkeypatch.setattr(mythic_agent.mythic, "create_payload", fake_create_payload)

    resp = await payload_commands._payload_build(_args(background=True))
    assert "Build started" in resp


# ----- per-parameter validation -----

async def test_required_param_blank_reprompts(payload_commands, monkeypatch):
    _queue_prompt(monkeypatch, [(TextPrompt, ""), (TextPrompt, "a-value")])
    value = await payload_commands._prompt_for_param(
        {"name": "host", "parameter_type": "String", "required": True})
    assert value == "a-value"


async def test_optional_param_blank_is_skipped(payload_commands, monkeypatch):
    _queue_prompt(monkeypatch, [(TextPrompt, "")])
    value = await payload_commands._prompt_for_param(
        {"name": "host", "parameter_type": "String", "required": False})
    assert value is _SKIPPED


async def test_number_param_non_numeric_reprompts(payload_commands, monkeypatch):
    _queue_prompt(monkeypatch, [(TextPrompt, "not-a-number"), (TextPrompt, "42")])
    value = await payload_commands._prompt_for_param(
        {"name": "port", "parameter_type": "Number", "required": True})
    assert value == 42


async def test_verifier_regex_mismatch_reprompts(payload_commands, monkeypatch):
    _queue_prompt(monkeypatch, [(TextPrompt, "nope"), (TextPrompt, "v1.2.3")])
    value = await payload_commands._prompt_for_param({
        "name": "version", "parameter_type": "String", "required": True,
        "verifier_regex": r"v\d+\.\d+\.\d+",
    })
    assert value == "v1.2.3"


async def test_required_choose_one_cancel_returns_cancelled(payload_commands, monkeypatch):
    _queue_prompt(monkeypatch, [(ChoicePrompt, None)])
    value = await payload_commands._prompt_for_param(
        {"name": "mode", "parameter_type": "ChooseOne", "required": True, "choices": ["a", "b"]})
    assert value is _CANCELLED


async def test_boolean_param_uses_yes_no_prompt(payload_commands, monkeypatch):
    _queue_prompt(monkeypatch, [(YesNoPrompt, True)])
    value = await payload_commands._prompt_for_param({"name": "debug", "parameter_type": "Boolean"})
    assert value is True


async def test_array_param_splits_lines(payload_commands, monkeypatch):
    _queue_prompt(monkeypatch, [(TextPrompt, "one\ntwo\nthree")])
    value = await payload_commands._prompt_for_param(
        {"name": "hosts", "parameter_type": "Array", "required": False})
    assert value == ["one", "two", "three"]


async def test_choose_multiple_param_returns_list(payload_commands, monkeypatch):
    _queue_prompt(monkeypatch, [(ChoicePrompt, ["a", "b"])])
    value = await payload_commands._prompt_for_param(
        {"name": "flags", "parameter_type": "ChooseMultiple", "required": False,
         "choices": ["a", "b", "c"]})
    assert value == ["a", "b"]


async def test_dictionary_param_reprompts_on_invalid_json(payload_commands, monkeypatch):
    _queue_prompt(monkeypatch, [(TextPrompt, "not json"), (TextPrompt, '{"a": 1}')])
    value = await payload_commands._prompt_for_param(
        {"name": "env", "parameter_type": "Dictionary", "required": True})
    assert value == {"a": 1}


# ----- new modals (widget-level) -----

async def test_text_prompt_submits_input_value():
    app = App()
    async with app.run_test() as pilot:
        modal = TextPrompt("Filename", default="payload.bin")
        app.push_screen(modal)
        await pilot.pause()

        from textual.widgets import Input
        field = modal.query_one("#value", Input)
        assert field.value == "payload.bin"

        result = {}
        modal.dismiss = lambda v=None: result.setdefault("value", v)
        field.post_message(Input.Submitted(field, "custom.bin"))
        await pilot.pause()
        assert result["value"] == "custom.bin"


async def test_text_prompt_cancel_returns_none():
    app = App()
    async with app.run_test() as pilot:
        modal = TextPrompt("Filename")
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        await pilot.click("#cancel")
        await pilot.pause()
        assert dismissed["value"] is None


async def test_choice_prompt_single_mode_keeps_only_last_selection():
    app = App()
    async with app.run_test() as pilot:
        modal = ChoicePrompt("OS", ["Linux", "Windows", "macOS"], mode="single")
        app.push_screen(modal)
        await pilot.pause()

        choice_list = modal.query_one("#choices", CheckSelectionList)
        choice_list.select("Linux")
        await pilot.pause()
        choice_list.select("Windows")
        await pilot.pause()

        assert list(choice_list.selected) == ["Windows"]


async def test_choice_prompt_multi_mode_keeps_all_selections():
    app = App()
    async with app.run_test() as pilot:
        modal = ChoicePrompt("C2 profiles", ["websocket", "webshell"], mode="multi")
        app.push_screen(modal)
        await pilot.pause()

        choice_list = modal.query_one("#choices", CheckSelectionList)
        choice_list.select("websocket")
        await pilot.pause()
        choice_list.select("webshell")
        await pilot.pause()

        assert set(choice_list.selected) == {"websocket", "webshell"}


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


async def test_select_commands_filter_and_select_all():
    app = App()
    async with app.run_test() as pilot:
        catalog = [{"cmd": "ls"}, {"cmd": "cat"}, {"cmd": "shell"}]
        modal = SelectCommands(catalog)
        app.push_screen(modal)
        await pilot.pause()

        from textual.widgets import Input
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


async def test_select_commands_ok_returns_sorted_selection():
    app = App()
    async with app.run_test() as pilot:
        catalog = [{"cmd": "ls"}, {"cmd": "cat"}]
        modal = SelectCommands(catalog, preselected=["cat"])
        app.push_screen(modal)
        await pilot.pause()

        dismissed = {}
        modal.dismiss = lambda v=None: dismissed.setdefault("value", v)
        modal._ok()
        assert dismissed["value"] == ["cat"]
