from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, SelectionList
from textual.widgets.selection_list import Selection

from backend import MythicInstance
from utils.transfer_list import compute_active_changes, move_all, move_selected


class ManageCallbacks(ModalScreen):
    BINDINGS = [
        Binding(key="escape", action="cancel", description="cancel", show=False),
    ]

    def __init__(self, instance: MythicInstance):
        super().__init__()
        self.instance = instance
        self.initial_active: dict[str, bool] = {}
        self.labels: dict[str, str] = {}
        self.shown: list[str] = []
        self.hidden: list[str] = []

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Manage Callbacks", id="title"),
            Horizontal(
                Vertical(
                    Label("Shown (active)"),
                    Checkbox("select all", id="shown_select_all"),
                    SelectionList(id="shown_list"),
                    id="shown_pane",
                ),
                Vertical(
                    Button(label=">", id="move_right"),
                    Button(label=">>", id="move_all_right"),
                    Button(label="<", id="move_left"),
                    Button(label="<<", id="move_all_left"),
                    id="move_buttons",
                ),
                Vertical(
                    Label("Hidden (inactive)"),
                    Checkbox("select all", id="hidden_select_all"),
                    SelectionList(id="hidden_list"),
                    id="hidden_pane",
                ),
                id="panes",
            ),
            Horizontal(
                Button(label="Apply", variant="success", id="apply"),
                Button(label="Cancel", variant="error", id="cancel"),
                id="actions",
            ),
        )

    async def on_mount(self) -> None:
        detail = await self.instance.get_all_callbacks_detail()
        self.populate(detail)

    def populate(self, detail: list[dict]) -> None:
        for row in detail:
            uuid = row.get("agent_callback_id")
            if not uuid:
                continue

            active = bool(row.get("active"))
            display_id = row.get("display_id")
            host = row.get("host")
            payload = row.get("payload") or {}
            payload_type = (payload.get("payloadtype") or {}).get("name", "")
            self.labels[uuid] = f"{display_id}  {host} ({payload_type})"
            self.initial_active[uuid] = active

            if active:
                self.shown.append(uuid)
            else:
                self.hidden.append(uuid)

        self._rebuild_lists()

    def _rebuild_lists(self) -> None:
        shown_list = self.query_one("#shown_list", SelectionList)
        hidden_list = self.query_one("#hidden_list", SelectionList)
        shown_list.clear_options()
        hidden_list.clear_options()
        for uuid in self.shown:
            shown_list.add_option(Selection(self.labels.get(uuid, uuid), uuid))
        for uuid in self.hidden:
            hidden_list.add_option(Selection(self.labels.get(uuid, uuid), uuid))

    @on(Button.Pressed, "#move_right")
    def _move_right(self) -> None:
        shown_list = self.query_one("#shown_list", SelectionList)
        self.shown, self.hidden = move_selected(self.shown, self.hidden, set(shown_list.selected))
        self._rebuild_lists()

    @on(Button.Pressed, "#move_all_right")
    def _move_all_right(self) -> None:
        self.shown, self.hidden = move_all(self.shown, self.hidden)
        self._rebuild_lists()

    @on(Button.Pressed, "#move_left")
    def _move_left(self) -> None:
        hidden_list = self.query_one("#hidden_list", SelectionList)
        self.hidden, self.shown = move_selected(self.hidden, self.shown, set(hidden_list.selected))
        self._rebuild_lists()

    @on(Button.Pressed, "#move_all_left")
    def _move_all_left(self) -> None:
        self.hidden, self.shown = move_all(self.hidden, self.shown)
        self._rebuild_lists()

    @on(Checkbox.Changed, "#shown_select_all")
    def _shown_select_all(self, event: Checkbox.Changed) -> None:
        shown_list = self.query_one("#shown_list", SelectionList)
        if event.value:
            shown_list.select_all()
        else:
            shown_list.deselect_all()

    @on(Checkbox.Changed, "#hidden_select_all")
    def _hidden_select_all(self, event: Checkbox.Changed) -> None:
        hidden_list = self.query_one("#hidden_list", SelectionList)
        if event.value:
            hidden_list.select_all()
        else:
            hidden_list.deselect_all()

    @on(Button.Pressed, "#apply")
    def _apply(self) -> None:
        changes = compute_active_changes(self.initial_active, set(self.shown))
        self.dismiss(changes)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
