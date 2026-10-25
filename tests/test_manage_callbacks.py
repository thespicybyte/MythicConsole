import types

from textual.app import App
from textual.widgets import Input, Static

from screens.home import Home
from screens.manage_callbacks import _HEADER_TEXT, ManageCallbacks
from widgets.transfer_selection import CheckSelectionList

DETAIL = [
    {"agent_callback_id": "uuid-active", "display_id": 1, "host": "host-a", "active": True,
     "payload": {"payloadtype": {"name": "poseidon"}}},
    {"agent_callback_id": "uuid-inactive", "display_id": 2, "host": "host-b", "active": False,
     "payload": {"payloadtype": {"name": "poseidon"}}},
]


def _stub_instance():
    async def _get_all_callbacks_detail():
        return DETAIL

    return types.SimpleNamespace(get_all_callbacks_detail=_get_all_callbacks_detail)


async def test_modal_populates_panes_from_detail():
    app = App()
    async with app.run_test() as pilot:
        modal = ManageCallbacks(_stub_instance())
        app.push_screen(modal)
        await pilot.pause()

        shown_list = modal.query_one("#shown_list", CheckSelectionList)
        hidden_list = modal.query_one("#hidden_list", CheckSelectionList)
        assert [option.value for option in shown_list.options] == ["uuid-active"]
        assert [option.value for option in hidden_list.options] == ["uuid-inactive"]


async def test_apply_returns_only_the_changed_callback():
    app = App()
    async with app.run_test() as pilot:
        modal = ManageCallbacks(_stub_instance())
        app.push_screen(modal)
        await pilot.pause()

        # simulate having moved the previously-inactive callback to Shown
        modal.shown, modal.hidden = ["uuid-active", "uuid-inactive"], []

        changes = {}
        modal.dismiss = changes.update
        modal._apply()

        assert changes == {"uuid-inactive": True}


async def test_populate_includes_status_and_checkin_columns():
    app = App()
    async with app.run_test() as pilot:
        modal = ManageCallbacks(_stub_instance())
        app.push_screen(modal)
        await pilot.pause()

        label = modal.labels["uuid-active"]
        assert "host-a" in label
        assert "?" in label  # no last_checkin in the fixture


async def test_header_row_is_never_filtered_out():
    app = App()
    async with app.run_test() as pilot:
        modal = ManageCallbacks(_stub_instance())
        app.push_screen(modal)
        await pilot.pause()

        filt = modal.query_one("#shown_filter", Input)
        filt.value = "nothing-matches-this"
        filt.post_message(Input.Changed(filt, "nothing-matches-this"))
        await pilot.pause()

        shown_list = modal.query_one("#shown_list", CheckSelectionList)
        assert [option.value for option in shown_list.options] == []
        header = modal.query_one("#shown_header", Static)
        assert header.render().plain == _HEADER_TEXT


async def test_filter_narrows_the_visible_rows():
    app = App()
    async with app.run_test() as pilot:
        modal = ManageCallbacks(_stub_instance())
        app.push_screen(modal)
        await pilot.pause()

        filt = modal.query_one("#shown_filter", Input)
        filt.value = "host-a"
        filt.post_message(Input.Changed(filt, "host-a"))
        await pilot.pause()

        shown_list = modal.query_one("#shown_list", CheckSelectionList)
        assert [option.value for option in shown_list.options] == ["uuid-active"]

        filt.value = ""
        filt.post_message(Input.Changed(filt, ""))
        await pilot.pause()
        assert [option.value for option in shown_list.options] == ["uuid-active"]


async def test_selection_persists_across_a_filter_change():
    app = App()
    async with app.run_test() as pilot:
        modal = ManageCallbacks(_stub_instance())
        app.push_screen(modal)
        await pilot.pause()

        shown_list = modal.query_one("#shown_list", CheckSelectionList)
        shown_list.select("uuid-active")
        await pilot.pause()

        filt = modal.query_one("#shown_filter", Input)
        filt.value = "nothing-matches-this"
        filt.post_message(Input.Changed(filt, "nothing-matches-this"))
        await pilot.pause()
        assert modal.shown_selected == {"uuid-active"}

        filt.value = ""
        filt.post_message(Input.Changed(filt, ""))
        await pilot.pause()
        assert shown_list.selected == ["uuid-active"]


async def test_header_click_toggles_sort_order():
    app = App()
    async with app.run_test() as pilot:
        modal = ManageCallbacks(_stub_instance())
        app.push_screen(modal)
        await pilot.pause()
        await pilot.click("#shown_header")
        await pilot.pause()
        assert modal.shown_sort_reverse is True

        await pilot.click("#shown_header")
        await pilot.pause()
        assert modal.shown_sort_reverse is False


class _ActionHarness(App):
    def __init__(self, instance):
        super().__init__()
        self.instance = instance

    action_manage_callbacks = Home.action_manage_callbacks
    _manage_callbacks = Home._manage_callbacks


async def test_action_manage_callbacks_does_not_require_an_active_worker():
    app = _ActionHarness(_stub_instance())
    async with app.run_test() as pilot:
        app.action_manage_callbacks()
        await pilot.pause()

        assert isinstance(app.screen, ManageCallbacks)
        app.screen.dismiss(None)
        await pilot.pause()
