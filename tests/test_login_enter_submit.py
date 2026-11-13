import importlib.resources

import pytest
from textual.app import App
from textual.widgets import Input

from mythic_console.backend.mythic_instance.mythic_instance import MythicInstance
from mythic_console.screens.login import LoginScreen

CSS_PATH = str(importlib.resources.files("mythic_console") / "mythic.tcss")


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self):
        super().__init__()
        self.login_screen: LoginScreen | None = None

    def on_mount(self) -> None:
        self.login_screen = LoginScreen()
        self.push_screen(self.login_screen)


@pytest.fixture(autouse=True)
def stub_mythic_login(monkeypatch):
    calls = []

    async def _login(self):
        calls.append(self)
        return True

    monkeypatch.setattr(MythicInstance, "login", _login)
    return calls


@pytest.fixture(autouse=True)
def capture_notifications(monkeypatch):
    notifications = []
    original = LoginScreen.notify

    def _notify(self, message, *args, **kwargs):
        notifications.append((message, kwargs.get("severity")))
        return original(self, message, *args, **kwargs)

    monkeypatch.setattr(LoginScreen, "notify", _notify)
    return notifications


@pytest.mark.parametrize("focused_id", ["#username", "#password", "#server"])
async def test_enter_in_field_submits_when_fields_filled(focused_id, stub_mythic_login):
    app = _Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.login_screen
        screen.query_one("#username", Input).value = "operator"
        screen.query_one("#password", Input).value = "secret"
        screen.query_one("#server", Input).value = "https://mythic.example"

        screen.query_one(focused_id, Input).focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert screen.instance is not None
        assert stub_mythic_login == [screen.instance]


async def test_enter_with_missing_required_field_does_not_submit(stub_mythic_login, capture_notifications):
    app = _Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.login_screen
        screen.query_one("#username", Input).value = ""
        screen.query_one("#password", Input).value = "secret"
        screen.query_one("#server", Input).value = "https://mythic.example"

        screen.query_one("#password", Input).focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert screen.instance is None
        assert stub_mythic_login == []
        assert ("user required", "warning") in capture_notifications


async def test_login_button_still_submits(stub_mythic_login):
    app = _Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.login_screen
        screen.query_one("#username", Input).value = "operator"
        screen.query_one("#password", Input).value = "secret"
        screen.query_one("#server", Input).value = "https://mythic.example"

        await pilot.click("#login_button")
        await pilot.pause()

        assert screen.instance is not None
        assert stub_mythic_login == [screen.instance]
