from typing import Optional

from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input

from backend import MythicInstance
from screens.login import LoginScreen
from screens.home import Home
from utils.logger import logger


class MythicConsole(App, inherit_bindings=False):
    BINDINGS = [("ctrl+q", "exit", "Quit")]
    SCREENS = {
        "login": LoginScreen,
        "home": Home,
    }
    CSS_PATH = "mythic.tcss"

    def __init__(self):
        self.instance: Optional[MythicInstance] = None
        super().__init__()
        self.push_screen(LoginScreen())

    def compose(self) -> ComposeResult:
        self.push_screen(LoginScreen(), callback=self.login_result)
        yield Header()
        yield Footer()

    def action_exit(self) -> None:
        self.app.exit()

    @on(Input.Submitted)
    def _enter(self, event: Input.Submitted):
        logger.info(event.value)

    def login_result(self, instance: MythicInstance):
        if instance.mythic:
            self.instance = instance
            self.push_screen(Home(self.instance))
            return
        self.app.exit()

    def action_logout(self):
        self.app.exit()


if __name__ == "__main__":
    app = MythicConsole()
    app.run()
