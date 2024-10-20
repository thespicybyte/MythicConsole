from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Input, Button, Header, Footer
from textual.worker import Worker

from backend.mythic_instance.mythic_instance import MythicInstance
from utils.environment import Environment
from utils.logger import logger


class LoginPrompt(Widget):
    def compose(self) -> ComposeResult:
        yield Container(
            Vertical(
                Input(placeholder="Username", value=Environment().username(), id="username"),
                Input(placeholder="Password", password=True, value=Environment().password(), id="password"),
                Input(placeholder="Server", id="server", value=Environment().server_url()),
                Button(label="Login", id="login_button"),
                classes="login_box",
            ),
            classes="login_screen",
        )


class LoginScreen(ModalScreen):
    BINDINGS = [
        Binding(key="ctrl+q", description="quit", key_display="^q", tooltip="Exit Program", action="quit")
    ]

    def __init__(self):
        super().__init__()
        self._username = reactive("")
        self._password = reactive("")
        self._server = ""
        self.instance: Optional[MythicInstance] = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield LoginPrompt()
        yield Footer()

    @on(Button.Pressed, "#login_button")
    def login(self):
        self._username = self.query_one("#username", Input).value
        self._password = self.query_one("#password", Input).value
        self._server = self.query_one("#server", Input).value

        if not self._server.removeprefix("https://"):
            self.notify(f"server required", severity="warning")
            return

        if not self._username:
            self.notify(f"user required", severity="warning")
            return

        if not self._password:
            self.notify(f"password required", severity="warning")
            return

        self.query_one(".login_screen").loading = True
        self.instance = MythicInstance(self._username, self._password, self._server)
        self.run_worker(self.instance.login(), exclusive=True)

    def action_quit(self) -> None:
        logger.info("we here")
        print(f"workers: {self.app.workers}")

        self.app.exit(None, 0)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        self.log(event)
        if event.worker.name == "login":
            if not event.worker.is_finished:
                return
            self.query_one(".login_screen").loading = False
            self.dismiss(self.instance)
