from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from screens.home import Home
from widgets.console import ConsolePanel

CSS_PATH = Path(__file__).resolve().parent.parent / "mythic.tcss"

_RESIZE_ACTIONS = {"shrink_sidebar", "grow_sidebar"}


def _resize_bindings() -> list[Binding]:
    return [b for b in Home.BINDINGS if isinstance(b, Binding) and b.action in _RESIZE_ACTIONS]


class _ResizeScreen(Screen):
    """Carries Home's real resize Binding objects, with lightweight stand-in actions so the
    test does not need a fully wired Sidebar/Mythic backend."""

    BINDINGS = _resize_bindings()

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.console_panel: ConsolePanel | None = None
        self.shrink_calls = 0
        self.grow_calls = 0

    def compose(self) -> ComposeResult:
        self.console_panel = ConsolePanel(instance=self._instance)
        yield self.console_panel

    def action_shrink_sidebar(self) -> None:
        self.shrink_calls += 1

    def action_grow_sidebar(self) -> None:
        self.grow_calls += 1


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.resize_screen: _ResizeScreen | None = None

    def on_mount(self) -> None:
        self.resize_screen = _ResizeScreen(self._instance)
        self.push_screen(self.resize_screen)


async def test_ctrl_shift_comma_and_full_stop_reach_resize_actions_through_focused_prompt(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.resize_screen.console_panel.console_input.focus()
        await pilot.pause()
        assert app.focused is app.resize_screen.console_panel.console_input

        await pilot.press("ctrl+shift+comma")
        await pilot.pause()
        assert app.resize_screen.shrink_calls == 1
        assert app.resize_screen.grow_calls == 0

        await pilot.press("ctrl+shift+full_stop")
        await pilot.pause()
        assert app.resize_screen.shrink_calls == 1
        assert app.resize_screen.grow_calls == 1


def test_resize_bindings_are_shown_and_alt_arrows_stay_hidden():
    shrink = [b for b in Home.BINDINGS if isinstance(b, Binding) and b.action == "shrink_sidebar"]
    grow = [b for b in Home.BINDINGS if isinstance(b, Binding) and b.action == "grow_sidebar"]

    ctrl_comma = next(b for b in shrink if b.key == "ctrl+shift+comma")
    ctrl_full_stop = next(b for b in grow if b.key == "ctrl+shift+full_stop")
    alt_left = next(b for b in shrink if b.key == "alt+left")
    alt_right = next(b for b in grow if b.key == "alt+right")

    assert ctrl_comma.show is True
    assert ctrl_comma.key_display == "<"
    assert ctrl_full_stop.show is True
    assert ctrl_full_stop.key_display == ">"

    assert alt_left.show is False
    assert alt_right.show is False
