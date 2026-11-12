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

_WORD_WRAP_ACTIONS = {"toggle_word_wrap"}


def _word_wrap_bindings() -> list[Binding]:
    return [b for b in Home.BINDINGS if isinstance(b, Binding) and b.action in _WORD_WRAP_ACTIONS]


class _WordWrapScreen(Screen):
    """Carries Home's real toggle_word_wrap Binding and mirrors its action, resolving the
    active tab's ConsolePanel through a real CallbackTabs with two tabs."""

    BINDINGS = _word_wrap_bindings()

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.toggle_calls = 0
        self.notifications: list[str] = []

    def compose(self) -> ComposeResult:
        with CallbackTabs(self._instance):
            yield TabPane("one", ConsolePanel(instance=self._instance), id="tab-one")
            yield TabPane("two", ConsolePanel(instance=self._instance), id="tab-two")

    def action_toggle_word_wrap(self) -> None:
        self.toggle_calls += 1
        active_pane = self.query_one(CallbackTabs).active_pane
        if active_pane is None:
            return
        try:
            panel = active_pane.query_one(ConsolePanel)
        except NoMatches:
            return
        enabled = panel.toggle_word_wrap()
        message = f"Word wrap {'on' if enabled else 'off'}"
        self.notifications.append(message)
        self.notify(message)


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.word_wrap_screen: _WordWrapScreen | None = None

    def on_mount(self) -> None:
        self.word_wrap_screen = _WordWrapScreen(self._instance)
        self.push_screen(self.word_wrap_screen)


async def test_f3_reaches_action_through_focused_prompt(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.word_wrap_screen
        active_panel = screen.query_one(CallbackTabs).active_pane.query_one(ConsolePanel)
        active_panel.console_input.focus()
        await pilot.pause()
        assert app.focused is active_panel.console_input

        await pilot.press("f3")
        await pilot.pause()
        assert screen.toggle_calls == 1


async def test_toggle_flips_wrap_on_active_panel(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.word_wrap_screen
        active_panel = screen.query_one(CallbackTabs).active_pane.query_one(ConsolePanel)
        assert active_panel.console_output.wrap is False

        await pilot.press("f3")
        await pilot.pause()
        assert active_panel.console_output.wrap is True

        await pilot.press("f3")
        await pilot.pause()
        assert active_panel.console_output.wrap is False


async def test_existing_content_rewraps(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.word_wrap_screen
        active_panel = screen.query_one(CallbackTabs).active_pane.query_one(ConsolePanel)

        active_panel.write_string("x" * 200)
        await pilot.pause()
        lines_before = len(active_panel.console_output.lines)

        await pilot.press("f3")
        await pilot.pause()
        assert active_panel.console_output.wrap is True
        assert len(active_panel.console_output.lines) > lines_before


async def test_toggle_lands_on_newest_line_when_scrolled_up(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.word_wrap_screen
        active_panel = screen.query_one(CallbackTabs).active_pane.query_one(ConsolePanel)

        for i in range(60):
            active_panel.write_string(f"line {i} " + "x" * 200)
        await pilot.pause()

        active_panel.console_output.scroll_to(y=30, animate=False)
        await pilot.pause()
        assert active_panel.console_output.is_vertical_scroll_end is False

        await pilot.press("f3")
        await pilot.pause()

        assert active_panel.console_output.wrap is True
        assert active_panel.console_output.is_vertical_scroll_end is True


async def test_at_bottom_stays_pinned_to_bottom(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.word_wrap_screen
        active_panel = screen.query_one(CallbackTabs).active_pane.query_one(ConsolePanel)

        for i in range(60):
            active_panel.write_string(f"line {i} " + "x" * 200)
        await pilot.pause()
        assert active_panel.console_output.is_vertical_scroll_end is True

        await pilot.press("f3")
        await pilot.pause()

        assert active_panel.console_output.wrap is True
        assert active_panel.console_output.is_vertical_scroll_end is True


async def test_only_active_tab_is_affected(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.word_wrap_screen
        tabs = screen.query_one(CallbackTabs)
        active_panel = tabs.active_pane.query_one(ConsolePanel)
        inactive_pane = next(pane for pane in (tabs.get_pane("tab-one"), tabs.get_pane("tab-two"))
                              if pane is not tabs.active_pane)
        inactive_panel = inactive_pane.query_one(ConsolePanel)

        await pilot.press("f3")
        await pilot.pause()

        assert active_panel.console_output.wrap is True
        assert inactive_panel.console_output.wrap is False


async def test_toast_shown_with_correct_text(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.word_wrap_screen

        await pilot.press("f3")
        await pilot.pause()
        await pilot.press("f3")
        await pilot.pause()

        assert screen.notifications == ["Word wrap on", "Word wrap off"]


def test_word_wrap_binding_is_registered_and_shown():
    bindings = [b for b in Home.BINDINGS if isinstance(b, Binding) and b.action == "toggle_word_wrap"]
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.key == "f3"
    assert binding.show is True
