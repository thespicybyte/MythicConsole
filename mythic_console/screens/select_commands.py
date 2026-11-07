from typing import List, Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, SelectionList

from mythic_console.screens.prompts import BACK
from mythic_console.utils.transfer_list import move_selected
from mythic_console.widgets.transfer_selection import CheckSelection, CheckSelectionList, GlyphCheckbox

_BUILTIN_REASON = "Always included (builtin command)."


def _norm(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().lower()


def _param_matches(actual, required) -> bool:
    """Whether a build parameter's value satisfies a `filter_by_build_parameter` requirement.
    The requirement may be a single value or a list of acceptable values."""
    if isinstance(required, (list, tuple, set)):
        return _norm(actual) in {_norm(r) for r in required}
    return _norm(actual) == _norm(required)


def _incompatibility_reason(attributes: dict, selected_os, build_parameters: dict):
    """Why a command can't be included for this build (OS or build-parameter filter), or None
    if it's compatible. Mirrors Mythic's own command-availability rules."""
    supported = attributes.get("supported_os") or []
    if supported and selected_os and selected_os not in supported:
        return f"Not available on {selected_os} — supported on: {', '.join(supported)}"

    filters = attributes.get("filter_by_build_parameter") or {}
    for name, required in filters.items():
        if not _param_matches(build_parameters.get(name), required):
            if isinstance(required, (list, tuple, set)):
                want = " / ".join(str(r) for r in required)
            else:
                want = str(required)
            return f"Requires build option {name} = {want}"
    return None


class SelectCommands(ModalScreen):
    """Pick a payload type's command set for `payload build` as a two-pane transfer list
    (Included | Excluded), mirroring the Manage Callbacks modal.

    The modal opens with the payload type's default command set already in the Included pane:
    every command Mythic always compiles in (`attributes.builtin`, shown as locked rows that
    can't be moved out) plus every command the payload type suggests
    (`attributes.suggested_command`). Commands that can't run on the chosen OS or don't satisfy
    the build-parameter filters are shown greyed in the Excluded pane and can't be selected; a
    tooltip explains why on hover. The operator moves the rest between the panes with the
    `>`/`<` buttons to customize. Dismisses with the sorted list of included command names on
    OK, `BACK` on back, or `SelectCommands.CANCELLED` on cancel."""

    CANCELLED = object()

    BINDINGS = [Binding(key="escape", action="cancel", description="cancel", show=False)]

    def __init__(self, catalog: List[dict], *, included: Optional[List[str]] = None,
                 selected_os: Optional[str] = None, build_parameters: Optional[dict] = None,
                 show_back: bool = False):
        super().__init__()
        names = sorted({c["cmd"] for c in catalog if c.get("cmd")})
        attributes = {c["cmd"]: (c.get("attributes") or {}) for c in catalog if c.get("cmd")}
        build_parameters = build_parameters or {}
        self.names = names

        # Commands that can't be included for this build (OS / build-parameter filters).
        self.reasons: dict[str, str] = {}
        for name in names:
            reason = _incompatibility_reason(attributes[name], selected_os, build_parameters)
            if reason:
                self.reasons[name] = reason
        incompatible = set(self.reasons)

        # Mythic always builds these in; they stay in Included and can't be removed. An
        # incompatible command is never pinned (it can't be built at all).
        self.builtin: set[str] = {n for n in names
                                  if attributes.get(n, {}).get("builtin") and n not in incompatible}

        if included is None:
            include = {n for n in names if n not in incompatible and (
                attributes.get(n, {}).get("builtin")
                or attributes.get(n, {}).get("suggested_command"))}
        else:
            include = (set(included) - incompatible) | self.builtin

        self.included: List[str] = [n for n in names if n in include]
        self.excluded: List[str] = [n for n in names if n not in include]
        self.included_selected: set[str] = set()
        self.excluded_selected: set[str] = set()
        self.included_filter: str = ""
        self.excluded_filter: str = ""
        self.show_back = show_back

    def compose(self) -> ComposeResult:
        buttons = []
        if self.show_back:
            buttons.append(Button(label="Back", variant="warning", id="back"))
        buttons.append(Button(label="OK", variant="success", id="ok"))
        buttons.append(Button(label="Cancel", variant="error", id="cancel"))
        yield Container(
            Label("Select commands", id="title"),
            Horizontal(
                Vertical(
                    Label("Excluded"),
                    Input(placeholder="Filter...", id="excluded_filter"),
                    GlyphCheckbox("select all", id="excluded_select_all"),
                    CheckSelectionList(id="excluded_list"),
                    id="excluded_pane",
                ),
                Vertical(
                    Button(label=">", id="move_right"),
                    Button(label="<", id="move_left"),
                    id="move_buttons",
                ),
                Vertical(
                    Label("Included"),
                    Input(placeholder="Filter...", id="included_filter"),
                    GlyphCheckbox("select all", id="included_select_all"),
                    CheckSelectionList(id="included_list"),
                    id="included_pane",
                ),
                id="panes",
            ),
            Horizontal(*buttons, id="actions"),
        )

    def on_mount(self) -> None:
        self._rebuild_lists()

    def _pane(self, which: str):
        """Return the (members, selected, list widget, select-all checkbox) for a pane."""
        if which == "included":
            return (
                self.included,
                self.included_selected,
                self.query_one("#included_list", CheckSelectionList),
                self.query_one("#included_select_all", GlyphCheckbox),
            )
        return (
            self.excluded,
            self.excluded_selected,
            self.query_one("#excluded_list", CheckSelectionList),
            self.query_one("#excluded_select_all", GlyphCheckbox),
        )

    def _visible(self, which: str) -> List[str]:
        """The pane's member commands that pass its current filter, in order."""
        members = self.included if which == "included" else self.excluded
        text_filter = self.included_filter if which == "included" else self.excluded_filter
        if not text_filter:
            return list(members)
        return [name for name in members if text_filter in name.lower()]

    def _is_locked(self, which: str, name: str) -> bool:
        """A row the operator can't move: a builtin in Included, or an incompatible command
        in Excluded."""
        if which == "included":
            return name in self.builtin
        return name in self.reasons

    def _rebuild_lists(self) -> None:
        for which in ("included", "excluded"):
            _, selected, widget, _ = self._pane(which)
            visible = self._visible(which)
            tooltips: dict = {}
            with widget.prevent(SelectionList.SelectedChanged):
                widget.clear_options()
                for name in visible:
                    locked = self._is_locked(which, name)
                    widget.add_option(CheckSelection(name, name, disabled=locked))
                    if locked:
                        tooltips[name] = (_BUILTIN_REASON if which == "included"
                                          else self.reasons[name])
                for name in visible:
                    if name in selected:
                        widget.select(name)
            widget.option_tooltips = tooltips
            self._refresh_select_all(which)

    def _refresh_select_all(self, which: str) -> None:
        """Set the select-all checkbox to reflect whether every movable visible row is selected."""
        _, selected, _, checkbox = self._pane(which)
        movable = [n for n in self._visible(which) if not self._is_locked(which, n)]
        all_selected = bool(movable) and all(n in selected for n in movable)
        with checkbox.prevent(Checkbox.Changed):
            checkbox.value = all_selected

    def _sync_selected(self, which: str) -> None:
        """Fold the widget's current (visible) selection into the persistent set, leaving
        selections of filtered-out rows untouched. Locked rows never count as selected."""
        _, selected, widget, _ = self._pane(which)
        visible = set(self._visible(which))
        selected.difference_update(visible)
        selected.update(v for v in widget.selected if v in visible)
        selected.difference_update(n for n in list(selected) if self._is_locked(which, n))

    @on(Input.Changed, "#included_filter")
    def _included_filter_changed(self, event: Input.Changed) -> None:
        self.included_filter = event.value.strip().lower()
        self._rebuild_lists()

    @on(Input.Changed, "#excluded_filter")
    def _excluded_filter_changed(self, event: Input.Changed) -> None:
        self.excluded_filter = event.value.strip().lower()
        self._rebuild_lists()

    def _sort_panes(self) -> None:
        self.included.sort()
        self.excluded.sort()

    @on(Button.Pressed, "#move_right")
    def _move_right(self) -> None:
        # `>` moves from the left (Excluded) into the right pane (Included). Incompatible
        # commands can't be included, so they never move.
        moving = self.excluded_selected - set(self.reasons)
        self.excluded, self.included = move_selected(self.excluded, self.included, moving)
        self.excluded_selected -= moving
        self._sort_panes()
        self._rebuild_lists()

    @on(Button.Pressed, "#move_left")
    def _move_left(self) -> None:
        # `<` moves from the right (Included) into the left pane (Excluded). Builtins stay in
        # Included even if a select-all swept them up.
        moving = self.included_selected - self.builtin
        self.included, self.excluded = move_selected(self.included, self.excluded, moving)
        self.included_selected -= moving
        self._sort_panes()
        self._rebuild_lists()

    @on(SelectionList.SelectedChanged, "#included_list")
    def _included_selection_changed(self) -> None:
        self._sync_selected("included")
        self._refresh_select_all("included")

    @on(SelectionList.SelectedChanged, "#excluded_list")
    def _excluded_selection_changed(self) -> None:
        self._sync_selected("excluded")
        self._refresh_select_all("excluded")

    @on(Checkbox.Changed, "#included_select_all")
    def _included_select_all(self, event: Checkbox.Changed) -> None:
        included_list = self.query_one("#included_list", CheckSelectionList)
        if event.value:
            included_list.select_all()
        else:
            included_list.deselect_all()

    @on(Checkbox.Changed, "#excluded_select_all")
    def _excluded_select_all(self, event: Checkbox.Changed) -> None:
        excluded_list = self.query_one("#excluded_list", CheckSelectionList)
        if event.value:
            excluded_list.select_all()
        else:
            excluded_list.deselect_all()

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self.dismiss(sorted(self.included))

    @on(Button.Pressed, "#back")
    def _back(self) -> None:
        self.dismiss(BACK)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(SelectCommands.CANCELLED)

    def action_cancel(self) -> None:
        self.dismiss(SelectCommands.CANCELLED)
