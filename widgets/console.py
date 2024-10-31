import dataclasses
import io
import shlex
from typing import List, Optional, TYPE_CHECKING

from rich.console import Console as RichConsole, RenderableType
from textual import on, events
from textual._text_area_theme import TextAreaTheme
from textual.app import ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import Container, Vertical
from textual.document._document import Location, EditResult
from textual.events import Paste, MouseUp
from textual.message import Message
from textual.widget import Widget
from textual.widgets import TextArea, Input, Label
from textual.widgets._text_area import ThemeDoesNotExist

from textual_textarea import TextEditor
from textual_autocomplete import AutoComplete, Dropdown, DropdownItem, InputState
from textual_textarea.autocomplete import CompletionList
from textual_textarea.containers import TextContainer, FooterContainer
from textual_textarea.text_editor import TextAreaPlus

from backend import MythicInstance
from utils.logger import logger
from widgets.console_themes import MYTHIC_DARK, MYTHIC_LIGHT

if TYPE_CHECKING:
    from backend import MythicAgent


class ConsoleAreaPlus(TextAreaPlus):
    BINDINGS = [
        # Cursor movement
        Binding("up", "cursor_up", "cursor up", show=False),
        Binding("down", "cursor_down", "cursor down", show=False),
        Binding("left", "cursor_left", "cursor left", show=False),
        Binding("right", "cursor_right", "cursor right", show=False),
        Binding("ctrl+left", "cursor_word_left", "cursor word left", show=False),
        Binding("ctrl+right", "cursor_word_right", "cursor word right", show=False),
        Binding("home", "cursor_line_start", "cursor line start", show=False),
        Binding("end", "cursor_line_end", "cursor line end", show=False),
        Binding("ctrl+home", "cursor_doc_start", "cursor doc start", show=False),
        Binding("ctrl+end", "cursor_doc_end", "cursor doc end", show=False),
        Binding("pageup", "cursor_page_up", "cursor page up", show=False),
        Binding("pagedown", "cursor_page_down", "cursor page down", show=False),
        # scrolling
        Binding("ctrl+up", "scroll_one('up')", "scroll one up", show=False),
        Binding("ctrl+down", "scroll_one('down')", "scroll one down", show=False),
        # Making selections (generally holding the shift key and moving cursor)
        Binding(
            "ctrl+shift+left",
            "cursor_word_left(True)",
            "cursor left word select",
            show=False,
        ),
        Binding(
            "ctrl+shift+right",
            "cursor_word_right(True)",
            "cursor right word select",
            show=False,
        ),
        Binding(
            "shift+home",
            "cursor_line_start(True)",
            "cursor line start select",
            show=False,
        ),
        Binding(
            "shift+end", "cursor_line_end(True)", "cursor line end select", show=False
        ),
        Binding(
            "ctrl+shift+home",
            "cursor_doc_start(True)",
            "select to cursor doc start",
            show=False,
        ),
        Binding(
            "ctrl+shift+end",
            "cursor_doc_end(True)",
            "select to cursor doc end",
            show=False,
        ),
        Binding("shift+up", "cursor_up(True)", "cursor up select", show=False),
        Binding("shift+down", "cursor_down(True)", "cursor down select", show=False),
        Binding("shift+left", "cursor_left(True)", "cursor left select", show=False),
        Binding("shift+right", "cursor_right(True)", "cursor right select", show=False),
        Binding("ctrl+a", "select_all", "select all", show=False),
        # Editing
        Binding("ctrl+c", "copy", "copy", show=False),
        Binding("cmd+c", "copy", "copy", show=False),
    ]

    def __init__(self, language: str = None, text: str = None):
        super().__init__(text=text, language=language)
        self.register_theme(MYTHIC_DARK)
        self.register_theme(MYTHIC_LIGHT)
        self._set_theme("mythic_dark" if self.app.dark else "mythic_light")

    def _handle_tab(self, _event: events.Key) -> None:
        """Override editor behavior which would write a tab in the console"""
        return

    def _handle_enter(self, event: events.Key) -> None:
        """Override editor behavior which would write a new line in the console"""
        return

    def _handle_backspace(self, _event: events.Key) -> None:
        """Override editor behavior which would delete a character in the console"""
        return

    def _delete_via_keyboard(
            self,
            _start: Location,
            _end: Location,
    ) -> EditResult | None:
        """Override editor behavior which would delete characters in the console"""
        return

    def on_mount(self) -> None:
        """Override base class mount which was doing clipboard stuff we don't need"""
        return

    def on_key(self, _event: events.Key) -> None:
        """Override base class key behavior"""
        logger.info(_event.name)
        return

    def on_paste(self, _event: Paste) -> None:
        """Override base class to prevent pasting in console"""
        return

    def _set_clipboard(self, _message) -> None:
        """Override base class as clipboard is already set"""
        return

    def _set_theme(self, theme: str) -> None:
        # somewhere monokai is being set as the theme at startup.
        if theme == "monokai":
            return

        theme_object: TextAreaTheme | None

        # If the user supplied a string theme name, find it and apply it.
        try:
            theme_object = self._themes[theme]
        except KeyError:
            theme_object = TextAreaTheme.get_builtin_theme(theme)
            if theme_object is None:
                raise ThemeDoesNotExist(
                    f"{theme!r} is not a builtin theme, or it has not been registered. "
                    f"To use a custom theme, register it first using `register_theme`, "
                    f"then switch to that theme by setting the `TextArea.theme` attribute."
                ) from None

        self._theme = dataclasses.replace(theme_object)
        if theme_object:
            base_style = theme_object.base_style
            if base_style:
                color = base_style.color
                background = base_style.bgcolor
                if color:
                    self.styles.color = Color.from_rich_color(color)
                if background:
                    self.styles.background = Color.from_rich_color(background)

    def set_theme(self, theme_name: str) -> None:
        self._set_theme(theme_name)


