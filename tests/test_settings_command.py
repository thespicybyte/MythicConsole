import pytest

from mythic_console.console import MythicConsole


@pytest.fixture(autouse=True)
def isolated_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


async def test_get_system_commands_yields_settings_command():
    app = MythicConsole()
    async with app.run_test() as pilot:
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))
        matching = [command for command in commands if command.title == "Settings"]

        assert len(matching) == 1
        assert matching[0].callback == app.action_open_settings


async def test_get_system_commands_does_not_yield_theme_command():
    app = MythicConsole()
    async with app.run_test() as pilot:
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))

        assert not any(command.callback == app.action_change_theme for command in commands)
        assert not any(command.title == "Theme" for command in commands)
