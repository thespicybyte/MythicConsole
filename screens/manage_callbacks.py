from datetime import datetime, timezone

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.events import Click
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, SelectionList, Static

from backend import MythicInstance
from utils.callback_status import alive_state, checkin_text, status_glyph
from utils.transfer_list import compute_active_changes, move_selected
from widgets.transfer_selection import GlyphCheckbox, CheckSelection, CheckSelectionList

_ID_W = 4
_HOST_W = 16
_PAYLOAD_W = 10
_CHECKIN_W = 9
_ROW_GUTTER = " " * 4

_HEADER_TEXT = _ROW_GUTTER + (
    f"{'ID':>{_ID_W}}  {'Host':<{_HOST_W}}  {'Payload':<{_PAYLOAD_W}}  {'Checkin':>{_CHECKIN_W}}"
)


def _format_row(glyph: str, display_id, host: str, payload_type: str, checkin: str) -> str:
    return (
        f"{glyph} {str(display_id):>{_ID_W}}  {host:<{_HOST_W}.{_HOST_W}}  "
        f"{payload_type:<{_PAYLOAD_W}.{_PAYLOAD_W}}  {checkin:>{_CHECKIN_W}}"
    )


class ManageCallbacks(ModalScreen):
    BINDINGS = [
        Binding(key="escape", action="cancel", description="cancel", show=False),
    ]

    def __init__(self, instance: MythicInstance):
        super().__init__()
        self.instance = instance
        self.initial_active: dict[str, bool] = {}
        self.labels: dict[str, str] = {}
        self.display_ids: dict[str, int] = {}
        self.shown: list[str] = []
        self.hidden: list[str] = []
        self.shown_selected: set[str] = set()
        self.hidden_selected: set[str] = set()
        self.shown_filter: str = ""
        self.hidden_filter: str = ""
        self.shown_sort_reverse: bool = False
        self.hidden_sort_reverse: bool = False

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Manage Callbacks", id="title"),
            Horizontal(
                Vertical(
                    Label("Shown"),
                    Input(placeholder="Filter...", id="shown_filter"),
                    GlyphCheckbox("select all", id="shown_select_all"),
                    Static(_HEADER_TEXT, id="shown_header"),
                    CheckSelectionList(id="shown_list"),
                    id="shown_pane",
                ),
                Vertical(
                    Button(label=">", id="move_right"),
                    Button(label="<", id="move_left"),
                    id="move_buttons",
                ),
                Vertical(
                    Label("Hidden"),
                    Input(placeholder="Filter...", id="hidden_filter"),
                    GlyphCheckbox("select all", id="hidden_select_all"),
                    Static(_HEADER_TEXT, id="hidden_header"),
                    CheckSelectionList(id="hidden_list"),
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
        now = datetime.now(timezone.utc)
        for row in detail:
            uuid = row.get("agent_callback_id")
            if not uuid:
                continue

            active = bool(row.get("active"))
            display_id = row.get("display_id")
            host = row.get("host") or ""
            payload = row.get("payload") or {}
            payload_type = (payload.get("payloadtype") or {}).get("name", "")
            last_checkin = row.get("last_checkin")
            state = alive_state(bool(row.get("dead")), last_checkin, row.get("sleep_info"), now)
            glyph = status_glyph(state)
            checkin = checkin_text(last_checkin, now)
            self.labels[uuid] = _format_row(glyph, display_id, host, payload_type, checkin)
            self.display_ids[uuid] = display_id or 0
            self.initial_active[uuid] = active

            if active:
                self.shown.append(uuid)
            else:
                self.hidden.append(uuid)

        self.shown.sort(key=lambda u: self.display_ids.get(u, 0))
        self.hidden.sort(key=lambda u: self.display_ids.get(u, 0))
        self._rebuild_lists()

    def _pane(self, which: str):
        """Return the (members, selected, list widget, select-all checkbox) for a pane."""
        if which == "shown":
            return (
                self.shown,
                self.shown_selected,
                self.query_one("#shown_list", CheckSelectionList),
                self.query_one("#shown_select_all", GlyphCheckbox),
            )
        return (
            self.hidden,
            self.hidden_selected,
            self.query_one("#hidden_list", CheckSelectionList),
            self.query_one("#hidden_select_all", GlyphCheckbox),
        )

    def _visible(self, which: str) -> list[str]:
        """The pane's member uuids that pass its current filter, in order."""
        members = self.shown if which == "shown" else self.hidden
        text_filter = self.shown_filter if which == "shown" else self.hidden_filter
        if not text_filter:
            return list(members)
        return [u for u in members if text_filter in self.labels.get(u, u).lower()]

    def _rebuild_lists(self) -> None:
        for which in ("shown", "hidden"):
            _, selected, widget, _ = self._pane(which)
            visible = self._visible(which)
            with widget.prevent(SelectionList.SelectedChanged):
                widget.clear_options()
                for uuid in visible:
                    widget.add_option(CheckSelection(self.labels.get(uuid, uuid), uuid))
                for uuid in visible:
                    if uuid in selected:
                        widget.select(uuid)
            self._refresh_select_all(which)

    def _refresh_select_all(self, which: str) -> None:
        """Set the select-all checkbox to reflect whether every visible row is selected."""
        _, selected, _, checkbox = self._pane(which)
        visible = self._visible(which)
        all_selected = bool(visible) and all(u in selected for u in visible)
        with checkbox.prevent(Checkbox.Changed):
            checkbox.value = all_selected

    def _sync_selected(self, which: str) -> None:
        """Fold the widget's current (visible) selection into the persistent set,
        leaving selections of filtered-out rows untouched."""
        _, selected, widget, _ = self._pane(which)
        visible = set(self._visible(which))
        selected.difference_update(visible)
        selected.update(v for v in widget.selected if v in visible)

    @on(Input.Changed, "#shown_filter")
    def _shown_filter_changed(self, event: Input.Changed) -> None:
        self.shown_filter = event.value.strip().lower()
        self._rebuild_lists()

    @on(Input.Changed, "#hidden_filter")
    def _hidden_filter_changed(self, event: Input.Changed) -> None:
        self.hidden_filter = event.value.strip().lower()
        self._rebuild_lists()

    def _toggle_sort(self, which: str) -> None:
        if which == "shown":
            self.shown_sort_reverse = not self.shown_sort_reverse
            self.shown.sort(key=lambda u: self.display_ids.get(u, 0), reverse=self.shown_sort_reverse)
        else:
            self.hidden_sort_reverse = not self.hidden_sort_reverse
            self.hidden.sort(key=lambda u: self.display_ids.get(u, 0), reverse=self.hidden_sort_reverse)
        self._rebuild_lists()

    @on(Click, "#shown_header")
    def _shown_header_clicked(self) -> None:
        self._toggle_sort("shown")

    @on(Click, "#hidden_header")
    def _hidden_header_clicked(self) -> None:
        self._toggle_sort("hidden")

    @on(Button.Pressed, "#move_right")
    def _move_right(self) -> None:
        moving = set(self.shown_selected)
        self.shown, self.hidden = move_selected(self.shown, self.hidden, moving)
        self.shown_selected -= moving
        self._rebuild_lists()

    @on(Button.Pressed, "#move_left")
    def _move_left(self) -> None:
        moving = set(self.hidden_selected)
        self.hidden, self.shown = move_selected(self.hidden, self.shown, moving)
        self.hidden_selected -= moving
        self._rebuild_lists()

    @on(SelectionList.SelectedChanged, "#shown_list")
    def _shown_selection_changed(self) -> None:
        self._sync_selected("shown")
        self._refresh_select_all("shown")

    @on(SelectionList.SelectedChanged, "#hidden_list")
    def _hidden_selection_changed(self) -> None:
        self._sync_selected("hidden")
        self._refresh_select_all("hidden")

    @on(Checkbox.Changed, "#shown_select_all")
    def _shown_select_all(self, event: Checkbox.Changed) -> None:
        shown_list = self.query_one("#shown_list", CheckSelectionList)
        if event.value:
            shown_list.select_all()
        else:
            shown_list.deselect_all()

    @on(Checkbox.Changed, "#hidden_select_all")
    def _hidden_select_all(self, event: Checkbox.Changed) -> None:
        hidden_list = self.query_one("#hidden_list", CheckSelectionList)
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
