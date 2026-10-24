import os
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label

from utils.logger import logger
from utils.state import get_last_file_dir, set_last_file_dir


class TaskPrompt(ModalScreen):
    pass


class YesNoPrompt(TaskPrompt):
    def __init__(self, question="Are you sure?"):
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        logger.debug("yes no prompt")
        yield Container(
            Label(self.question),
            Horizontal(
                Button(label="Yes", variant="success", id="yes"),
                Button(label="No", variant="error", id="no"),
            ),
        )

    @on(Button.Pressed)
    def _return(self, event: Button.Pressed):
        self.dismiss(event.button.id == "yes")


class FilePrompt(TaskPrompt):
    BINDINGS = [
        Binding(key="escape", action="cancel", description="cancel", show=False),
        Binding(key="left", action="go_up", description="up", show=False),
        Binding(key="right", action="enter_dir", description="open", show=False),
    ]

    def __init__(self, label: str, start_path: Optional[str] = None):
        super().__init__()
        self.label = label
        self.start_path = start_path or get_last_file_dir() or os.getcwd()
        self._selected: Optional[str] = None

    def compose(self) -> ComposeResult:
        logger.debug("file prompt")
        yield Container(
            Label(f"Select a file for '{self.label}'"),
            DirectoryTree(self.start_path, id="tree"),
            Label("", id="selection"),
            Horizontal(
                Button(label="Select", variant="success", id="select"),
                Button(label="Cancel", variant="error", id="cancel"),
            ),
        )

    @on(DirectoryTree.FileSelected)
    def _file_selected(self, event: DirectoryTree.FileSelected):
        self._selected = str(event.path)
        self.query_one("#selection", Label).update(self._selected)

    @on(Button.Pressed)
    def _button_pressed(self, event: Button.Pressed):
        if event.button.id == "select":
            if self._selected:
                set_last_file_dir(os.path.dirname(self._selected))
                self.dismiss(self._selected)
            return

        self.dismiss(None)

    def action_go_up(self):
        tree = self.query_one("#tree", DirectoryTree)
        node = tree.cursor_node
        current = node.data.path if node and node.data else tree.path
        if current.is_file():
            current = current.parent
        parent = current.parent
        if parent != current:
            tree.path = parent

    def action_enter_dir(self):
        self.query_one("#tree", DirectoryTree).action_select_cursor()

    def action_cancel(self):
        self.dismiss(None)
