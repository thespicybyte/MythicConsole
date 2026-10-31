import json
import re
from dataclasses import dataclass, field as dataclass_field
from typing import Any, List, Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static, TextArea

from screens.prompts import FilePrompt
from widgets.transfer_selection import CheckSelection, CheckSelectionList

_OMIT = object()
_MULTI_LINE_TYPES = {"Array", "TypedArray"}


@dataclass
class FieldSpec:
    """One `ParamForm` field: a server parameter (or a plain payload-level field like
    `selected_os`/`filename`) plus the value it should start out pre-filled with."""
    name: str
    parameter_type: str
    initial: Any = None
    required: bool = False
    choices: List[str] = dataclass_field(default_factory=list)
    verifier_regex: Optional[str] = None
    description: str = ""
    group_name: str = ""
    label: Optional[str] = None


def field_spec_from_param(param: dict, initial: Any = None) -> FieldSpec:
    """A server `commandparameter`/`buildparameter`/`c2profileparameter` dict -> `FieldSpec`,
    pre-filled with `initial` (the config's answer) if given, else the param's own default."""
    return FieldSpec(
        name=param["name"],
        parameter_type=param.get("parameter_type") or "String",
        initial=initial if initial is not None else param.get("default_value"),
        required=bool(param.get("required")),
        choices=list(param.get("choices") or []),
        verifier_regex=param.get("verifier_regex") or None,
        description=param.get("description") or "",
        group_name=param.get("group_name") or "",
    )


