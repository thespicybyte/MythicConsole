from pathlib import Path

from textual.app import App, ComposeResult

from screens.home import _sort_tasks_table
from widgets.tasks_table import TasksTable

CSS_PATH = Path(__file__).resolve().parent.parent / "mythic.tcss"


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.tasks_module: TasksTable | None = None

    def compose(self) -> ComposeResult:
        self.tasks_module = TasksTable(self._instance)
        yield self.tasks_module


async def test_live_task_inserts_in_id_order(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.tasks_module.datatable

        for task_id in (143, 141, 140, 131):
            table.add_row(task_id, "user", "status", "command", "args", key=str(task_id))
        _sort_tasks_table(table)

        table.add_row(144, "user", "status", "command", "args", key="144")
        _sort_tasks_table(table)

        table.add_row(145, "user", "status", "command", "args", key="145")
        _sort_tasks_table(table)

        ids = [table.get_row_at(i)[0] for i in range(table.row_count)]
        assert ids == [145, 144, 143, 141, 140, 131]


async def test_tasks_table_sorts_numerically_not_lexically(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.tasks_module.datatable

        for task_id in (2, 9, 10, 100):
            table.add_row(task_id, "user", "status", "command", "args", key=str(task_id))
        _sort_tasks_table(table)

        ids = [table.get_row_at(i)[0] for i in range(table.row_count)]
        assert ids == [100, 10, 9, 2]
