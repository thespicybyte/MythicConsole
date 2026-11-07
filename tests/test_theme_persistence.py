import pytest

from mythic_console.console import MythicConsole
from mythic_console.utils import state


@pytest.fixture(autouse=True)
def isolated_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


@pytest.mark.asyncio
async def test_saved_theme_is_restored_at_startup():
    state.set_theme("gruvbox")

    app = MythicConsole()
    async with app.run_test():
        assert app.theme == "gruvbox"


@pytest.mark.asyncio
async def test_unknown_saved_theme_falls_back_to_default():
    state.set_theme("no-such-theme")

    app = MythicConsole()
    async with app.run_test():
        assert app.theme == "textual-dark"
