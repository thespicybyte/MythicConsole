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