class ParamForm(ModalScreen):
    """A scrollable modal of labeled fields built from parameter specs, grouped by section,
    with inline per-field validation. Returns {name: value} on submit, None on cancel."""

    BINDINGS = [Binding(key="escape", action="cancel", description="cancel", show=False)]

    def __init__(self, title: str, specs: List[FieldSpec], *, groups_as_sections: bool = True):
        super().__init__()
        self.title_text = title
        self.specs = list(specs)
        self.groups_as_sections = groups_as_sections

    @staticmethod
    def _field_id(index: int) -> str:
        return f"field_{index}"

    @staticmethod
    def _error_id(index: int) -> str:
        return f"error_{index}"

    def compose(self) -> ComposeResult:
        rows = []
        last_group = None
        for index, spec in enumerate(self.specs):
            group = spec.group_name if self.groups_as_sections else ""
            if group and group != last_group:
                rows.append(Static(group, classes="form-section"))
            if self.groups_as_sections:
                last_group = group
            rows.append(self._compose_field(index, spec))

        yield Container(
            Label(self.title_text, id="form-title"),
            VerticalScroll(*rows, id="fields"),
            Horizontal(
                Button(label="OK", variant="success", id="ok"),
                Button(label="Cancel", variant="error", id="cancel"),
            ),
            id="param-form",
        )

    def _compose_field(self, index: int, spec: FieldSpec) -> Container:
        widget_id = self._field_id(index)
        children = [Label(spec.label or spec.name)]
        if spec.description:
            children.append(Label(spec.description, classes="field-description"))
        children.append(self._build_widget(widget_id, spec))
        children.append(Label("", id=self._error_id(index), classes="field-error"))
        return Container(*children, classes="form-field")

    def _build_widget(self, widget_id: str, spec: FieldSpec):
        param_type = spec.parameter_type

        if param_type == "Boolean":
            return Checkbox(value=bool(spec.initial), id=widget_id)

        if param_type == "ChooseOne":
            options = [(choice, choice) for choice in spec.choices]
            value = spec.initial if spec.initial in spec.choices else Select.NULL
            return Select(options, value=value, id=widget_id, allow_blank=True)

        if param_type == "ChooseMultiple":
            selection_list = CheckSelectionList(id=widget_id)
            initial = spec.initial if isinstance(spec.initial, list) else []
            for choice in spec.choices:
                selection_list.add_option(CheckSelection(choice, choice, choice in initial))
            return selection_list

        if param_type in _MULTI_LINE_TYPES:
            text = "\n".join(str(v) for v in spec.initial) if isinstance(spec.initial, list) \
                else str(spec.initial or "")
            return TextArea(text, id=widget_id)

        if param_type == "Dictionary":
            text = json.dumps(spec.initial) if isinstance(spec.initial, dict) else str(spec.initial or "")
            return TextArea(text, id=widget_id)

        if param_type == "File":
            return Horizontal(
                Input(value=str(spec.initial or ""), id=widget_id),
                Button(label="Browse...", id=f"browse_{widget_id}"),
                classes="file-field",
            )

        # String, Number, Date, and anything else not covered above: free text.
        return Input(value=str(spec.initial) if spec.initial is not None else "", id=widget_id)

    @on(Button.Pressed)
    def _button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "ok":
            self._submit()
            return
        if button_id == "cancel":
            self.dismiss(None)
            return
        if button_id.startswith("browse_"):
            self._browse(button_id.removeprefix("browse_"))

    def _browse(self, field_widget_id: str) -> None:
        def _set_path(path: Optional[str]) -> None:
            if path:
                self.query_one(f"#{field_widget_id}", Input).value = path

        self.app.push_screen(FilePrompt(field_widget_id), _set_path)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _set_error(self, index: int, message: str) -> None:
        self.query_one(f"#{self._error_id(index)}", Label).update(message)

    def _clear_error(self, index: int) -> None:
        self.query_one(f"#{self._error_id(index)}", Label).update("")

    def _extract(self, index: int, spec: FieldSpec):
        """Returns (ok, value). value is an error message when ok is False, or _OMIT when the
        field is a blank optional that should be left out of the result."""
        widget_id = self._field_id(index)
        param_type = spec.parameter_type

        if param_type == "Boolean":
            return True, self.query_one(f"#{widget_id}", Checkbox).value

        if param_type == "ChooseOne":
            value = self.query_one(f"#{widget_id}", Select).value
            if value is Select.NULL:
                return (False, "required") if spec.required else (True, _OMIT)
            return True, value

        if param_type == "ChooseMultiple":
            selected = list(self.query_one(f"#{widget_id}", CheckSelectionList).selected)
            if not selected:
                return (False, "required") if spec.required else (True, _OMIT)
            return True, selected

        if param_type in _MULTI_LINE_TYPES:
            raw = self.query_one(f"#{widget_id}", TextArea).text
            lines = [line for line in raw.splitlines() if line.strip()]
            if not lines:
                return (False, "required") if spec.required else (True, _OMIT)
            return True, lines

        if param_type == "Dictionary":
            raw = self.query_one(f"#{widget_id}", TextArea).text
            if not raw.strip():
                return (False, "required") if spec.required else (True, _OMIT)
            try:
                return True, json.loads(raw)
            except json.JSONDecodeError:
                return False, "must be valid JSON"

        if param_type == "File":
            raw = self.query_one(f"#{widget_id}", Input).value
            if not raw.strip():
                return (False, "required") if spec.required else (True, _OMIT)
            return True, raw

        raw = self.query_one(f"#{widget_id}", Input).value
        if not raw.strip():
            return (False, "required") if spec.required else (True, _OMIT)

        value = raw
        if param_type == "Number":
            try:
                value = int(raw)
            except ValueError:
                return False, "must be a number"

        if spec.verifier_regex and not re.fullmatch(spec.verifier_regex, str(value)):
            return False, f"must match {spec.verifier_regex}"

        return True, value

    def _submit(self) -> None:
        result = {}
        has_error = False
        for index, spec in enumerate(self.specs):
            ok, value = self._extract(index, spec)
            if not ok:
                has_error = True
                self._set_error(index, value)
                continue
            self._clear_error(index)
            if value is not _OMIT:
                result[spec.name] = value

        if has_error:
            return

        self.dismiss(result)
