import sys
from enum import Enum
from typing import Iterable, List, Optional

import asyncio
from textual import events
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.dom import DOMNode
from textual.errors import NoWidget
from textual.reactive import var
from textual.screen import Screen
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Header

from mythic_console.backend import MythicInstance
from mythic_console.backend.payload_type.queries import PayloadTypeQueries
from mythic_console.plugins import get_plugin_registry, load_installed_plugins
from mythic_console.screens.home import Home
from mythic_console.screens.login import LoginScreen
from mythic_console.screens.settings import SettingsScreen
from mythic_console.utils import keybindings, state
from mythic_console.utils.logger import logger


class Focus(Enum):
    Input = 1,
    Console = 2,


class State(Enum):
    Login = 1,
    LoggingIn = 2,
    LoginFailed = 3,
    Main = 4,
    Interactive = 5,
    ExtendedInteractive = 6,


VERTICAL_SCROLL_EVENTS = (events.MouseScrollDown, events.MouseScrollUp)
HORIZONTAL_SCROLL_EVENTS = (events.MouseScrollLeft, events.MouseScrollRight)
SCROLLBAR_HIDE_DELAY = 1.0


class MythicConsole(App, inherit_bindings=False):
    authenticated = var(False)
    instance: Optional[MythicInstance] = None

    CSS_PATH = "mythic.tcss"
    SCREENS = {
        "home": Home
    }

    callbacks: List[str] = []

    def __init__(self):
        super().__init__()
        self.state = State.Login
        self._scrollbar_hide_timers: dict[Widget, Timer] = {}
        self.keybinding_overrides: dict[str, str] = {}

    async def on_event(self, event: events.Event) -> None:
        if isinstance(event, VERTICAL_SCROLL_EVENTS + HORIZONTAL_SCROLL_EVENTS) and not event.is_forwarded:
            self._reveal_scrollbars(event)
        await super().on_event(event)

    def _reveal_scrollbars(self, event: events.MouseEvent) -> None:
        """Show the scrollbars of the widget being wheel-scrolled until scrolling stops."""
        try:
            widget, _ = self.screen.get_widget_at(event.screen_x, event.screen_y)
        except NoWidget:
            return

        horizontal = isinstance(event, HORIZONTAL_SCROLL_EVENTS) or event.ctrl or event.shift
        for node in widget.ancestors_with_self:
            if not isinstance(node, Widget):
                break
            if node.allow_horizontal_scroll if horizontal else node.allow_vertical_scroll:
                node.add_class("-scrolling")
                timer = self._scrollbar_hide_timers.get(node)
                if timer is not None:
                    timer.reset()
                else:
                    self._scrollbar_hide_timers[node] = self.set_timer(
                        SCROLLBAR_HIDE_DELAY, lambda: self._hide_scrollbars(node)
                    )
                return

    def _hide_scrollbars(self, widget: Widget) -> None:
        self._scrollbar_hide_timers.pop(widget, None)
        widget.remove_class("-scrolling")

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        for command in super().get_system_commands(screen):
            if command.callback == self.action_change_theme:
                continue
            yield command
        yield SystemCommand("Settings", "Configure key bindings and themes", self.action_open_settings)

    def action_open_settings(self) -> None:
        self.push_screen(SettingsScreen(self.keybinding_overrides), callback=self._handle_settings_result)

    def _handle_settings_result(self, overrides: Optional[dict[str, str]]) -> None:
        if overrides is None:
            return
        self.keybinding_overrides = overrides
        self.set_keymap(overrides)

    def handle_bindings_clash(self, clashed_bindings: set[Binding], node: DOMNode) -> None:
        keys = ", ".join(sorted({binding.key for binding in clashed_bindings}))
        logger.warning(f"key binding clash on {keys}")
        self.notify(f"Key binding clash: {keys}", severity="warning", timeout=10)

    def copy_to_clipboard(self, text: str) -> None:
        super().copy_to_clipboard(text)
        self.notify("Copied to clipboard", timeout=2)

    def watch_authenticated(self) -> None:
        if self.authenticated:
            logger.info("authenticated; pushing Home screen")
            self.push_screen(self.SCREENS["home"](self.instance))

    def on_mount(self):
        logger.info("starting console")
        load_installed_plugins()
        logger.info("installed plugins loaded")
        saved_theme = state.get_theme()
        if saved_theme and saved_theme in self.available_themes:
            self.theme = saved_theme

        overrides, messages = keybindings.load_keymap()
        self.keybinding_overrides = overrides
        self.set_keymap(overrides)
        for message in messages:
            logger.warning(message)
        if messages:
            self.notify("\n".join(messages), severity="warning", timeout=10)

        logger.debug("pushing login screen")
        self.push_screen(LoginScreen(), callback=self.handle_login_response)

    def compose(self) -> ComposeResult:
        yield Header()

    def handle_login_response(self, response: MythicInstance):
        self.instance = response

        err_message = self.instance.get_login_error()
        if err_message:
            logger.warning(f"login failed: {err_message}")
            self.notify(f"login failed: {err_message}", severity="error", timeout=15)
            logger.debug("re-pushing login screen after failure")
            self.push_screen(LoginScreen(), callback=self.handle_login_response)
            return

        logger.info("login succeeded")
        self.notify(f"login success")
        loop = asyncio.get_running_loop()
        if loop:
            self.instance.loop = loop
        self.authenticated = True
        self.run_worker(self._log_plugin_vs_generated_payload_types(), exit_on_error=False)

    async def _log_plugin_vs_generated_payload_types(self):
        try:
            payload_types = await PayloadTypeQueries.query_all_payload_types(self.instance.mythic)
        except Exception as e:
            logger.warning(f"could not query payload types for plugin reconciliation: {e}")
            return

        registry = get_plugin_registry()
        for payload_type in payload_types or []:
            name = payload_type.get("name")
            if not name:
                continue
            if registry.agent_class_for(name) is not None:
                logger.info(f"payload type '{name}': plugin-backed")
            else:
                logger.info(f"payload type '{name}': generated (no plugin installed)")

    def action_logout(self):
        self.authenticated = False
        self.instance = None

        logger.info(f"logout: cancelling {len(self.workers)} workers")
        for worker in self.workers:
            worker.cancel()

        while len(self.screen_stack) > 1:
            logger.debug(self.screen_stack[-1].id)
            self.pop_screen()
        logger.info("logout: returning to login screen")
        self.push_screen(LoginScreen(), callback=self.handle_login_response)


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("install", "plugin"):
        from mythic_console.plugins.cli import run as run_plugin_cli
        sys.exit(run_plugin_cli(argv))

    app = MythicConsole()
    app.run()


if __name__ == '__main__':
    main()
