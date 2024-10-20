import json
from typing import Optional

from textual import events, on, work
from textual.app import ComposeResult
from textual.containers import HorizontalScroll
from textual.events import MouseUp, Timer
from textual.message import Message
from textual.widgets import DataTable
from textual.widgets._data_table import DuplicateKey

from backend import Task, MythicInstance
from widgets import messages
from widgets.sidebar_module import SidebarModule


class ReplayTask(Message):
    def __init__(self, task: Task):
        super().__init__()
        self.task = task


class TasksTable(SidebarModule):
    class NewTask(Message):
        def __init__(self, task: Task):
            self.task = task
            super().__init__()

    datatable = DataTable(cursor_type="row", id="tasks_table", zebra_stripes=True)

    def __init__(self, instance: MythicInstance):
        super().__init__()
        self.instance = instance
        self.border_title = "Tasks"
        self.double_click_timer: Timer | None = None
        self.current_row_id: Optional[int] = None

    def _on_mount(self, event: events.Mount) -> None:
        try:
            self.datatable.add_column("ID", key="id")
            self.datatable.add_column("User", key="user")
            self.datatable.add_column("Status", key="status")
            self.datatable.add_column("Command", key="command")
            self.datatable.add_column("Arguments", key="args")
        except DuplicateKey:
            pass

    def _clear_double_click(self) -> None:
        self.consecutive_clicks = 0
        self.double_click_timer = None

    def compose(self) -> ComposeResult:
        with HorizontalScroll():
            yield self.datatable

    def _copy_task_info(self, task: Task) -> None:
        info = task.__dict__
        del (info["instance"])
        del (info["mythic"])
        del (info["background"])
        del (info["verify_prompt"])
        info = dict(sorted(info.items()))
        content = json.dumps(info, indent=2)
        message = f"Task {task.display_id} Information copied to clipboard"
        self.post_message(messages.CopyToClipboard(content, message))

    async def _get_selected_task(self) -> Task:
        row_index = self.datatable.cursor_row
        row = self.datatable.get_row_at(row_index)
        selected_task_id = row[self.datatable.get_column_index("id")]
        task = Task(self.instance, task_id=selected_task_id)
        worker = self.run_worker(task.query())
        await worker.wait()
        return task

    async def _replay_output(self) -> None:
        task = await self._get_selected_task()
        await task.query()
        if task.completed:
            self.post_message(ReplayTask(task))

        self._clear_double_click()

    @on(MouseUp)
    async def _on_click(self, event: events.MouseUp):
        if event.button == 2:
            return

        if event.button == 3:
            self._right_click()
            return

        self._left_click()

    @work()
    async def _right_click(self):
        task = await self._get_selected_task()
        self._copy_task_info(task)

    @work()
    async def _left_click(self):
        if self.double_click_timer is not None:
            self.double_click_timer.reset()
            await self._replay_output()
        else:
            self.double_click_timer = self.set_timer(
                delay=0.5, callback=self._clear_double_click, name="double_click_timer"
            )
