from textual.app import ComposeResult
from textual.containers import Container
from textual.widget import Widget

from textual_console import ConsoleOutput

from mythic_console.utils.logger import get_log_buffer_handler

DRAIN_INTERVAL = 0.25


class LogViewer(Container):
    """Toggleable panel that shows the buffered application log and follows it live."""

    def __init__(self, *children: Widget):
        super().__init__(*children)
        self.border_title = "Log"
        self.console_output = ConsoleOutput()
        self._seen = 0

    def compose(self) -> ComposeResult:
        yield self.console_output

    def on_mount(self) -> None:
        self._drain()
        self.set_interval(DRAIN_INTERVAL, self._drain)

    def _drain(self) -> None:
        total, snapshot = get_log_buffer_handler().drain_state()
        new_count = total - self._seen
        self._seen = total
        if new_count <= 0:
            return
        for line in snapshot[-new_count:]:
            self.console_output.write(line)

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
