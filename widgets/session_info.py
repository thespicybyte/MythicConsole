import json

from textual import on, events
from textual.app import ComposeResult
from textual.events import MouseUp, Timer
from textual.widget import Widget
from textual.widgets import Pretty, Static

from backend import MythicInstance
from widgets.messages import CopyToClipboard


class SessionInfo(Static):

    def __init__(self, instance: MythicInstance, *children: Widget):
        super().__init__(*children)
        self.instance = instance
        self.session_info = {
            "username": self.instance.username,
            "server_url": self.instance.url,
            "current_operation": "",
            "current_operation_id": self.instance.mythic.current_operation_id
        }

        self.border_title = "Session Info"
        self.double_click_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Pretty(self.session_info)

    @on(MouseUp)
    def _on_left_click(self, event: events.MouseUp):
        if event.button != 1:
            return

        if self.double_click_timer is not None:
            self.double_click_timer.reset()
            self._copy_session_info()
        else:
            self.double_click_timer = self.set_timer(
                delay=0.5, callback=self._clear_double_click, name="double_click_timer"
            )

    def _clear_double_click(self) -> None:
        self.consecutive_clicks = 0
        self.double_click_timer = None

    def _copy_session_info(self) -> None:
        content = json.dumps(self.session_info, indent=2)
        message = "Session Information copied to clipboard"
        self.post_message(CopyToClipboard(content, message))
