import importlib.resources
import logging

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from mythic_console.screens.home import Home
from mythic_console.screens.prompts import LogLevelMenu
from mythic_console.utils.logger import logger as app_logger
from mythic_console.widgets.console import ConsolePanel
from mythic_console.widgets.log_viewer import DRAIN_INTERVAL, LogViewer, level_style
from mythic_console.widgets.transfer_selection import CheckSelectionList

CSS_PATH = str(importlib.resources.files("mythic_console") / "mythic.tcss")

_LOG_PANEL_ACTIONS = {"toggle_log_viewer", "toggle_log_filter"}


def _log_panel_bindings() -> list[Binding]:
    return [b for b in Home.BINDINGS if isinstance(b, Binding) and b.action in _LOG_PANEL_ACTIONS]


class _LogPanelScreen(Screen):
    """Carries Home's real F2/Ctrl+F Bindings and a real LogViewer child, so this test does
    not need a fully wired Home/Mythic backend."""

    BINDINGS = _log_panel_bindings()

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.console_panel: ConsolePanel | None = None
        self.log_viewer: LogViewer | None = None

    def compose(self) -> ComposeResult:
        self.console_panel = ConsolePanel(instance=self._instance)
        yield self.console_panel
        self.log_viewer = LogViewer()
        self.log_viewer.add_class("-hidden")
        yield self.log_viewer

    def action_toggle_log_viewer(self) -> None:
        self.query_one(LogViewer).toggle()

    def action_toggle_log_filter(self) -> None:
        log_viewer = self.query_one(LogViewer)
        if log_viewer.has_class("-hidden"):
            return
        log_viewer.toggle_filter()


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.log_panel_screen: _LogPanelScreen | None = None

    def on_mount(self) -> None:
        self.log_panel_screen = _LogPanelScreen(self._instance)
        self.push_screen(self.log_panel_screen)


async def test_ctrl_f_shows_and_focuses_filter_then_escape_hides_it(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.log_panel_screen
        await pilot.press("f2")
        await pilot.pause()

        await pilot.press("ctrl+f")
        await pilot.pause()
        assert not screen.log_viewer.filter_input.has_class("-hidden")
        assert app.focused is screen.log_viewer.filter_input

        await pilot.press("escape")
        await pilot.pause()
        assert screen.log_viewer.filter_input.has_class("-hidden")


async def test_ctrl_f_toggles_filter_off_again(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.log_panel_screen
        await pilot.press("f2")
        await pilot.pause()

        await pilot.press("ctrl+f")
        await pilot.pause()
        assert not screen.log_viewer.filter_input.has_class("-hidden")

        await pilot.press("ctrl+f")
        await pilot.pause()
        assert screen.log_viewer.filter_input.has_class("-hidden")


async def test_ctrl_f_does_nothing_when_panel_hidden(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.log_panel_screen
        assert screen.log_viewer.has_class("-hidden")

        await pilot.press("ctrl+f")
        await pilot.pause()
        assert screen.log_viewer.filter_input.has_class("-hidden")


async def test_regex_filter_narrows_lines_live_and_case_insensitively(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.log_panel_screen
        await pilot.press("f2")
        await pilot.pause()

        app_logger.info("zzz-alpha-marker")
        app_logger.info("zzz-beta-marker")
        await pilot.pause(DRAIN_INTERVAL * 2)

        await pilot.press("ctrl+f")
        await pilot.pause()
        screen.log_viewer.filter_input.value = "ALPHA"
        await pilot.pause()

        output = screen.log_viewer.console_output
        assert any("zzz-alpha-marker" in str(line) for line in output.lines)
        assert not any("zzz-beta-marker" in str(line) for line in output.lines)


async def test_invalid_regex_adds_invalid_class_and_does_not_blank_panel(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.log_panel_screen
        await pilot.press("f2")
        await pilot.pause()

        app_logger.info("zzz-stays-visible-marker")
        await pilot.pause(DRAIN_INTERVAL * 2)

        await pilot.press("ctrl+f")
        await pilot.pause()

        filter_input = screen.log_viewer.filter_input
        filter_input.value = "("
        await pilot.pause()

        assert filter_input.has_class("-invalid")
        output = screen.log_viewer.console_output
        assert any("zzz-stays-visible-marker" in str(line) for line in output.lines)


async def test_right_click_opens_level_menu_and_toggles_apply_live(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.log_panel_screen
        await pilot.press("f2")
        await pilot.pause()

        app_logger.debug("zzz-debug-only-marker")
        app_logger.info("zzz-info-only-marker")
        await pilot.pause(DRAIN_INTERVAL * 2)

        output = screen.log_viewer.console_output
        assert not any("zzz-debug-only-marker" in str(line) for line in output.lines)
        assert any("zzz-info-only-marker" in str(line) for line in output.lines)

        await pilot.click(LogViewer, button=3)
        await pilot.pause()
        assert isinstance(app.screen, LogLevelMenu)

        levels = app.screen.query_one("#levels", CheckSelectionList)
        levels.select("DEBUG")
        await pilot.pause()
        assert any("zzz-debug-only-marker" in str(line) for line in output.lines)

        levels.deselect("INFO")
        await pilot.pause()
        assert not any("zzz-info-only-marker" in str(line) for line in output.lines)

        await pilot.press("escape")
        await pilot.pause()


async def test_colored_level_uses_theme_warning_style(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert level_style(logging.WARNING) == app.current_theme.warning


async def test_populated_filtered_colored_panel_screenshot(fake_instance, tmp_path):
    app = _Harness(fake_instance)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = app.log_panel_screen
        await pilot.press("f2")
        await pilot.pause()

        app_logger.debug("screenshot-debug-marker")
        app_logger.info("screenshot-info-marker")
        app_logger.warning("screenshot-warning-marker")
        app_logger.error("screenshot-error-marker")
        await pilot.pause(DRAIN_INTERVAL * 2)

        await pilot.click(LogViewer, button=3)
        await pilot.pause()
        app.screen.query_one("#levels", CheckSelectionList).select("DEBUG")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        path = tmp_path / "log_viewer_filter.svg"
        app.save_screenshot(str(path))
        assert path.exists()
