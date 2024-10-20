from typing import Optional, Callable, Any

from textual.message import Message

from backend import Callback
from utils import ViewMode


class UpdateCurrentCallback(Message):
    def __init__(self, callback_uuid: str | None) -> None:
        self.callback_uuid = callback_uuid
        super().__init__()


class UpdateViewMode(Message):
    def __init__(self, mode: ViewMode) -> None:
        self.view_mode = mode
        super().__init__()


class CloseCurrentTab(Message):
    """Close the current tab"""


class NextTab(Message):
    """Open the next tab"""


class PreviousTab(Message):
    """Open Previous Tab"""


class TabClosed(Message):
    def __init__(self, tab_id: str) -> None:
        self.tab_id = tab_id
        super().__init__()


class ClipboardReady(Message):
    def __init__(
            self, copy: Callable[[Any], None], paste: Callable[[], str]
    ) -> None:
        super().__init__()
        self.copy = copy
        self.paste = paste


class CopyToClipboard(Message):
    def __init__(self, content: str, success_message: Optional[str]):
        self.content = content
        self.success_message = success_message
        super().__init__()
