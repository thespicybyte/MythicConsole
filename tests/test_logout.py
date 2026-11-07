import asyncio

import pytest

from mythic_console.console import MythicConsole
from mythic_console.screens.login import LoginScreen


@pytest.fixture(autouse=True)
def isolated_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


@pytest.mark.asyncio
async def test_logout_cancels_workers_and_returns_to_login():
    app = MythicConsole()
    async with app.run_test() as pilot:
        worker = app.run_worker(asyncio.sleep(3600), exclusive=False)
        await pilot.pause()

        app.action_logout()
        await pilot.pause()

        assert isinstance(app.screen, LoginScreen)
        assert worker.is_cancelled
