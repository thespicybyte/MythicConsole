from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from utils.logger import logger


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
