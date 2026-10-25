from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.content import Content
from textual.strip import Strip
from textual.widgets import Checkbox, OptionList, SelectionList
from textual.widgets._option_list import Option
from textual.widgets.selection_list import Selection

CHECKED = "☑"
UNCHECKED = "☐"

# A row's checkbox occupies the mark glyph plus one trailing space.
CHECKBOX_WIDTH = 2


class GlyphCheckbox(Checkbox):
    """A checkbox that shows a single box glyph (`☐`/`☑`) with no surrounding
    brackets or solid-block button."""

    BUTTON_LEFT = ""
    BUTTON_RIGHT = ""

    @property
    def BUTTON_INNER(self) -> str:
        return CHECKED if self.value else UNCHECKED

    @property
    def _button(self) -> Content:
        button_style = self.get_visual_style("toggle--button")
        return Content.assemble((self.BUTTON_INNER, button_style))


class CheckSelection(Selection):
    """A single-line `Selection` for a `CheckSelectionList`."""

    def __init__(self, prompt, value, initial_state: bool = False, id=None, disabled: bool = False):
        Option.__init__(self, Content.from_text(prompt), id, disabled)
        self._value = value
        self._initial_state = initial_state


class CheckSelectionList(SelectionList):
    """A `SelectionList` whose rows use a single box-glyph checkbox (blank box
    when unselected, a check mark when selected) instead of the default
    bracketed/solid-block button.

    Selection is shown only by the checkbox. The highlighted (cursor) row is
    given a background highlight, but only while the operator is navigating with
    the keyboard; it clears as soon as the mouse is clicked."""

    COMPONENT_CLASSES = SelectionList.COMPONENT_CLASSES | {"check-selection-list--cursor"}

    DEFAULT_CSS = """
    CheckSelectionList > .check-selection-list--cursor {
        background: $primary 25%;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._keyboard_cursor = False

    def _use_keyboard_cursor(self) -> None:
        if not self._keyboard_cursor:
            self._keyboard_cursor = True
            self.refresh()

    def _use_mouse_cursor(self) -> None:
        if self._keyboard_cursor:
            self._keyboard_cursor = False
            self.refresh()

    def action_cursor_up(self) -> None:
        self._use_keyboard_cursor()
        super().action_cursor_up()

    def action_cursor_down(self) -> None:
        self._use_keyboard_cursor()
        super().action_cursor_down()

    def action_first(self) -> None:
        self._use_keyboard_cursor()
        super().action_first()

    def action_last(self) -> None:
        self._use_keyboard_cursor()
        super().action_last()

    def action_page_up(self) -> None:
        self._use_keyboard_cursor()
        super().action_page_up()

    def action_page_down(self) -> None:
        self._use_keyboard_cursor()
        super().action_page_down()

    def _on_click(self, event: events.Click) -> None:
        self._use_mouse_cursor()

    def _get_left_gutter_width(self) -> int:
        return CHECKBOX_WIDTH

    def render_line(self, y: int) -> Strip:
        line = OptionList.render_line(self, y)

        line_number = self.scroll_offset.y + y
        try:
            option_index, _ = self._lines[line_number]
        except IndexError:
            return line

        selection = self.get_option_at_index(option_index)
        selected = selection.value in self._selected
        component_style = "selection-list--button"
        if selected:
            component_style += "-selected"
        if self.highlighted == option_index:
            component_style += "-highlighted"

        underlying_style = next(iter(line)).style or self.rich_style
        button_style = self.get_component_rich_style(component_style)
        button_style += Style(meta={"option": option_index})
        inner = CHECKED if selected else UNCHECKED

        segments = [
            Segment(inner, style=button_style),
            Segment(" ", style=underlying_style),
            *line,
        ]

        if self._keyboard_cursor and self.highlighted == option_index:
            cursor_style = self.get_component_rich_style("check-selection-list--cursor")
            segments = [
                Segment(seg.text, (seg.style + cursor_style) if seg.style else cursor_style)
                for seg in segments
            ]

        return Strip(segments)
