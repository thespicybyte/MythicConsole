import pytest

from console import MythicConsole


@pytest.mark.asyncio
async def test_theme_preview_and_restore():
    app = MythicConsole()
    async with app.run_test() as pilot:
        original = app.theme

        app.search_themes()
        await pilot.pause()

        await pilot.press(*"nord")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert app.theme == "nord"

        await pilot.press("escape")
        await pilot.pause()
        assert app.theme == original

        app.search_themes()
        await pilot.pause()

        await pilot.press(*"gruvbox")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.theme == "gruvbox"

        app.search_themes()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.theme == "gruvbox"
        assert app._theme_preview_active is False
