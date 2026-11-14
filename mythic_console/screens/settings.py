from typing import Optional

from textual import events, on
from textual.actions import SkipAction
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, Static, TabbedContent, TabPane
from textual.widgets.option_list import Option, OptionDoesNotExist

from mythic_console.utils import state
from mythic_console.utils.keybindings import (
    ACTIONS_BY_ID,
    REBINDABLE_ACTIONS,
    RebindableAction,
    diff_from_defaults,
    effective_keymap,
    find_conflicts,
    is_reserved_key,
    is_valid_key,
    save_overrides,
)

_SET_PREFIX = "set_"
_CAPTURE_PROMPT = "Press keys..."
_KEY_DISPLAY_NAMES = {"full_stop": "period"}


def _display_id(action_id: str) -> str:
    return f"keydisplay_{action_id}"


def _set_button_id(action_id: str) -> str:
    return f"{_SET_PREFIX}{action_id}"


def _error_id(action_id: str) -> str:
    return f"error_{action_id}"


def _display_key(key: str) -> str:
    """Operator-facing rendering of a stored key string. Display only; the stored and
    bound value is always the canonical Textual key string."""
    *modifiers, final = key.split("+")
    return "+".join([*modifiers, _KEY_DISPLAY_NAMES.get(final, final)])


class SettingsScreen(ModalScreen):
    """Tabbed settings panel reached from the command palette: Key Bindings (each row's
    key is set by capturing the next key press rather than typing a key name) and
    Themes (a live-previewing theme picker). Key Bindings is first and active by
    default. Returns the id -> key override map (entries differing from the registry
    defaults) on Save, or None on Cancel; theme selection applies immediately and is
    independent of Save/Cancel, except that a merely-previewed (not committed) theme
    reverts on any dismissal."""

    BINDINGS = [
        Binding(key="escape", action="cancel", description="cancel", show=False),
        Binding(key="ctrl+s", action="save", description="save", show=False),
        Binding(key="ctrl+x", action="cancel", description="cancel", show=False),
        Binding(key="ctrl+r", action="reset", description="reset", show=False),
    ]

    def __init__(self, overrides: dict[str, str]):
        super().__init__()
        self._initial = effective_keymap(overrides)
        self._values: dict[str, str] = dict(self._initial)
        self._capturing: Optional[str] = None
        self._original_command_palette_action = None
        self._theme_baseline: Optional[str] = None

    def on_mount(self) -> None:
        """The command palette binding is priority-level and fires before any key event
        reaches this screen, so a captured ctrl+p never reaches on_key. Shadow the
        app's action for the life of this screen and only intercept while capturing."""
        self._original_command_palette_action = self.app.action_command_palette
        self.app.action_command_palette = self._guard_command_palette

        self._theme_baseline = self.app.theme
        theme_list = self.query_one("#theme-list", OptionList)
        try:
            theme_list.highlighted = theme_list.get_option_index(self._theme_baseline)
        except OptionDoesNotExist:
            pass

    def _guard_command_palette(self) -> None:
        if self._capturing is not None:
            raise SkipAction()
        self._original_command_palette_action()

    def _restore_command_palette(self) -> None:
        if self._original_command_palette_action is not None:
            self.app.action_command_palette = self._original_command_palette_action
            self._original_command_palette_action = None

    def compose(self) -> ComposeResult:
        rows = []
        last_group: Optional[str] = None
        for action in REBINDABLE_ACTIONS:
            if action.group != last_group:
                rows.append(Static(action.group, classes="form-section"))
                last_group = action.group
            rows.append(self._compose_row(action))

        with Container(id="settings-panel"):
            yield Label("Settings", id="settings-title")
            with TabbedContent(id="settings-tabs"):
                with TabPane("Key Bindings", id="keybindings"):
                    yield VerticalScroll(*rows, id="keybindings-fields")
                with TabPane("Themes", id="themes"):
                    yield OptionList(*self._theme_options(), id="theme-list")
            yield Horizontal(
                Button(label="Reset to defaults", variant="warning", id="reset"),
                Button(label="Save", variant="success", id="save"),
                Button(label="Cancel", variant="error", id="cancel"),
                id="settings-buttons",
            )

    def _compose_row(self, action: RebindableAction) -> Container:
        return Container(
            Horizontal(
                Label(action.label, classes="keybinding-label"),
                Static(
                    _display_key(self._values[action.id]),
                    id=_display_id(action.id),
                    classes="keybinding-key-display",
                ),
                Button(
                    label="Set",
                    id=_set_button_id(action.id),
                    classes="keybinding-set-button",
                ),
                classes="keybinding-input-row",
            ),
            Label("", id=_error_id(action.id), classes="field-error"),
            classes="keybinding-row",
        )

    def _theme_options(self) -> list[Option]:
        return [Option(name, id=name) for name in sorted(self.app.available_themes)]

    @on(OptionList.OptionHighlighted, "#theme-list")
    def _preview_theme(self, event: OptionList.OptionHighlighted) -> None:
        name = event.option.id
        if name and name in self.app.available_themes:
            self.app.theme = name
            # App.refresh_css skips the topmost screen; restyle this modal here.
            self.call_next(self._restyle_self)

    def _restyle_self(self) -> None:
        if self.is_mounted:
            self.app.stylesheet.update(self, animate=False)

    @on(OptionList.OptionSelected, "#theme-list")
    def _commit_theme(self, event: OptionList.OptionSelected) -> None:
        name = event.option.id
        if name:
            state.set_theme(name)
            self._theme_baseline = name

    def _revert_theme_to_baseline(self) -> None:
        if self._theme_baseline is not None and self.app.theme != self._theme_baseline:
            self.app.theme = self._theme_baseline

    def _set_error(self, action_id: str, message: str) -> None:
        self.query_one(f"#{_error_id(action_id)}", Label).update(message)

    def _update_display(self, action_id: str) -> None:
        self.query_one(f"#{_display_id(action_id)}", Static).update(_display_key(self._values[action_id]))

    def _begin_capture(self, action_id: str) -> None:
        if self._capturing is not None:
            self._cancel_capture()
        self._capturing = action_id
        self._set_error(action_id, "")
        self.query_one(f"#{_display_id(action_id)}", Static).update(_CAPTURE_PROMPT)

    def _cancel_capture(self) -> None:
        if self._capturing is None:
            return
        action_id = self._capturing
        self._capturing = None
        self._update_display(action_id)

    def _apply_captured_key(self, key: str) -> None:
        action_id = self._capturing
        self._capturing = None
        if is_reserved_key(key):
            self._update_display(action_id)
            self._set_error(action_id, "reserved for the command palette")
            return
        self._values[action_id] = key
        self._update_display(action_id)
        self._set_error(action_id, "")

    def on_key(self, event: events.Key) -> None:
        if self._capturing is None:
            return
        event.stop()
        event.prevent_default()
        if event.key == "escape":
            self._cancel_capture()
            return
        self._apply_captured_key(event.key)

    @on(Button.Pressed, ".keybinding-set-button")
    def _start_capture(self, event: Button.Pressed) -> None:
        action_id = event.button.id[len(_SET_PREFIX):]
        self._begin_capture(action_id)

    @staticmethod
    def _validate(key: str) -> Optional[str]:
        if not is_valid_key(key):
            return "invalid key"
        if is_reserved_key(key):
            return "reserved for the command palette"
        return None

    @on(Button.Pressed, "#save")
    def _save(self) -> None:
        self._cancel_capture()

        values = dict(self._values)
        errors: dict[str, str] = {}
        for action in REBINDABLE_ACTIONS:
            error = self._validate(values[action.id])
            if error:
                errors[action.id] = error

        valid_values = {action_id: key for action_id, key in values.items() if action_id not in errors}
        conflicts = find_conflicts(valid_values)
        for action_id, clashing_id in conflicts.items():
            errors.setdefault(action_id, f"conflicts with '{ACTIONS_BY_ID[clashing_id].label}'")

        first_error: Optional[str] = None
        for action in REBINDABLE_ACTIONS:
            message = errors.get(action.id, "")
            self._set_error(action.id, message)
            if message and first_error is None:
                first_error = action.id

        if first_error is not None:
            widget = self.query_one(f"#{_set_button_id(first_error)}", Button)
            widget.scroll_visible()
            widget.focus()
            return

        overrides = diff_from_defaults(values)
        save_overrides(overrides)
        self._restore_command_palette()
        self._revert_theme_to_baseline()
        self.dismiss(overrides)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self._cancel_capture()
        self._restore_command_palette()
        self._revert_theme_to_baseline()
        self.dismiss(None)

    @on(Button.Pressed, "#reset")
    def _reset(self) -> None:
        self._cancel_capture()
        for action in REBINDABLE_ACTIONS:
            self._values[action.id] = action.default_key
            self._update_display(action.id)
            self._set_error(action.id, "")

    def action_cancel(self) -> None:
        self._restore_command_palette()
        self._revert_theme_to_baseline()
        self.dismiss(None)

    def action_save(self) -> None:
        self._save()

    def action_reset(self) -> None:
        self._reset()
