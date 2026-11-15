import logging
import re
from collections import deque

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.events import MouseUp
from textual.widget import Widget
from textual.widgets import Input, SelectionList

from textual_console import ConsoleOutput

from mythic_console.screens.prompts import LogLevelMenu
from mythic_console.utils.environment import Environment
from mythic_console.utils.logger import BufferedRecord, LOG_BUFFER_MAXLEN, get_log_buffer_handler
from mythic_console.utils.severity import Severity, severity_style

DRAIN_INTERVAL = 0.25

_LEVELS: tuple[tuple[int, str], ...] = (
    (logging.DEBUG, "DEBUG"),
    (logging.INFO, "INFO"),
    (logging.WARNING, "WARNING"),
    (logging.ERROR, "ERROR"),
    (logging.CRITICAL, "CRITICAL"),
)


def level_style(levelno: int) -> str:
    """The Rich style for a level field: dim for DEBUG, neutral for INFO, and the
    active theme's warning/error color for WARNING and ERROR/CRITICAL."""
    if levelno >= logging.ERROR:
        return severity_style(Severity.ERROR)
    if levelno >= logging.WARNING:
        return severity_style(Severity.WARNING)
    if levelno >= logging.INFO:
        return ""
    return "dim"


def render_record(record: BufferedRecord) -> Text:
    """A buffered record rendered as a colored Rich `Text` line."""
    text = Text(f"{record.asctime} - {record.location} - ")
    text.append(record.levelname, style=level_style(record.levelno))
    text.append(f" - {record.message}")
    return text


def default_enabled_levels() -> set[str]:
    """The level names enabled by default: the configured `LOG_LEVEL` and above."""
    configured = Environment().log_level()
    return {name for levelno, name in _LEVELS if levelno >= configured}


class LogFilterInput(Input):
    """Filter input for the log panel. Escape hides it instead of clearing it."""

    BINDINGS = [Binding("escape", "hide", show=False)]

    def __init__(self, log_viewer: "LogViewer", **kwargs):
        super().__init__(**kwargs)
        self._log_viewer = log_viewer

    def action_hide(self) -> None:
        self._log_viewer.hide_filter()


class LogViewer(Container):
    """Toggleable panel that shows the buffered application log and follows it live."""

    def __init__(self, *children: Widget):
        super().__init__(*children)
        self.border_title = "Log"
        self.console_output = ConsoleOutput()
        self.filter_input = LogFilterInput(self, id="log_filter", placeholder="Filter (regex)...")
        self.filter_input.add_class("-hidden")
        self._records: deque[BufferedRecord] = deque(maxlen=LOG_BUFFER_MAXLEN)
        self._seen = 0
        self._enabled_levels: set[str] = default_enabled_levels()
        self._pattern: re.Pattern | None = None

    def compose(self) -> ComposeResult:
        yield self.filter_input
        yield self.console_output

    def on_mount(self) -> None:
        self._drain()
        self.set_interval(DRAIN_INTERVAL, self._drain)
        self.app.theme_changed_signal.subscribe(self, self._on_theme_changed)

    def _on_theme_changed(self, _theme) -> None:
        self._apply_filter()

    def _passes(self, record: BufferedRecord) -> bool:
        if record.levelname not in self._enabled_levels:
            return False
        return self._pattern is None or bool(self._pattern.search(record.plain()))

    def _apply_filter(self) -> None:
        self.console_output.clear()
        for record in self._records:
            if self._passes(record):
                self.console_output.write(render_record(record))

    def _drain(self) -> None:
        total, snapshot = get_log_buffer_handler().drain_state()
        new_count = total - self._seen
        self._seen = total
        if new_count <= 0:
            return
        for record in snapshot[-new_count:]:
            self._records.append(record)
            if self._passes(record):
                self.console_output.write(render_record(record))

    def set_enabled_levels(self, levels) -> None:
        self._enabled_levels = set(levels)
        self._apply_filter()

    @on(MouseUp)
    def _on_mouse_up(self, event: MouseUp) -> None:
        if event.button != 3:
            return
        self.app.push_screen(LogLevelMenu(self._enabled_levels, self.set_enabled_levels))

    @on(Input.Changed, "#log_filter")
    def _filter_changed(self, event: Input.Changed) -> None:
        pattern_text = event.value
        if not pattern_text:
            self._pattern = None
            self.filter_input.remove_class("-invalid")
            self._apply_filter()
            return
        try:
            pattern = re.compile(pattern_text, re.IGNORECASE)
        except re.error:
            self.filter_input.add_class("-invalid")
            return
        self._pattern = pattern
        self.filter_input.remove_class("-invalid")
        self._apply_filter()

    def show_filter(self) -> None:
        self.filter_input.remove_class("-hidden")
        self.filter_input.focus()

    def hide_filter(self) -> None:
        self.filter_input.remove_class("-invalid")
        if self.filter_input.value:
            self.filter_input.value = ""
        else:
            self._pattern = None
        self.filter_input.add_class("-hidden")
        if self.screen.focused is self.filter_input:
            self.screen.set_focus(None)

    def toggle_filter(self) -> bool:
        """Flip filter-input visibility. Returns whether it is now shown."""
        if self.filter_input.has_class("-hidden"):
            self.show_filter()
            return True
        self.hide_filter()
        return False

    def show(self) -> None:
        self.remove_class("-hidden")
        if self.console_output.auto_scroll:
            self.console_output.scroll_end(animate=False)

    def hide(self) -> None:
        self.add_class("-hidden")

    def toggle(self) -> bool:
        """Flip visibility. Returns whether the panel is now shown."""
        if self.has_class("-hidden"):
            self.show()
            return True
        self.hide()
        return False
