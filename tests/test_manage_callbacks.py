import types

from textual.app import App
from textual.widgets import SelectionList

from screens.manage_callbacks import ManageCallbacks

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

        shown_list = modal.query_one("#shown_list", SelectionList)
        hidden_list = modal.query_one("#hidden_list", SelectionList)
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
