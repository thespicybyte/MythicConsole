"""Opt-in Pilot smoke test. Needs a reachable Mythic server + .env (see CLAUDE.md).

Run with `pytest -m live`; deselected by default (pytest.ini's `addopts -m "not live"`).

Deliberately kept to a boot/login smoke only. `Home.execute_cmd` globally swaps
sys.stdout/stderr for the duration of any command execution, which risks clobbering
pytest's capture process-wide if a full command-execution flow were driven here.
Full login -> select callback -> issue command flows are documented as the manual
verification method instead (see mythicconsole-80-dev-verify.md).
"""
import pytest

from console import MythicConsole
from utils.environment import Environment

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def skip_without_live_server():
    if not Environment().server_url() or not Environment().username():
        pytest.skip("MYTHIC_SERVER_URL / MYTHIC_CONSOLE_USER not set; no live Mythic server configured")


async def test_app_boots_to_login_screen():
    app = MythicConsole()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen is not None
