import importlib.resources
import json
import os

import pytest
from textual.app import App
from textual.widgets import Button, Label, OptionList, Static, TabbedContent

from mythic_console.screens.settings import SettingsScreen, _display_id, _set_button_id
from mythic_console.utils import state
from mythic_console.utils.environment import Environment

CSS_PATH = str(importlib.resources.files("mythic_console") / "mythic.tcss")


@pytest.fixture(autouse=True)
def isolated_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, overrides=None):
        super().__init__()
        self._overrides = overrides or {}
        self.result = "pending"

    def on_mount(self) -> None:
        self.push_screen(SettingsScreen(self._overrides), callback=self._set_result)

    def _set_result(self, result) -> None:
        self.result = result


def _display_text(pilot, action_id: str) -> str:
    return pilot.app.screen.query_one(f"#{_display_id(action_id)}", Static).content


async def _click_set(pilot, action_id: str) -> None:
    button = pilot.app.screen.query_one(f"#{_set_button_id(action_id)}", Button)
    button.scroll_visible(animate=False)
    await pilot.pause()
    await pilot.click(button)


async def test_key_bindings_tab_is_active_by_default():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        tabbed = app.screen.query_one(TabbedContent)
        assert tabbed.active == "keybindings"


async def test_capturing_a_key_updates_display_and_saving_writes_file():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await _click_set(pilot, "toggle_sidebar")
        await pilot.pause()
        assert _display_text(pilot, "toggle_sidebar") == "Press keys..."

        await pilot.press("ctrl+g")
        await pilot.pause()
        assert _display_text(pilot, "toggle_sidebar") == "ctrl+g"

        await pilot.click("#save")
        await pilot.pause()

        assert app.result == {"toggle_sidebar": "ctrl+g"}
        with open(Environment().keybindings_file()) as f:
            written = json.load(f)
        assert written == {"toggle_sidebar": "ctrl+g"}


async def test_capturing_full_stop_displays_as_period_and_persists_canonical():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await _click_set(pilot, "toggle_sidebar")
        await pilot.pause()

        await pilot.press("full_stop")
        await pilot.pause()
        assert _display_text(pilot, "toggle_sidebar") == "period"

        await pilot.click("#save")
        await pilot.pause()

        assert app.result == {"toggle_sidebar": "full_stop"}
        with open(Environment().keybindings_file()) as f:
            written = json.load(f)
        assert written == {"toggle_sidebar": "full_stop"}


async def test_capturing_the_reserved_command_palette_key_keeps_old_value_and_shows_error():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await _click_set(pilot, "toggle_sidebar")
        await pilot.pause()

        await pilot.press("ctrl+p")
        await pilot.pause()

        assert _display_text(pilot, "toggle_sidebar") == "ctrl+s"
        error = app.screen.query_one("#error_toggle_sidebar", Label)
        assert "reserved" in error.content.lower()


async def test_saving_a_conflicting_captured_key_shows_inline_error_and_blocks_save():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await _click_set(pilot, "toggle_sidebar")
        await pilot.pause()
        await pilot.press("ctrl+shift+comma")
        await pilot.pause()

        await pilot.click("#save")
        await pilot.pause()

        assert app.result == "pending"
        error = app.screen.query_one("#error_toggle_sidebar", Label)
        assert "conflicts" in error.content.lower()


async def test_escape_cancels_an_active_capture_without_dismissing_the_modal():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await _click_set(pilot, "toggle_sidebar")
        await pilot.pause()
        assert _display_text(pilot, "toggle_sidebar") == "Press keys..."

        await pilot.press("escape")
        await pilot.pause()

        assert app.result == "pending"
        assert _display_text(pilot, "toggle_sidebar") == "ctrl+s"


async def test_escape_dismisses_the_modal_when_no_capture_is_active():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert app.result is None


async def test_starting_a_new_capture_cancels_the_previous_one():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await _click_set(pilot, "toggle_sidebar")
        await pilot.pause()
        assert _display_text(pilot, "toggle_sidebar") == "Press keys..."

        await _click_set(pilot, "manage_callbacks")
        await pilot.pause()

        assert _display_text(pilot, "toggle_sidebar") == "ctrl+s"
        assert _display_text(pilot, "manage_callbacks") == "Press keys..."


