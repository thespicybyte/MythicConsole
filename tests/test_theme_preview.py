import pytest
from textual.command import CommandPalette

from console import MythicConsole


def _palette_background(app):
    screen = app.screen
    assert isinstance(screen, CommandPalette)
    return screen.query_one("Vertical").styles.background


@pytest.mark.asyncio
async def test_theme_preview_and_restore():
    app = MythicConsole()
    async with app.run_test() as pilot:
        original = app.theme

        app.search_themes()
        await pilot.pause()
        original_background = _palette_background(app)

        await pilot.press(*"nord")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert app.theme == "nord"
        # the open palette itself must visibly repaint, not just app.theme
        assert _palette_background(app) != original_background

        await pilot.press("escape")
        await pilot.pause()
        assert app.theme == original

        app.search_themes()
        await pilot.pause()

        await pilot.press(*"gruvbox")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert _palette_background(app) != original_background
        await pilot.press("enter")
        await pilot.pause()
        assert app.theme == "gruvbox"

        app.search_themes()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.theme == "gruvbox"
        assert app._theme_preview_active is False
