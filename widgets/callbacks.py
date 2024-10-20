import json
from typing import Optional

from textual import events, on, work
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DataTable
from textual.events import Click, MouseUp, Timer, Key

from backend import Callback, MythicInstance
from utils.logger import logger
from widgets.messages import CopyToClipboard
from widgets.sidebar_module import SidebarModule


class CallbackTable(DataTable):
    class RowUpdated(Message):
        def __init__(self, row_key: str, callback_uuid: str):
            super().__init__()
            self.row_key = row_key
            self.callback_uuid = callback_uuid

    headers = ("ID", "Hostname", "Payload", "UUID")
    current_tab_id: reactive[str | None] = reactive(None)

    def __init__(self, instance: MythicInstance):
        super().__init__(cursor_type="row", id="callback_table", zebra_stripes=True, show_cursor=False)
        self.instance = instance
        self.double_click_timer: Timer | None = None
        self.first_click = -1
        self.current_row_id: Optional[int] = None
        self.add_column("ID", key="id")
        self.add_column("Hostname", key="hostname")
        self.add_column("Payload", key="payload")
        self.add_column("UUID", key="uuid", width=8)

    def _copy_callback_info(self, callback: Callback) -> None:
        info = callback.__dict__
        del (info["instance"])
        del (info["mythic"])
        del (info["config_path"])
        del (info["tasks"])
        del (info["extra_info"])
        del (info["sleep_info"])
        del (info["timestamp"])
        del (info["console_panel"])
        info = dict(sorted(info.items()))
        content = json.dumps(info, indent=2)
        message = f"Callback {callback.display_id} Information copied to clipboard"
        self.post_message(CopyToClipboard(content, message))

    def _clear_double_click(self) -> None:
        self.double_click_timer = None
        self.first_click = -1

    def _post_new_row_selected(self):
        """
        Whenever a new row is selected (double-clicked or user pressed enter),
        post the updated row
        """
        row_index = self.cursor_row
        cursor_coordinate = self.cursor_coordinate
        row_key, _ = self.coordinate_to_cell_key(cursor_coordinate)
        row = self.get_row_at(row_index)
        callback_uuid = row[self.get_column_index("uuid")]
        self.post_message(self.RowUpdated(row_key=row_key, callback_uuid=callback_uuid))

    def watch_current_tab_id(self) -> None:
        """
        Responsible for moving the cursor
        """
        if not self.current_tab_id:
            self.show_cursor = False
            return

        logger.debug(f"new current tab id: {self.current_tab_id}")
        self.show_cursor = True
        index = self.get_row_index(row_key=self.current_tab_id)
        self.move_cursor(row=index)

    @on(MouseUp)
    async def _on_click(self, event: events.MouseUp):
        if event.button == 2:
            return

        if event.button == 3:
            self._right_click()
            return

        self._left_click()

    @on(Click)
    def _show_cursor(self) -> None:
        self.show_cursor = True

        if not self.current_tab_id:
            return

        index = self.get_row_index(row_key=self.current_tab_id)
        self.move_cursor(row=index)

    @on(Key)
    def action_row_selected(self, event: events.Key):
        if event.key == "enter":
            row_index = self.cursor_row
            # row has not changed, don't post
            if self.current_row_id == row_index:
                return

            self.current_row_id = row_index
            logger.debug(f"enter hit on {row_index}")
            self._post_new_row_selected()

    @work()
    async def get_selected_callback(self) -> Callback:
        """
        Based on the location of the cursor, return a callback object based on the index in the table
        """
        row_index = self.cursor_row
        row = self.get_row_at(row_index)
        selected_cb_uuid = row[self.get_column_index("uuid")]
        callback = Callback(self.instance, callback_uuid=selected_cb_uuid)
        worker = self.run_worker(callback.query())
        await worker.wait()
        return callback

    @work()
    async def _right_click(self) -> None:
        """
        Copy selected callback to clipboard
        """
        worker = self.get_selected_callback()
        await worker.wait()
        callback = worker.result
        self._copy_callback_info(callback)

    @work()
    async def _left_click(self) -> None:
        """
        If user double-clicks a row in the callbacks table, post message that a callback was selected
        """

        row_clicked = self.cursor_row

        if self.double_click_timer is not None:
            self.double_click_timer.reset()
            if self.first_click < 0:
                self.first_click = row_clicked
                return

            if self.first_click != row_clicked:
                self._clear_double_click()
                return

            # row has not changed, don't post
            if self.current_row_id == row_clicked:
                return

            self.current_row_id = row_clicked
            self._post_new_row_selected()
        else:
            self.double_click_timer = self.set_timer(delay=0.5,
                                                     callback=self._clear_double_click,
                                                     name="double_click_timer")
            if not self.first_click:
                self.first_click = row_clicked


class Callbacks(SidebarModule):
    def __init__(self, instance: MythicInstance):
        super().__init__()
        self.border_title = "Callbacks"
        self.datatable = CallbackTable(instance=instance)

    def compose(self) -> ComposeResult:
        yield self.datatable
