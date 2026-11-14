from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from mythic_console.screens.home import Home
from mythic_console.widgets.console import ConsolePanel


def _rebindable_bindings() -> list[Binding]:
    return [binding for binding in Home.BINDINGS if isinstance(binding, Binding)]


class _KeymapScreen(Screen):
    """Carries every one of Home's real rebindable Binding objects, with lightweight
    stand-in actions so the test does not need a fully wired backend."""

    BINDINGS = _rebindable_bindings()

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.console_panel: ConsolePanel | None = None
        self.toggle_sidebar_calls = 0
        self.toggle_log_viewer_calls = 0

    def compose(self) -> ComposeResult:
        self.console_panel = ConsolePanel(instance=self._instance)
        yield self.console_panel

    def action_toggle_sidebar(self) -> None:
        self.toggle_sidebar_calls += 1

    def action_toggle_log_viewer(self) -> None:
        self.toggle_log_viewer_calls += 1


class _Harness(App):
    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.keymap_screen: _KeymapScreen | None = None

    def on_mount(self) -> None:
        self.keymap_screen = _KeymapScreen(self._instance)
        self.push_screen(self.keymap_screen)


async def test_set_keymap_overrides_the_default_key(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.set_keymap({"toggle_sidebar": "ctrl+g"})
        await pilot.pause()

        await pilot.press("ctrl+g")
        await pilot.pause()
        assert app.keymap_screen.toggle_sidebar_calls == 1

        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.keymap_screen.toggle_sidebar_calls == 1


async def test_set_keymap_leaves_unlisted_actions_on_their_default(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.set_keymap({"toggle_sidebar": "ctrl+g"})
        await pilot.pause()

        await pilot.press("f2")
        await pilot.pause()
        assert app.keymap_screen.toggle_log_viewer_calls == 1
