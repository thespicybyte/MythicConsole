from textual import on
from textual.app import App, ComposeResult

from widgets.callbacks import CallbackTable


class _Harness(App):
    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.table: CallbackTable | None = None
        self.updates: list[CallbackTable.RowUpdated] = []

    def compose(self) -> ComposeResult:
        self.table = CallbackTable(self._instance)
        yield self.table

    def on_mount(self) -> None:
        for i in range(2):
            uuid = f"uuid-{i}"
            self.table.add_row(i, f"host-{i}", "poseidon", uuid, key=uuid)
        self.table.focus()

    @on(CallbackTable.RowUpdated)
    def _capture(self, message: CallbackTable.RowUpdated) -> None:
        self.updates.append(message)


async def _click(table: CallbackTable, pilot, row: int) -> None:
    table.move_cursor(row=row)
    table._left_click()
    await pilot.pause()


async def test_clean_double_click_opens_on_second_click(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await _click(app.table, pilot, 0)
        assert app.updates == []

        await _click(app.table, pilot, 0)
        assert len(app.updates) == 1
        assert app.updates[0].callback_uuid == "uuid-0"


async def test_single_click_does_not_open(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await _click(app.table, pilot, 0)
        await pilot.pause(0.6)
        assert app.updates == []


async def test_second_click_opens_the_row_under_the_cursor(fake_instance):
    """The timer only tracks that a second click landed within the window, not which row
    the first click targeted (same as tasks_table). A second click on a different row opens
    that row rather than being discarded."""
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await _click(app.table, pilot, 0)
        await _click(app.table, pilot, 1)
        assert len(app.updates) == 1
        assert app.updates[0].callback_uuid == "uuid-1"


async def test_reset_selection_clears_guard(fake_instance):
    async with App().run_test():
        table = CallbackTable(fake_instance)
        table.current_row_id = 0
        table.reset_selection()
        assert table.current_row_id is None


async def test_reopen_after_reset_selection(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await _click(app.table, pilot, 0)
        await _click(app.table, pilot, 0)
        assert len(app.updates) == 1

        app.table.reset_selection()
        await pilot.pause(0.6)

        await _click(app.table, pilot, 0)
        await _click(app.table, pilot, 0)
        assert len(app.updates) == 2


async def test_enter_key_opens_and_suppresses_repeat(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        app.table.move_cursor(row=0)
        await pilot.press("enter")
        assert len(app.updates) == 1

        await pilot.press("enter")
        assert len(app.updates) == 1

        app.table.reset_selection()
        await pilot.press("enter")
        assert len(app.updates) == 2
