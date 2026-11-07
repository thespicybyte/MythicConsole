import json
import types
from datetime import datetime, timezone

from textual import on
from textual.app import App, ComposeResult

from utils.callback_status import STATUS_GLYPHS, STREAMING_SENTINEL
from widgets.callbacks import CallbackTable, build_callback_row

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _fake_callback(uuid, active=True, dead=False, last_checkin="2024-01-01T00:00:00",
                    sleep_info=None, display_id=1, hostname="host", payload_type_name="poseidon",
                    ip=None, external_ip=None):
    return types.SimpleNamespace(
        uuid=uuid, active=active, dead=dead, last_checkin=last_checkin, sleep_info=sleep_info,
        display_id=display_id, hostname=hostname, payload_type_name=payload_type_name,
        ip=ip if ip is not None else ["10.0.0.1"], external_ip=external_ip,
    )


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
            cb = _fake_callback(uuid, display_id=i, hostname=f"host-{i}")
            self.table.add_row(*build_callback_row(cb, NOW), key=uuid)
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


async def test_new_columns_present_by_key(fake_instance):
    async with App().run_test():
        table = CallbackTable(fake_instance)
        for key, expected_index in (
            ("status", 0), ("id", 1), ("hostname", 2), ("payload", 3),
            ("uuid", 4), ("ip", 5), ("checkin", 6),
        ):
            assert table.get_column_index(key) == expected_index


def test_build_callback_row_status_glyphs():
    sleep_info = json.dumps({"http": {"interval": 10, "jitter": 0}})

    streaming_cb = _fake_callback("u1", last_checkin=STREAMING_SENTINEL)
    alive_cb = _fake_callback("u2", last_checkin="2024-01-01T00:00:00", sleep_info=sleep_info)
    late_cb = _fake_callback("u3", last_checkin="2023-12-31T23:00:00", sleep_info=sleep_info)
    dead_cb = _fake_callback("u4", dead=True, last_checkin="2023-01-01T00:00:00")

    assert build_callback_row(streaming_cb, NOW)[0] == STATUS_GLYPHS["streaming"]
    assert build_callback_row(alive_cb, NOW)[0] == STATUS_GLYPHS["alive"]
    assert build_callback_row(late_cb, NOW)[0] == STATUS_GLYPHS["late"]
    assert build_callback_row(dead_cb, NOW)[0] == STATUS_GLYPHS["dead"]


async def test_refresh_live_cells_updates_checkin_and_status_only(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        before_hostname = app.table.get_cell("uuid-0", "hostname")

        cb = _fake_callback("uuid-0", dead=True, last_checkin="2023-01-01T00:00:00")
        app.table.refresh_live_cells({"uuid-0": cb})
        await pilot.pause()

        assert app.table.get_cell("uuid-0", "status") == STATUS_GLYPHS["dead"]
        assert app.table.get_cell("uuid-0", "checkin") != ""
        assert app.table.get_cell("uuid-0", "hostname") == before_hostname


async def test_reconcile_callback_adds_row_when_active_and_not_shown(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        cb = _fake_callback("uuid-new", active=True, hostname="host-new", display_id=9)
        app.table.reconcile_callback(cb, app.table.current_tab_id)
        await pilot.pause()
        assert app.table.is_displayed("uuid-new")


async def test_reconcile_callback_removes_row_when_inactive_and_shown(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        cb = _fake_callback("uuid-0", active=False)
        app.table.reconcile_callback(cb, app.table.current_tab_id)
        await pilot.pause()
        assert not app.table.is_displayed("uuid-0")


async def test_reconcile_callback_refreshes_ip_when_active_and_shown(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        cb = _fake_callback("uuid-0", active=True, ip=["10.0.0.9"])
        app.table.reconcile_callback(cb, app.table.current_tab_id)
        await pilot.pause()
        assert app.table.get_cell("uuid-0", "ip") == "10.0.0.9"


async def test_watch_current_tab_id_guard_after_row_removed(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        app.table.current_tab_id = "uuid-0"
        await pilot.pause()
        app.table.remove_row("uuid-0")
        await pilot.pause()

        # simulate the watcher firing again against the now-missing key
        app.table.watch_current_tab_id()


async def test_show_cursor_guard_after_row_removed(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        app.table.current_tab_id = "uuid-0"
        await pilot.pause()
        app.table.remove_row("uuid-0")
        await pilot.pause()

        app.table._show_cursor()


async def test_post_new_row_selected_guard_after_rows_removed(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        app.table.remove_row("uuid-0")
        app.table.remove_row("uuid-1")
        await pilot.pause()

        app.table._post_new_row_selected()
        assert app.updates == []
