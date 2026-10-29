from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.color import Color
from textual.containers import VerticalScroll
from textual.widgets import Static, TabPane, Tabs

from widgets.calback_tabs import CallbackTabs

CSS_PATH = Path(__file__).resolve().parent.parent / "mythic.tcss"

THEMES = ["textual-dark", "textual-light", "nord"]


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.tabs_module: CallbackTabs | None = None
        self.scroll: VerticalScroll | None = None

    def compose(self) -> ComposeResult:
        with CallbackTabs(self._instance) as tabs:
            self.tabs_module = tabs
            with TabPane("Mythic", id="home"):
                with VerticalScroll() as self.scroll:
                    spacer = Static("")
                    spacer.styles.height = 50
                    yield spacer


@pytest.mark.parametrize("theme", THEMES)
async def test_tab_bar_background_tracks_theme(fake_instance, theme):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        app.theme = theme
        await pilot.pause()
        content_tabs = app.tabs_module.query_one(Tabs)
        surface = Color.parse(app.get_css_variables()["surface"])
        assert content_tabs.styles.background == surface


async def test_tab_bar_background_differs_between_light_and_dark(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        content_tabs = app.tabs_module.query_one(Tabs)

        app.theme = "textual-dark"
        await pilot.pause()
        dark_background = content_tabs.styles.background

        app.theme = "textual-light"
        await pilot.pause()
        light_background = content_tabs.styles.background

        assert dark_background != light_background


@pytest.mark.parametrize("theme", THEMES)
async def test_scrollbar_color_tracks_theme(fake_instance, theme):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        app.theme = theme
        await pilot.pause()
        expected = Color.parse(app.get_css_variables()["primary"]).with_alpha(0.5)
        assert app.scroll.styles.scrollbar_color == expected


async def test_scrollbar_color_differs_between_light_and_dark(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        app.theme = "textual-dark"
        await pilot.pause()
        dark_color = app.scroll.styles.scrollbar_color

        app.theme = "textual-light"
        await pilot.pause()
        light_color = app.scroll.styles.scrollbar_color

        assert dark_color != light_color