class Console(TextEditor, inherit_bindings=False):
    BINDINGS = [
        Binding("ctrl+o", "load", "Open Query", show=False),
        Binding("ctrl+f", "find", "Find", show=False),
        Binding("f3", "find(True)", "Find Next", show=False),
    ]

    def __init__(self, *children: Widget):
        super().__init__(*children)
        self.text_container = TextContainer()
        self.completion_list = CompletionList()
        self.footer = FooterContainer(classes="hide")
        self.footer_label = Label("", id="textarea__save_open_input_label")
        self.watch(self.app, "dark", self._app_dark_toggled, init=False)
        self.text_input = ConsoleAreaPlus(language=self._language, text=self._initial_text)

    def _app_dark_toggled(self):
        if self.app.dark:
            self.text_input.set_theme("mythic_dark")
            return
        self.text_input.set_theme("mythic_light")

    def on_mount(self):
        area = self.query_one(TextArea)
        area.read_only = True
        area.show_line_numbers = False
        area.cursor_blink = False

    def compose(self) -> ComposeResult:
        with self.text_container:
            yield self.text_input
            yield self.completion_list
        with self.footer:
            yield self.footer_label

    def write(self, value) -> None:
        string_io = io.StringIO()
        console = RichConsole(file=string_io, style=None, no_color=True)
        console.print(value)

        area = self.query_one(TextArea)
        area.insert(string_io.getvalue(), area.document.end)
        string_io.close()


class ConsoleInput(Input):
    class Paste(Message):
        pass

    @on(MouseUp)
    async def _on_click(self, event: events.MouseUp) -> None:
        if event.button == 2:
            self.post_message(self.Paste())

    def append(self, value: str) -> None:
        """Append a string to the current value in the input"""
        self.value += value


class CommandAutoComplete(AutoComplete):
    def on_key(self, event: events.Key) -> None:
        if not self.dropdown.display:
            # only respond and stop the event if the dropdown is open
            return

        key = event.key
        if key == "down":
            self.dropdown.cursor_down()
            event.stop()
        elif key == "up":
            self.dropdown.cursor_up()
            event.stop()
        elif key == "escape":
            self.dropdown.close()
            event.stop()
        elif key == "tab" or key == "enter" or key == "right":
            # Only interfere if there's a dropdown visible,
            # otherwise, we want things to behave like a normal input.
            if self.dropdown.display:
                self._select_item()
                if not self.tab_moves_focus:
                    event.stop()  # Prevent focus change


class CommandDropdown(Dropdown):
    def reposition(
            self,
            input_cursor_position: int | None = None,
            scroll_target_adjust_y: int = 0,
    ) -> None:
        if self.input_widget is None:
            return

        if input_cursor_position is None:
            input_cursor_position = self.input_widget.cursor_position

        top, right, bottom, left = self.styles.margin
        x, y, width, height = self.input_widget.content_region
        count = len(self.child.matches)
        line_below_cursor = y - count + scroll_target_adjust_y

        cursor_screen_position = x + (
                input_cursor_position - self.input_widget.view_position
        )
        self.styles.margin = (
            line_below_cursor,
            right,
            bottom,
            cursor_screen_position,
        )


