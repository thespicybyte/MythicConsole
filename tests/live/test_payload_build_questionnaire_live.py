"""Opt-in live Pilot test for the `payload build` questionnaire. Needs a reachable Mythic
server + .env (see CLAUDE.md). Drives the *real* modals (ChoicePrompt/TextPrompt/YesNoPrompt/
SelectCommands) through a live Textual App against the real server's payload-type/C2-profile
introspection, rather than the offline suite's scripted `_prompt` stub.

Run with `pytest -m live`; deselected by default (pytest.ini's `addopts -m "not live"`).

Pre-fills `commands` so the command-set step (and its SelectCommands modal) is skipped --
that step is exercised directly by the offline suite's widget-level tests instead; this test's
job is to prove the real modal chain (OS, filename, build params, C2 profile selection, C2
params, confirm) works end-to-end against a real server's schema.
"""
import asyncio

import pytest
from textual.app import App

from backend.mythic_agent.mythic_agent import MythicCommands
from backend.mythic_instance.mythic_instance import MythicInstance
from screens.prompts import ChoicePrompt, TextPrompt, YesNoPrompt
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
    """A second-attempt value for a TextPrompt whose server-supplied default failed its own
    verifier_regex. Keeps a `scheme://` prefix (several real C2-profile params, e.g.
    websocket's callback_host, require one) and otherwise falls back to a plain alphanumeric
    string, which satisfies every verifier_regex seen on the live test server."""
    if default and "://" in default:
        scheme = default.split("://", 1)[0]
        return f"{scheme}://localhost1"
    return "testvalue1"


def _answer(screen, attempts: dict):
    """A sensible default answer for whichever modal the questionnaire just pushed. A param
    can legitimately re-prompt (advisory required/choices/Number/verifier_regex checks --
    plan §5); a server's own documented default_value isn't guaranteed to satisfy its own
    verifier_regex (seen live: websocket's callback_host default `ws://127.0.0.1` fails its
    `^(ws|wss)://[a-zA-Z0-9]+` regex, since dots aren't in that character class), so a second
    attempt for the same label falls back to a generic value instead of looping on the same
    rejected default forever."""
    if isinstance(screen, TextPrompt):
        attempt = attempts.get(screen.label, 0)
        attempts[screen.label] = attempt + 1
        if attempt == 0 and screen.default:
            return screen.default
        return _fallback_text(screen.default)
    if isinstance(screen, YesNoPrompt):
        return True
    if isinstance(screen, SelectCommands):
        return screen.names[:1]
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
        if isinstance(screen, (ChoicePrompt, TextPrompt, YesNoPrompt, SelectCommands)):
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
    assert config["commands"] == ["ls"]
    assert config["c2_profiles"], "expected at least one C2 profile to be selected"
