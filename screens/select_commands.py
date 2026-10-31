from typing import List, Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, SelectionList

from widgets.transfer_selection import CheckSelection, CheckSelectionList, GlyphCheckbox

_MODES = ["default", "all", "custom"]


class SelectCommands(ModalScreen):
    """Pick a payload type's command set for `payload build`: a mode pulldown
    (default/all/custom) plus a filterable checklist that's shown only in custom mode. Dismisses
    with `None` for default, `SelectCommands.ALL` for all (the caller expands it to the full
    catalog), the chosen `list[str]` for custom, or `SelectCommands.CANCELLED` on cancel."""

    ALL = object()
    CANCELLED = object()

    BINDINGS = [Binding(key="escape", action="cancel", description="cancel", show=False)]

    def __init__(self, catalog: List[dict], *, mode: str = "default", preselected: Optional[List[str]] = None):
        super().__init__()
        self.names = sorted({c["cmd"] for c in catalog if c.get("cmd")})
        self.selected: set[str] = set(preselected or [])
        self.text_filter = ""
        self.mode = mode if mode in _MODES else "default"

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Select commands", id="title"),
            Select([(m.capitalize(), m) for m in _MODES], value=self.mode, allow_blank=False, id="mode"),
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
        self._apply_mode_visibility()

    def _apply_mode_visibility(self) -> None:
        show_custom = self.mode == "custom"
        self.query_one("#filter", Input).display = show_custom
        self.query_one("#select_all", GlyphCheckbox).display = show_custom
        self.query_one("#commands", CheckSelectionList).display = show_custom

    @on(Select.Changed, "#mode")
    def _mode_changed(self, event: Select.Changed) -> None:
        self.mode = event.value
        self._apply_mode_visibility()

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
        if self.mode == "default":
            self.dismiss(None)
        elif self.mode == "all":
            self.dismiss(SelectCommands.ALL)
        else:
            self.dismiss(sorted(self.selected))

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(SelectCommands.CANCELLED)

    def action_cancel(self) -> None:
        self.dismiss(SelectCommands.CANCELLED)
