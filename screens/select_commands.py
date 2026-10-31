from typing import List, Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, SelectionList

from widgets.transfer_selection import CheckSelection, CheckSelectionList, GlyphCheckbox


class SelectCommands(ModalScreen):
    """Pick a subset of a payload type's command catalog for `payload build`'s custom
    command-set option. A single filterable checklist rather than ManageCallbacks' two-pane
    transfer list -- there is nothing to move between, just a catalog to pick from."""

    BINDINGS = [Binding(key="escape", action="cancel", description="cancel", show=False)]

    def __init__(self, catalog: List[dict], preselected: Optional[List[str]] = None):
        super().__init__()
        self.names = sorted({c["cmd"] for c in catalog if c.get("cmd")})
        self.selected: set[str] = set(preselected or [])
        self.text_filter = ""

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Select commands", id="title"),
            Input(placeholder="Filter...", id="filter"),
            GlyphCheckbox("select all", id="select_all"),
            CheckSelectionList(id="commands"),
            Horizontal(
                Button(label="OK", variant="success", id="ok"),
                Button(label="Cancel", variant="error", id="cancel"),
            ),
        )

    def on_mount(self) -> None:
        self._rebuild()

    def _visible(self) -> List[str]:
        if not self.text_filter:
            return self.names
        return [name for name in self.names if self.text_filter in name.lower()]

    def _rebuild(self) -> None:
        widget = self.query_one("#commands", CheckSelectionList)
        visible = self._visible()
        with widget.prevent(SelectionList.SelectedChanged):
            widget.clear_options()
            for name in visible:
                widget.add_option(CheckSelection(name, name))
            for name in visible:
                if name in self.selected:
                    widget.select(name)
        self._refresh_select_all(visible)

    def _refresh_select_all(self, visible: List[str]) -> None:
        checkbox = self.query_one("#select_all", GlyphCheckbox)
        all_selected = bool(visible) and all(name in self.selected for name in visible)
        with checkbox.prevent(Checkbox.Changed):
            checkbox.value = all_selected

    @on(Input.Changed, "#filter")
    def _filter_changed(self, event: Input.Changed) -> None:
        self.text_filter = event.value.strip().lower()
        self._rebuild()

    @on(SelectionList.SelectedChanged, "#commands")
    def _selection_changed(self) -> None:
        visible = set(self._visible())
        widget = self.query_one("#commands", CheckSelectionList)
        self.selected.difference_update(visible)
        self.selected.update(v for v in widget.selected if v in visible)
        self._refresh_select_all(self._visible())

    @on(Checkbox.Changed, "#select_all")
    def _select_all_changed(self, event: Checkbox.Changed) -> None:
        widget = self.query_one("#commands", CheckSelectionList)
        if event.value:
            widget.select_all()
        else:
            widget.deselect_all()

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self.dismiss(sorted(self.selected))

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