async def test_cancel_returns_none_and_writes_no_file():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await _click_set(pilot, "toggle_sidebar")
        await pilot.pause()
        await pilot.press("ctrl+g")
        await pilot.pause()

        await pilot.click("#cancel")
        await pilot.pause()

        assert app.result is None
        assert not os.path.isfile(Environment().keybindings_file())


async def test_panel_prefills_from_existing_overrides():
    app = _Harness(overrides={"toggle_sidebar": "ctrl+g"})
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        assert _display_text(pilot, "toggle_sidebar") == "ctrl+g"


async def test_navigating_the_themes_tab_previews_a_theme_live():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one(TabbedContent).active = "themes"
        await pilot.pause()

        theme_list = app.screen.query_one("#theme-list", OptionList)
        theme_names = sorted(app.available_themes)
        start_index = theme_list.get_option_index(app.theme)
        expected = theme_names[(start_index + 1) % len(theme_names)]

        theme_list.focus()
        await pilot.press("down")
        await pilot.pause()

        assert app.theme == expected


async def test_activating_a_theme_commits_it_and_it_survives_cancel():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        app.screen.query_one(TabbedContent).active = "themes"
        await pilot.pause()

        theme_list = app.screen.query_one("#theme-list", OptionList)
        theme_list.highlighted = theme_list.get_option_index("nord")
        await pilot.pause()
        theme_list.action_select()
        await pilot.pause()

        assert app.theme == "nord"
        assert state.get_theme() == "nord"

        await pilot.click("#cancel")
        await pilot.pause()
        assert app.theme == "nord"


async def test_dismissing_without_activating_reverts_theme_to_baseline():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        original = app.theme
        app.screen.query_one(TabbedContent).active = "themes"
        await pilot.pause()

        theme_list = app.screen.query_one("#theme-list", OptionList)
        other = next(name for name in sorted(app.available_themes) if name != original)
        theme_list.highlighted = theme_list.get_option_index(other)
        await pilot.pause()
        assert app.theme == other

        await pilot.click("#cancel")
        await pilot.pause()

        assert app.theme == original
        assert state.get_theme() is None


async def test_ctrl_s_saves_the_same_diffs_as_the_save_button():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await _click_set(pilot, "toggle_sidebar")
        await pilot.pause()
        await pilot.press("ctrl+g")
        await pilot.pause()

        await pilot.press("ctrl+s")
        await pilot.pause()

        assert app.result == {"toggle_sidebar": "ctrl+g"}
        with open(Environment().keybindings_file()) as f:
            written = json.load(f)
        assert written == {"toggle_sidebar": "ctrl+g"}


async def test_ctrl_x_cancels_and_reverts_a_previewed_theme():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        original = app.theme
        app.screen.query_one(TabbedContent).active = "themes"
        await pilot.pause()

        theme_list = app.screen.query_one("#theme-list", OptionList)
        other = next(name for name in sorted(app.available_themes) if name != original)
        theme_list.highlighted = theme_list.get_option_index(other)
        await pilot.pause()
        assert app.theme == other

        await pilot.press("ctrl+x")
        await pilot.pause()

        assert app.result is None
        assert app.theme == original
        assert not os.path.isfile(Environment().keybindings_file())


async def test_ctrl_r_resets_fields_to_defaults():
    app = _Harness(overrides={"toggle_sidebar": "ctrl+g"})
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        assert _display_text(pilot, "toggle_sidebar") == "ctrl+g"

        await pilot.press("ctrl+r")
        await pilot.pause()

        assert _display_text(pilot, "toggle_sidebar") == "ctrl+s"


async def test_a_hotkey_pressed_during_capture_is_captured_instead_of_firing():
    app = _Harness()
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        await _click_set(pilot, "manage_callbacks")
        await pilot.pause()

        await pilot.press("ctrl+r")
        await pilot.pause()

        assert app.result == "pending"
        assert _display_text(pilot, "manage_callbacks") == "ctrl+r"
