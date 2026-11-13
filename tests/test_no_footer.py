import types

from textual.app import App, ComposeResult
from textual.widgets import Footer

from mythic_console.screens.home import Home
from mythic_console.screens.login import LoginScreen
from mythic_console.widgets.session_info import SessionInfo


class _LoginHarness(App):
    def compose(self) -> ComposeResult:
        yield from ()

    def on_mount(self) -> None:
        self.push_screen(LoginScreen())


async def test_login_screen_has_no_footer():
    app = _LoginHarness()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.screen.query(Footer)) == 0


class _HomeHarness(App):
    def __init__(self, instance):
        super().__init__()
        self._instance = instance

    def compose(self) -> ComposeResult:
        yield from ()

    def on_mount(self) -> None:
        self.push_screen(Home(self._instance))


async def test_home_screen_has_no_footer(fake_instance, monkeypatch):
    monkeypatch.setattr(Home, "_on_mount", lambda self, event: None)
    monkeypatch.setattr(SessionInfo, "_query_operation", lambda self: None)
    monkeypatch.setattr(SessionInfo, "_query_server_version", lambda self: None)
    fake_instance.mythic = types.SimpleNamespace(current_operation_id=1)
    fake_instance.username = "operator"
    fake_instance.url = "https://mythic.test"
    app = _HomeHarness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.screen.query(Footer)) == 0
