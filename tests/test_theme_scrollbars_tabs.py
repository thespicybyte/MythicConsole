from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.color import Color
from textual.containers import HorizontalScroll, VerticalScroll
from textual.widgets import DataTable, Static, TabPane, Tabs

from widgets.calback_tabs import CallbackTabs
from widgets.callbacks import Callbacks
from widgets.sidebar_module import SidebarModule

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


class _TasksLikeModule(SidebarModule):
    """CSS-equivalent stand-in for TasksTable: a DataTable in a HorizontalScroll inside a
    SidebarModule, which is all that matters for the scrollbar styling under test.

    TasksTable.datatable is a class-level attribute shared by every TasksTable instance,
    so repeatedly instantiating the real class across separate `run_test()` apps (one per
    theme) leaks widget/event-loop state between them. This double builds its DataTable
    per-instance instead, which is the only thing CSS resolution depends on.
    """

    def __init__(self):
        super().__init__()
        self.datatable = DataTable(cursor_type="row", zebra_stripes=True)
        self.datatable.add_column("ID", key="id")

    def compose(self) -> ComposeResult:
        with HorizontalScroll():
            yield self.datatable


class _SidebarTablesHarness(App):
    """Mirrors how Callbacks/TasksTable are sized in the real sidebar (SidebarModule's
    max-height cap), so their DataTables are forced to overflow and scroll."""

    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.callbacks_module: Callbacks | None = None
        self.tasks_module: _TasksLikeModule | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            self.callbacks_module = Callbacks(self._instance)
            yield self.callbacks_module
            self.tasks_module = _TasksLikeModule()
            yield self.tasks_module


def _fill_callback_table(table, count=40):
    for i in range(count):
        table.add_row("*", i, f"host{i}", "poseidon", f"uuid-{i}", "1.2.3.4", "now", key=f"cb{i}")


def _fill_tasks_table(table, count=40):
    for i in range(count):
        table.add_row(i, key=f"task{i}")


@pytest.mark.parametrize("theme", THEMES)
async def test_callback_table_scrollbar_appears_on_overflow(fake_instance, theme):
    app = _SidebarTablesHarness(fake_instance)
    async with app.run_test(size=(100, 50)) as pilot:
        app.theme = theme
        await pilot.pause()
        datatable = app.callbacks_module.datatable
        _fill_callback_table(datatable)
        await pilot.pause()
        assert datatable.show_vertical_scrollbar


@pytest.mark.parametrize("theme", THEMES)
async def test_callback_table_scrollbar_contrasts_with_box(fake_instance, theme):
    app = _SidebarTablesHarness(fake_instance)
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


@pytest.mark.parametrize("theme", THEMES)
async def test_tasks_table_scrollbar_appears_on_overflow(fake_instance, theme):
    app = _SidebarTablesHarness(fake_instance)
    async with app.run_test(size=(100, 50)) as pilot:
        app.theme = theme
        await pilot.pause()
        datatable = app.tasks_module.datatable
        _fill_tasks_table(datatable)
        await pilot.pause()
        assert datatable.show_vertical_scrollbar


@pytest.mark.parametrize("theme", THEMES)
async def test_tasks_table_scrollbar_contrasts_with_box(fake_instance, theme):
    app = _SidebarTablesHarness(fake_instance)
    async with app.run_test(size=(100, 50)) as pilot:
        app.theme = theme
        await pilot.pause()
        datatable = app.tasks_module.datatable
        _fill_tasks_table(datatable)
        await pilot.pause()

        handle = datatable.styles.scrollbar_color
        track = datatable.styles.scrollbar_background
        box_background = datatable.styles.background

        assert handle != track
        assert _contrast(handle, box_background) >= MIN_HANDLE_CONTRAST
