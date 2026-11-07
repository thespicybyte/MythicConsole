from typing import List, Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, Label, Static

from mythic_console.screens.prompts import BACK

# Theme-driven styles so keys and values read distinctly in any theme.
_KEY_STYLE = "bold $primary"
_VALUE_STYLE = "$text"
_SUBHEAD_STYLE = "bold $text-muted"
_MUTED_STYLE = "$text-muted"


def _fmt_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else "(none)"
    if isinstance(value, dict):
        return ", ".join(f"{k}={_fmt_value(v)}" for k, v in value.items()) if value else "(none)"
    if value is None or value == "":
        return "(none)"
    return str(value)


def _kv_content(items, indent: str = "") -> Content:
    """A `name: value` block with theme-colored keys and values. `items` is an iterable of
    (name, value) pairs. Values are placed literally, so brackets/quotes aren't parsed."""
    parts: List = []
    for name, value in items:
        parts.append((f"{indent}{name}: ", _KEY_STYLE))
        parts.append((_fmt_value(value), _VALUE_STYLE))
        parts.append(("\n", ""))
    if parts:
        parts.pop()  # drop the trailing newline
    return Content.assemble(*parts)


class BuildSummary(ModalScreen):
    """Final review before building the payload: one collapsible section per questionnaire step
    (the payload itself, each selected C2 profile, and the command set). Dismisses with True to
    build, `BACK` to step back to the command selection, or False to cancel the whole flow."""

    BINDINGS = [Binding(key="escape", action="cancel", description="cancel", show=False)]

    def __init__(self, *, payload_type: str, selected_os, filename,
                 build_parameters: Optional[dict] = None, c2_profiles: Optional[List[dict]] = None,
                 commands: Optional[List[str]] = None, description: str = "",
                 show_back: bool = True):
        super().__init__()
        self.payload_type = payload_type
        self.selected_os = selected_os
        self.filename = filename
        self.build_parameters = build_parameters or {}
        self.c2_profiles = list(c2_profiles or [])
        self.commands = list(commands or [])
        self.description = description or ""
        self.show_back = show_back

    def compose(self) -> ComposeResult:
        sections = [
            Collapsible(Static(self._payload_content()), title="Payload", collapsed=False),
        ]
        for profile in self.c2_profiles:
            name = profile.get("name", "")
            params = profile.get("parameters") or {}
            body = (_kv_content(params.items()) if params
                    else Content.assemble(("(no parameters)", _MUTED_STYLE)))
            sections.append(Collapsible(Static(body), title=f"C2 profile: {name}", collapsed=False))

        if self.commands:
            cmd_body = Content.assemble((", ".join(sorted(self.commands)), _VALUE_STYLE))
        else:
            cmd_body = Content.assemble(("(none)", _MUTED_STYLE))
        sections.append(Collapsible(Static(cmd_body),
                                    title=f"Commands ({len(self.commands)})", collapsed=False))

        buttons = []
        if self.show_back:
            buttons.append(Button(label="Back", variant="warning", id="back"))
        buttons.append(Button(label="Build", variant="success", id="build"))
        buttons.append(Button(label="Cancel", variant="error", id="cancel"))

        yield Container(
            Label(f"Review build — '{self.payload_type}'", id="summary-title"),
            VerticalScroll(*sections, id="summary-body"),
            Horizontal(*buttons, id="actions"),
            id="build-summary",
        )

    def _payload_content(self) -> Content:
        head = _kv_content(self._payload_head_items())
        parts: List = [head, "\n\n", ("Build parameters:", _SUBHEAD_STYLE), "\n"]
        if self.build_parameters:
            parts.append(_kv_content(self.build_parameters.items(), indent="  "))
        else:
            parts.append(("  (defaults)", _MUTED_STYLE))
        return Content.assemble(*parts)

    def _payload_head_items(self):
        items = [("Type", self.payload_type), ("OS", self.selected_os),
                 ("Filename", self.filename)]
        if self.description:
            items.append(("Comment", self.description))
        return items

    @on(Button.Pressed)
    def _button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss(BACK)
            return
        self.dismiss(event.button.id == "build")

    def action_cancel(self) -> None:
        self.dismiss(False)
