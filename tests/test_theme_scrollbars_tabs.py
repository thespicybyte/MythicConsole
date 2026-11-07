from pathlib import Path

import pytest
from textual import events
from textual.app import App, ComposeResult
from textual.color import Color
from textual.containers import VerticalScroll
from textual.widgets import Static, TabPane, Tabs

import console
from console import MythicConsole
from widgets.calback_tabs import CallbackTabs
from widgets.callbacks import Callbacks
from widgets.tasks_table import TasksTable

CSS_PATH = Path(__file__).resolve().parent.parent / "mythic.tcss"

THEMES = ["textual-dark", "textual-light", "nord"]

# WCAG relative-luminance contrast ratio; a revealed scrollbar handle needs to clear
# this against the box it sits in or it visually disappears into the background.
MIN_HANDLE_CONTRAST = 2.0


def _contrast(a: Color, b: Color) -> float:
    def luminance(c: Color) -> float:
        def channel(v: int) -> float:
            v = v / 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        return 0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b)

    lighter, darker = sorted((luminance(a), luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class _TabsHarness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.tabs_module: CallbackTabs | None = None

    def compose(self) -> ComposeResult:
        with CallbackTabs(self._instance) as tabs:
            self.tabs_module = tabs
            with TabPane("Mythic", id="home"):
                yield Static("")


@pytest.mark.parametrize("theme", THEMES)
async def test_tab_bar_background_tracks_theme(fake_instance, theme):
    app = _TabsHarness(fake_instance)
    async with app.run_test() as pilot:
        app.theme = theme
        await pilot.pause()
        content_tabs = app.tabs_module.query_one(Tabs)
        surface = Color.parse(app.get_css_variables()["surface"])
        assert content_tabs.styles.background == surface


async def test_tab_bar_background_differs_between_light_and_dark(fake_instance):
    app = _TabsHarness(fake_instance)
    async with app.run_test() as pilot:
        content_tabs = app.tabs_module.query_one(Tabs)

        app.theme = "textual-dark"
        await pilot.pause()
        dark_background = content_tabs.styles.background

        app.theme = "textual-light"
        await pilot.pause()
        light_background = content_tabs.styles.background

        assert dark_background != light_background


class _ScrollHarness(MythicConsole):
    """The real app (so its wheel handling is exercised) composed with the real sidebar
    tables instead of the login flow, each forced to overflow."""

    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.callbacks_module: Callbacks | None = None
        self.tasks_module: TasksTable | None = None
        self.scroll: VerticalScroll | None = None

    def on_mount(self, event: events.Mount) -> None:
        # Skip MythicConsole.on_mount, which pushes the login screen.
        event.prevent_default()

    def compose(self) -> ComposeResult:
        with VerticalScroll() as self.scroll:
            self.callbacks_module = Callbacks(self._instance)
            yield self.callbacks_module
            self.tasks_module = TasksTable(self._instance)
            yield self.tasks_module
            spacer = Static("")
            spacer.styles.height = 100
            yield spacer


async def _run_filled(app: _ScrollHarness, pilot) -> None:
    await pilot.pause()
    for i in range(40):
        app.callbacks_module.datatable.add_row(
            "*", i, f"host{i}", "poseidon", f"uuid-{i}", "100.100.100.100", "streaming", key=f"cb{i}"
        )
        app.tasks_module.datatable.add_row(
            i, "operator", "success", "ps", '{"regex_filter": "something long"}', key=f"task{i}"
        )
    await pilot.pause()


async def _wheel_over(app: App, pilot, widget, event_type=events.MouseScrollDown) -> None:
    x, y = widget.region.x + 2, widget.region.y + 2
    await app.on_event(
        event_type(None, x, y, 0, 0, 0, False, False, False, screen_x=x, screen_y=y)
    )
    await pilot.pause()


def _tables(app: _ScrollHarness):
    return app.callbacks_module.datatable, app.tasks_module.datatable


async def test_scrollbars_take_no_space_at_rest(fake_instance):
    app = _ScrollHarness(fake_instance)
    async with app.run_test(size=(60, 40)) as pilot:
        await _run_filled(app, pilot)
        for widget in (*_tables(app), app.scroll):
            assert widget.show_vertical_scrollbar or widget.show_horizontal_scrollbar
            assert widget.scrollbar_size_vertical == 0
            assert widget.scrollbar_size_horizontal == 0


async def test_wheel_reveals_scrollbar_then_hides_it(fake_instance, monkeypatch):
    monkeypatch.setattr(console, "SCROLLBAR_HIDE_DELAY", 0.1)
    app = _ScrollHarness(fake_instance)
    async with app.run_test(size=(60, 40)) as pilot:
        await _run_filled(app, pilot)
        tasks = app.tasks_module.datatable

        await _wheel_over(app, pilot, tasks)
        assert tasks.has_class("-scrolling")
        assert tasks.scrollbar_size_vertical > 0
        assert tasks.scroll_y > 0

        await pilot.pause(0.3)
        assert not tasks.has_class("-scrolling")
        assert tasks.scrollbar_size_vertical == 0


async def test_shift_wheel_reveals_horizontal_scrollbar(fake_instance, monkeypatch):
    monkeypatch.setattr(console, "SCROLLBAR_HIDE_DELAY", 0.1)
    app = _ScrollHarness(fake_instance)
    async with app.run_test(size=(60, 40)) as pilot:
        await _run_filled(app, pilot)
        callbacks = app.callbacks_module.datatable
        assert callbacks.show_horizontal_scrollbar

        await _wheel_over(app, pilot, callbacks, events.MouseScrollRight)
        assert callbacks.has_class("-scrolling")
        assert callbacks.scrollbar_size_horizontal > 0


async def test_hidden_scrollbar_matches_table_header_and_rows(fake_instance):
    """At rest the scrollbar column is painted, so it has to match everything it sits beside."""
    app = _ScrollHarness(fake_instance)
    async with app.run_test(size=(60, 40)) as pilot:
        await _run_filled(app, pilot)
        for theme in THEMES:
            app.theme = theme
            await pilot.pause()
            for table in _tables(app):
                background = table.styles.background
                header = table.get_component_styles("datatable--header").background
                assert header == background
                assert table.styles.scrollbar_background == background
                assert table.styles.scrollbar_color == background
                assert table.styles.scrollbar_corner_color == background


async def test_revealed_scrollbar_is_themed_and_visible(fake_instance):
    app = _ScrollHarness(fake_instance)
    async with app.run_test(size=(60, 40)) as pilot:
        await _run_filled(app, pilot)
        for table in _tables(app):
            table.add_class("-scrolling")
        await pilot.pause()

        handles = {}
        for theme in THEMES:
            app.theme = theme
            await pilot.pause()
            primary = Color.parse(app.get_css_variables()["primary"])
            for table in _tables(app):
                handle = table.styles.scrollbar_color
                assert handle == primary
                assert handle != table.styles.scrollbar_background
                assert _contrast(handle, table.styles.background) >= MIN_HANDLE_CONTRAST
            handles[theme] = primary

        assert handles["textual-dark"] != handles["textual-light"]
