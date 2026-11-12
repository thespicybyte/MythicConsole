from typing import Iterable, Optional, TYPE_CHECKING

from rich.console import RenderableType
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.message import Message
from textual.widget import Widget
from textual_autocomplete import DropdownItem

from textual_console import CommandAutoComplete, ConsoleInput, ConsoleOutput

from mythic_console.backend import MythicInstance
from mythic_console.utils.history import load_history
from mythic_console.utils.logger import logger

if TYPE_CHECKING:
    from mythic_console.backend import MythicAgent


class ConsolePanel(Container):
    class NewInput(Message):
        def __init__(self, data: str):
            super().__init__()
            self.data = data

    def __init__(self, *children: Widget, instance: MythicInstance):
        from mythic_console.backend.mythic_agent.mythic_agent import MythicCommands

        super().__init__(*children)
        self.instance = instance
        self.agent: Optional["MythicAgent"] = None
        self.mythic_commands = MythicCommands(instance)
        self.console_output = ConsoleOutput()
        self.console_input = ConsoleInput(prompt="> ", id="prompt", history=load_history())
        self.auto = CommandAutoComplete(self.console_input, candidates=self._completer_items)
        self._written: list[RenderableType] = []
        self._entry_end_lines: list[int] = []

    def compose(self) -> ComposeResult:
        with Container():
            with Vertical():
                yield self.console_output
                yield self.console_input
                yield self.auto

    def on_mount(self) -> None:
        logger.info("seeding completion caches (payload types, users, operations)")
        self.run_worker(self.mythic_commands.cache_payload_types(), exit_on_error=False)
        self.run_worker(self.mythic_commands.cache_users(), exit_on_error=False)
        self.run_worker(self.mythic_commands.cache_operations(), exit_on_error=False)
        self.run_worker(self.mythic_commands.cache_blocklists(), exit_on_error=False)
        self.run_worker(self.mythic_commands.cache_blocklist_commands(), exit_on_error=False)

    def _completer_items(self, text: str) -> Iterable[str | DropdownItem]:
        """Candidate source for CommandAutoComplete: last-word matching is handled by the
        package itself, so this just delegates to the active agent or global commands.
        A trailing space is passed through so Tab after a command (or subcommand) lists
        its subcommands/options; empty text lists the top-level commands. An unclosed
        quote yields nothing."""
        if text.endswith('"'):
            return []

        source = self.agent or self.mythic_commands
        return source.get_completer_items(text)

    def write_string(self, data: RenderableType) -> None:
        """
        Write a renderable value to the console
        :param data: any renderable value
        """
        self._written.append(data)
        self.console_output.write(data)
        self._entry_end_lines.append(len(self.console_output.lines))

    def toggle_autoscroll(self) -> bool:
        """
        Flip autoscroll for this panel's output. On re-enable, jump to the newest line.
        :return: the new enabled state
        """
        enabled = not self.console_output.auto_scroll
        self.console_output.auto_scroll = enabled
        if enabled:
            self.console_output.scroll_end(animate=False)
        return enabled

    def toggle_word_wrap(self) -> bool:
        """
        Flip word wrap for this panel's output, re-render existing content, and keep the
        viewport anchored on the same content.
        :return: the new wrap state
        """
        output = self.console_output
        at_bottom = output.is_vertical_scroll_end
        anchor_index = self._entry_at_display_line(output.scroll_offset.y)

        enabled = not output.wrap
        output.wrap = enabled
        output.clear()
        self._entry_end_lines = []
        anchor_line = 0
        for index, renderable in enumerate(self._written):
            if index == anchor_index:
                anchor_line = len(output.lines)
            output.write(renderable)
            self._entry_end_lines.append(len(output.lines))

        if at_bottom:
            output.scroll_end(animate=False)
        elif anchor_index is not None:
            output.scroll_to(y=anchor_line, animate=False)
        return enabled

    def _entry_at_display_line(self, line: int) -> int | None:
        """Index into _written of the entry whose display lines contain line."""
        for index, end in enumerate(self._entry_end_lines):
            if end > line:
                return index
        return len(self._written) - 1 if self._written else None

    async def set_agent(self, payload_type: str):
        from mythic_console.agents import get_agent

        if not payload_type:
            return

        if self.agent:
            return

        self.agent = get_agent(self.instance, payload_type)
        await self.agent.load_commands()

    @on(ConsoleInput.Submitted)
    def _input_submitted(self, event: ConsoleInput.Submitted) -> None:
        for line in event.value.splitlines():
            if line.strip():
                self.post_message(self.NewInput(line))
