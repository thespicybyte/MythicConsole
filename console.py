from enum import Enum
from typing import List, Optional

import asyncio
from textual import on
from textual.app import App, ComposeResult
from textual.command import CommandPalette
from textual.reactive import var
from textual.widgets import Header, Footer

from backend import MythicInstance
from screens.home import Home
from screens.login import LoginScreen
from utils.logger import logger


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
        self._theme_preview_active = False
        self._theme_before_preview: Optional[str] = None

    def search_themes(self) -> None:
        self._theme_before_preview = self.theme
        self._theme_preview_active = True
        super().search_themes()

    @on(CommandPalette.OptionHighlighted)
    def _preview_highlighted_theme(self, event: CommandPalette.OptionHighlighted) -> None:
        if not self._theme_preview_active:
            return
        name = event.highlighted_event.option.hit.text
        if name in self.available_themes:
            self.theme = name

    @on(CommandPalette.Closed)
    def _end_theme_preview(self, event: CommandPalette.Closed) -> None:
        if not self._theme_preview_active:
            return
        self._theme_preview_active = False
        if not event.option_selected and self._theme_before_preview is not None:
            self.theme = self._theme_before_preview

    def copy_to_clipboard(self, text: str) -> None:
        super().copy_to_clipboard(text)
        self.notify("Copied to clipboard", timeout=2)

    def watch_authenticated(self) -> None:
        if self.authenticated:
            self.push_screen(self.SCREENS["home"](self.instance))

    def on_mount(self):
        logger.debug("starting console")
        self.push_screen(LoginScreen(), callback=self.handle_login_response)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def handle_login_response(self, response: MythicInstance):
        self.instance = response

        err_message = self.instance.get_login_error()
        logger.debug(err_message)
        if err_message:
            self.notify(f"login failed: {err_message}", severity="error", timeout=15)
            self.push_screen(LoginScreen(), callback=self.handle_login_response)
            return

        self.notify(f"login success")
        loop = asyncio.get_running_loop()
        if loop:
            self.instance.loop = loop
        self.authenticated = True

    def action_logout(self):
        self.authenticated = False
        self.instance = None

        logger.debug(app.workers)
        for worker in app.workers:
            worker.cancel()

        while len(self.screen_stack) > 1:
            logger.debug(self.screen_stack[-1].id)
            self.pop_screen()
        logger.debug(self.screen_stack)
        self.push_screen(LoginScreen(), callback=self.handle_login_response)


if __name__ == '__main__':
    app = MythicConsole()
    app.run()
