"""Opt-in live Pilot test for the `payload build` questionnaire. Needs a reachable Mythic
server + .env (see CLAUDE.md). Drives the *real* modals (ParamForm/ChoicePrompt/YesNoPrompt/
SelectCommands) through a live Textual App against the real server's payload-type/C2-profile
introspection, rather than the offline suite's scripted `_prompt` stub.

Run with `pytest -m live`; deselected by default (pytest.ini's `addopts -m "not live"`).

Pre-fills `commands` so the command-set step opens in custom mode with `ls` pre-checked and the
default-mode OK path is taken -- that step's mode switching is exercised directly by the offline
suite's widget-level tests instead; this test's job is to prove the real modal chain (payload
form, C2 profile selection, C2 params, confirm) works end-to-end against a real server's schema,
and that the profile-selection modal only offers the payload type's supported profiles.
"""
import asyncio

import pytest
from textual.app import App
from textual.widgets import Checkbox, Input, Label, Select, TextArea

from backend.mythic_agent.mythic_agent import MythicCommands
from backend.mythic_instance.mythic_instance import MythicInstance
from screens.forms import ParamForm
from screens.prompts import ChoicePrompt, YesNoPrompt
from screens.select_commands import SelectCommands
from utils.environment import Environment

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def skip_without_live_server():
    if not Environment().server_url() or not Environment().username():
        pytest.skip("MYTHIC_SERVER_URL / MYTHIC_CONSOLE_USER not set; no live Mythic server configured")


async def _login() -> MythicInstance:
    instance = MythicInstance(Environment().username(), Environment().password(), Environment().server_url())
    assert await instance.login(), instance.get_login_error()
    return instance


def _fallback_text(default: str) -> str:
    """A second-attempt value for a field whose server-supplied default failed its own
    verifier_regex. Keeps a `scheme://` prefix (several real C2-profile params, e.g.
    websocket's callback_host, require one) and otherwise falls back to a plain alphanumeric
    string, which satisfies every verifier_regex seen on the live test server."""
    if default and "://" in default:
        scheme = default.split("://", 1)[0]
        return f"{scheme}://localhost1"
    return "testvalue1"


def _fill_param_form(modal: ParamForm, attempts: dict) -> None:
    """Fill a real ParamForm's fields with values that should satisfy their schema. Only a
    field that is currently blank (first pass) or still flagged with an error (a retry after a
    failed submit) is touched -- a field that already passed validation is left alone, so a
    generic fallback for one field's retry can't accidentally invalidate another field's
    already-valid default."""
    for index, spec in enumerate(modal.specs):
        error_id = f"#{ParamForm._error_id(index)}"
        key = (id(modal), spec.name)
        has_error = str(modal.query_one(error_id, Label).content) != ""
        if attempts.get(key, 0) > 0 and not has_error:
            continue

        widget_id = f"#{ParamForm._field_id(index)}"
        attempt = attempts.get(key, 0)
        attempts[key] = attempt + 1

        if spec.parameter_type == "Boolean":
            modal.query_one(widget_id, Checkbox).value = True
        elif spec.parameter_type == "ChooseOne":
            if spec.choices:
                modal.query_one(widget_id, Select).value = spec.choices[0]
        elif spec.parameter_type == "ChooseMultiple":
            pass  # optional in every live schema seen; leave unselected
        elif spec.parameter_type in ("Array", "TypedArray"):
            modal.query_one(widget_id, TextArea).text = "one" if spec.required else ""
        elif spec.parameter_type == "Dictionary":
            modal.query_one(widget_id, TextArea).text = "{}" if spec.required else ""
        elif spec.parameter_type == "File":
            pass  # no required File params in the live schemas exercised here
        else:
            default = str(spec.initial) if spec.initial is not None else ""
            value = default if attempt == 0 and default else _fallback_text(default)
            modal.query_one(widget_id, Input).value = value


def _answer(screen, attempts: dict):
    """A sensible default answer for whichever modal the questionnaire just pushed."""
    if isinstance(screen, ParamForm):
        _fill_param_form(screen, attempts)
        return screen._submit()
    if isinstance(screen, YesNoPrompt):
        return True
    if isinstance(screen, SelectCommands):
        return None
    if isinstance(screen, ChoicePrompt):
        if not screen.choices:
            return None
        return screen.choices[0] if screen.mode == "single" else screen.choices[:1]
    return None


async def _drive_to_completion(app, pilot, worker) -> None:
    """Answer each real modal the questionnaire pushes until the worker finishes.
    `push_screen_wait` requires a Textual worker context (not a bare asyncio task), so the
    questionnaire coroutine must run via `app.run_worker`, same as production (home.py)."""
    attempts: dict = {}
    seen = 0
    while not worker.is_finished:
        await pilot.pause()
        screen = app.screen
        if isinstance(screen, ParamForm):
            # ParamForm dismisses itself (via its own validation) rather than returning a
            # plain value for us to dismiss with.
            _answer(screen, attempts)
            seen += 1
            await pilot.pause()
        elif isinstance(screen, (ChoicePrompt, YesNoPrompt, SelectCommands)):
            screen.dismiss(_answer(screen, attempts))
            seen += 1
            await pilot.pause()
        else:
            await asyncio.sleep(0.05)
        assert seen < 50, "too many modal steps; questionnaire likely looping"


async def test_questionnaire_walks_real_modals_against_live_server():
    instance = await _login()
    if not instance.mythic.current_operation_id:
        pytest.skip("no current operation set for this account on the test server")

    commands = MythicCommands(instance)
    app = App()
    async with app.run_test() as pilot:
        worker = app.run_worker(
            commands._payload_build_questionnaire("poseidon", {"commands": ["ls"]}),
            exclusive=False, exit_on_error=False)
        await _drive_to_completion(app, pilot, worker)
        await worker.wait()
        config = worker.result

    assert config is not None, "questionnaire was unexpectedly cancelled"
    assert config["payload_type"] == "poseidon"
    assert config["selected_os"] in ("Linux", "macOS")
    assert config["filename"]
    assert config["c2_profiles"], "expected at least one C2 profile to be selected"


async def test_profile_selection_offers_only_supported_profiles():
    """poseidon's `payloadtypec2profiles` join on the live test server is `websocket`/`webshell`
    (narrower than its full declared `supported_c2`); the selection modal must offer only those."""
    instance = await _login()
    if not instance.mythic.current_operation_id:
        pytest.skip("no current operation set for this account on the test server")

    from backend.payload_type.queries import PayloadTypeQueries
    supported = await PayloadTypeQueries.query_supported_c2_profiles(instance.mythic, "poseidon")

    names = {p["name"] for p in supported["profiles"]}
    assert names == {"websocket", "webshell"}
    assert isinstance(supported["supports_multiple"], bool)