class ConsolePanel(Container):
    class NewInput(Message):
        def __init__(self, data: str):
            super().__init__()
            self.data = data

    def __init__(self, *children: Widget, instance: MythicInstance):
        from backend.mythic_agent.mythic_agent import MythicCommands

        super().__init__(*children)
        self.instance = instance
        self.agent: Optional[MythicAgent] = None
        self.auto = CommandAutoComplete(ConsoleInput(), CommandDropdown(items=self._get_matches),
                                        completion_strategy=self._complete)
        self.mythic_commands = MythicCommands(instance)
        self._mythic_console = Console()
        self._history: List[str] = []
        self._history_index: int = -1

    @classmethod
    def _complete(cls, selected_value: str, old_state: InputState) -> InputState:
        """
        Replace the last word with the selected value from the `DropDown` without replacing the entire line
        :param selected_value: Value the user selected from the `DropDown`
        :param old_state: old `InputState` value which includes the value of the entire line
        :return: Updated `InputState`
        """
        tokens = shlex.split(old_state.value)
        tokens[-1] = selected_value
        result = " ".join(tokens) + " "
        new_state = InputState(value=result, cursor_position=len(result))
        return new_state

    def _get_matches(self, state: List[DropdownItem] | InputState) -> List[DropdownItem]:
        """
        Generates a list of possible matches based on what the current input state
        :param state: Current input state or value in the input
        :return: List of possible matches
        """
        if not isinstance(state, InputState):
            # not handled, don't think this will hit
            return []

        if not state.value:
            return []

        if state.value.endswith(" ") or state.value.endswith("\""):
            return []

        if self.agent:
            items = self.agent.get_completer_items(state.value)
        else:
            items = self.mythic_commands.get_completer_items(state.value)

        try:
            tokens = shlex.split(state.value)
        except:
            return []

        matched_items = []
        for item in items:
            if item.__contains__(tokens[-1]):
                matched_items.append(DropdownItem(item))

        return matched_items

    def compose(self) -> ComposeResult:
        logger.info(self.auto)
        with Container():
            with Vertical():
                logger.warning("yeidling consle")
                yield self._mythic_console
                logger.warning("yeidling auto")
                yield self.auto
                logger.warning("yeilded auto")

    def write_string(self, data: RenderableType) -> None:
        """
        Write a renderable value to the console
        :param data: any renderable value
        """
        console = self.query_one(Console)
        console.write(data)

    def set_agent(self, payload_type: str):
        from agents import get_agent

        if not payload_type:
            return

        if self.agent:
            return

        self.agent = get_agent(self.instance, payload_type)

    @on(ConsoleInput.Submitted)
    def _input_submitted(self, event: ConsoleInput.Submitted) -> None:
        prompt = self.query_one(ConsoleInput)
        command = event.value
        prompt.clear()
        self.post_message(self.NewInput(command))
        self._history_index = -1
        if not self._history:
            self._history.append(command)
            return

        # prevent the same command twice in a row
        if self._history[-1] != command:
            self._history.append(command)

    @on(events.Key)
    def key_press(self, event: events.Key) -> None:
        """
        Catch keystroke for history and tab complete. Tab will cancel default behavior to prevent switching context
        :param event: key event
        """
        key = event.key
        console_input = self.query_one(ConsoleInput)
        match key:
            case "up":
                event.stop()
                if not self._history:
                    return
                if self._history_index < 0:
                    self._history_index = len(self._history) - 1
                    console_input.value = self._history[self._history_index]
                    console_input.cursor_position = len(console_input.value)
                    return

                self._history_index -= 1
                if self._history_index <= 0:
                    self._history_index = 0

                console_input.value = self._history[self._history_index]
                self.auto.dropdown.visible = False
                console_input.cursor_position = len(console_input.value)
            case "down":
                event.stop()
                if not self._history:
                    return

                if self._history_index < 0:
                    return

                self._history_index += 1
                if self._history_index == len(self._history):
                    self._history_index = -1
                    console_input.value = ""
                    return

                console_input.value = self._history[self._history_index]
                self.auto.dropdown.visible = False
                console_input.cursor_position = len(console_input.value)
            case "tab":
                event.stop()
                event.prevent_default()
