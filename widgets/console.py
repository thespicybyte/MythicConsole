from typing import List, Optional, TYPE_CHECKING

from rich.console import RenderableType
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.message import Message
from textual.widget import Widget

from textual_console import CommandAutoComplete, ConsoleInput, ConsoleOutput

from backend import MythicInstance

if TYPE_CHECKING:
    from backend import MythicAgent


class ConsolePanel(Container):
    class NewInput(Message):
        def __init__(self, data: str):
            super().__init__()
            self.data = data

    def __init__(self, *children: Widget, instance: MythicInstance):
        from backend.mythic_agent.mythic_agent import MythicCommands

        super().__init__(*children)
        self.instance = instance
        self.agent: Optional["MythicAgent"] = None
        self.mythic_commands = MythicCommands(instance)
        self.console_output = ConsoleOutput()
        self.console_input = ConsoleInput(prompt="> ", id="prompt")
        self.auto = CommandAutoComplete(self.console_input, candidates=self._completer_items)

    def compose(self) -> ComposeResult:
        with Container():
            with Vertical():
                yield self.console_output
                yield self.console_input
                yield self.auto

    def _completer_items(self, text: str) -> List[str]:
        """Candidate source for CommandAutoComplete: last-word matching is handled by the
        package itself, so this just delegates to the active agent or global commands."""
        source = self.agent or self.mythic_commands
        return source.get_completer_items(text)

    def write_string(self, data: RenderableType) -> None:
        """
        Write a renderable value to the console
        :param data: any renderable value
        """
        self.console_output.write(data)

    def set_agent(self, payload_type: str):
        from agents import get_agent

        if not payload_type:
            return

        if self.agent:
            return

        self.agent = get_agent(self.instance, payload_type)

    @on(ConsoleInput.Submitted)
    def _input_submitted(self, event: ConsoleInput.Submitted) -> None:
        for line in event.value.splitlines():
            if line.strip():
                self.post_message(self.NewInput(line))
