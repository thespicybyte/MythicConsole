from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.color import Color
from textual.containers import VerticalScroll
from textual.widgets import Static, TabPane, Tabs

from widgets.calback_tabs import CallbackTabs
from widgets.callbacks import Callbacks
from widgets.tasks_table import TasksTable

CSS_PATH = Path(__file__).resolve().parent.parent / "mythic.tcss"

THEMES = ["textual-dark", "textual-light", "nord"]

# WCAG relative-luminance contrast ratio; a scrollbar handle needs to clear this
# against the box it sits in or it visually disappears into the background.
MIN_HANDLE_CONTRAST = 2.0


def _contrast(a: Color, b: Color) -> float:
    def luminance(c: Color) -> float:
        def channel(v: int) -> float:
            v = v / 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        return 0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b)

    lighter, darker = sorted((luminance(a), luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


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
        expected = Color.parse(app.get_css_variables()["primary"])
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


class _CallbacksHarness(App):
    """Mirrors how Callbacks is sized in the real sidebar (SidebarModule's max-height
    cap), so its DataTable is forced to overflow and scroll."""

    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.callbacks_module: Callbacks | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            self.callbacks_module = Callbacks(self._instance)
            yield self.callbacks_module


class _TasksTableHarness(App):
    """Mirrors the sizing test_sidebar_tasks_fill.py uses for the real TasksTable: a
    tall spacer above it inside a VerticalScroll, so it's forced to overflow."""

    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.tasks_module: TasksTable | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            spacer = Static("")
            spacer.styles.height = 15
            spacer.styles.margin = 1
            yield spacer
            self.tasks_module = TasksTable(self._instance)
            yield self.tasks_module


def _fill_callback_table(table, count=40):
    for i in range(count):
        table.add_row("*", i, f"host{i}", "poseidon", f"uuid-{i}", "1.2.3.4", "now", key=f"cb{i}")


def _fill_tasks_table(table, count=40):
    for i in range(count):
        table.add_row(i, "operator", "completed", "ls", "", key=f"task{i}")


@pytest.mark.parametrize("theme", THEMES)
async def test_callback_table_scrollbar_appears_on_overflow(fake_instance, theme):
    app = _CallbacksHarness(fake_instance)
    async with app.run_test(size=(100, 50)) as pilot:
        app.theme = theme
        await pilot.pause()
        datatable = app.callbacks_module.datatable
        _fill_callback_table(datatable)
        await pilot.pause()
        assert datatable.show_vertical_scrollbar


@pytest.mark.parametrize("theme", THEMES)
async def test_callback_table_scrollbar_contrasts_with_box(fake_instance, theme):
    app = _CallbacksHarness(fake_instance)
    async with app.run_test(size=(100, 50)) as pilot:
        app.theme = theme
        await pilot.pause()
        datatable = app.callbacks_module.datatable
        _fill_callback_table(datatable)
        await pilot.pause()

        handle = datatable.styles.scrollbar_color
        track = datatable.styles.scrollbar_background
        box_background = datatable.styles.background

        assert handle != track
        assert _contrast(handle, box_background) >= MIN_HANDLE_CONTRAST


async def test_tasks_table_scrollbar_visible_across_themes(fake_instance):
    """Exercises the real TasksTable/DataTable, not a stand-in.

    TasksTable.datatable (widgets/tasks_table.py) is a class-level attribute shared by
    every TasksTable instance. Instantiating TasksTable repeatedly across separate
    `run_test()` apps was confirmed (outside pytest, via a standalone repro script) to
    leave stale layout/scrollbar state behind and produce non-deterministic
    `show_vertical_scrollbar` results on the next instance — unrelated to CSS. A single
    instance, re-themed in place across one `run_test()` run, avoids that and still
    proves the real widget picks up the themed scrollbar colors.
    """
    app = _TasksTableHarness(fake_instance)
    async with app.run_test(size=(100, 50)) as pilot:
        await pilot.pause()
        datatable = app.tasks_module.datatable
        _fill_tasks_table(datatable)
        await pilot.pause()

        for theme in THEMES:
            app.theme = theme
            await pilot.pause()

            assert datatable.show_vertical_scrollbar

            handle = datatable.styles.scrollbar_color
            track = datatable.styles.scrollbar_background
            box_background = datatable.styles.background

            assert handle != track
            assert _contrast(handle, box_background) >= MIN_HANDLE_CONTRAST
