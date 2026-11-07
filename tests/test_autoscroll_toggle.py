import importlib.resources

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import TabPane

from mythic_console.screens.home import Home
from mythic_console.widgets.calback_tabs import CallbackTabs
from mythic_console.widgets.console import ConsolePanel

CSS_PATH = str(importlib.resources.files("mythic_console") / "mythic.tcss")

_AUTOSCROLL_ACTIONS = {"toggle_autoscroll"}


def _autoscroll_bindings() -> list[Binding]:
    return [b for b in Home.BINDINGS if isinstance(b, Binding) and b.action in _AUTOSCROLL_ACTIONS]


class _AutoscrollScreen(Screen):
    """Carries Home's real toggle_autoscroll Binding and mirrors its action, resolving the
    active tab's ConsolePanel through a real CallbackTabs with two tabs."""

    BINDINGS = _autoscroll_bindings()

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.toggle_calls = 0
        self.notifications: list[str] = []

    def compose(self) -> ComposeResult:
        with CallbackTabs(self._instance):
            yield TabPane("one", ConsolePanel(instance=self._instance), id="tab-one")
            yield TabPane("two", ConsolePanel(instance=self._instance), id="tab-two")

    def action_toggle_autoscroll(self) -> None:
        self.toggle_calls += 1
        active_pane = self.query_one(CallbackTabs).active_pane
        if active_pane is None:
            return
        try:
            panel = active_pane.query_one(ConsolePanel)
        except NoMatches:
            return
        enabled = panel.toggle_autoscroll()
        message = f"Autoscroll {'on' if enabled else 'off'}"
        self.notifications.append(message)
        self.notify(message)


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.autoscroll_screen: _AutoscrollScreen | None = None

    def on_mount(self) -> None:
        self.autoscroll_screen = _AutoscrollScreen(self._instance)
        self.push_screen(self.autoscroll_screen)


async def test_ctrl_shift_a_reaches_action_through_focused_prompt(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.autoscroll_screen
        active_panel = screen.query_one(CallbackTabs).active_pane.query_one(ConsolePanel)
        active_panel.console_input.focus()
        await pilot.pause()
        assert app.focused is active_panel.console_input

        await pilot.press("ctrl+shift+a")
        await pilot.pause()
        assert screen.toggle_calls == 1


async def test_toggle_flips_auto_scroll_on_active_panel(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.autoscroll_screen
        active_panel = screen.query_one(CallbackTabs).active_pane.query_one(ConsolePanel)
        assert active_panel.console_output.auto_scroll is True

        await pilot.press("ctrl+shift+a")
        await pilot.pause()
        assert active_panel.console_output.auto_scroll is False

        await pilot.press("ctrl+shift+a")
        await pilot.pause()
        assert active_panel.console_output.auto_scroll is True


async def test_reenable_scrolls_to_newest_line(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.autoscroll_screen
        active_panel = screen.query_one(CallbackTabs).active_pane.query_one(ConsolePanel)

        await pilot.press("ctrl+shift+a")
        await pilot.pause()
        assert active_panel.console_output.auto_scroll is False

        for i in range(200):
            active_panel.write_string(f"line {i}")
        await pilot.pause()

        active_panel.console_output.scroll_home(animate=False)
        await pilot.pause()
        assert active_panel.console_output.is_vertical_scroll_end is False

        await pilot.press("ctrl+shift+a")
        await pilot.pause()
        assert active_panel.console_output.auto_scroll is True
        assert active_panel.console_output.is_vertical_scroll_end is True


async def test_only_active_tab_is_affected(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.autoscroll_screen
        tabs = screen.query_one(CallbackTabs)
        active_panel = tabs.active_pane.query_one(ConsolePanel)
        inactive_pane = next(pane for pane in (tabs.get_pane("tab-one"), tabs.get_pane("tab-two"))
                              if pane is not tabs.active_pane)
        inactive_panel = inactive_pane.query_one(ConsolePanel)

        await pilot.press("ctrl+shift+a")
        await pilot.pause()

        assert active_panel.console_output.auto_scroll is False
        assert inactive_panel.console_output.auto_scroll is True


async def test_toast_shown_with_correct_text(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.autoscroll_screen

        await pilot.press("ctrl+shift+a")
        await pilot.pause()
        await pilot.press("ctrl+shift+a")
        await pilot.pause()

        assert screen.notifications == ["Autoscroll off", "Autoscroll on"]


def test_autoscroll_binding_is_registered_and_shown():
    bindings = [b for b in Home.BINDINGS if isinstance(b, Binding) and b.action == "toggle_autoscroll"]
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.key == "ctrl+shift+a"
    assert binding.show is True
