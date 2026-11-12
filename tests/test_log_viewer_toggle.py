import importlib.resources

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from mythic_console.screens.home import Home
from mythic_console.widgets.console import ConsolePanel
from mythic_console.widgets.log_viewer import LogViewer

CSS_PATH = str(importlib.resources.files("mythic_console") / "mythic.tcss")

_LOG_VIEWER_ACTIONS = {"toggle_log_viewer"}


def _log_viewer_bindings() -> list[Binding]:
    return [b for b in Home.BINDINGS if isinstance(b, Binding) and b.action in _LOG_VIEWER_ACTIONS]


class _LogViewerScreen(Screen):
    """Carries Home's real F2 Binding and a real LogViewer child, so this test does not need a
    fully wired Home/Mythic backend."""

    BINDINGS = _log_viewer_bindings()

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


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.log_viewer_screen: _LogViewerScreen | None = None

    def on_mount(self) -> None:
        self.log_viewer_screen = _LogViewerScreen(self._instance)
        self.push_screen(self.log_viewer_screen)


async def test_f2_reaches_action_through_focused_prompt(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.log_viewer_screen
        screen.console_panel.console_input.focus()
        await pilot.pause()
        assert app.focused is screen.console_panel.console_input
        assert screen.log_viewer.has_class("-hidden")

        await pilot.press("f2")
        await pilot.pause()
        assert not screen.log_viewer.has_class("-hidden")


async def test_toggle_flips_hidden_class(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.log_viewer_screen
        assert screen.log_viewer.has_class("-hidden")

        await pilot.press("f2")
        await pilot.pause()
        assert not screen.log_viewer.has_class("-hidden")

        await pilot.press("f2")
        await pilot.pause()
        assert screen.log_viewer.has_class("-hidden")


async def test_content_and_scroll_position_survive_hide_show(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.log_viewer_screen

        # show first so the widget has a real size and writes render immediately
        # (ConsoleOutput defers rendering while display: none)
        await pilot.press("f2")
        await pilot.pause()
        output = screen.log_viewer.console_output

        for i in range(200):
            output.write(f"marker line {i}")
        await pilot.pause()

        # disable auto-scroll so the drain's own writes (buffered app log noise picked up
        # while shown) can't pull the view back down between the scroll and the assertion
        output.auto_scroll = False
        output.scroll_home(animate=False)
        await pilot.pause()
        scroll_before = output.scroll_offset
        top_line_before = str(output.lines[0])
        assert any("marker line 0" in str(line) for line in output.lines)

        await pilot.press("f2")
        await pilot.pause()
        await pilot.press("f2")
        await pilot.pause()

        assert output.scroll_offset == scroll_before
        assert str(output.lines[0]) == top_line_before
