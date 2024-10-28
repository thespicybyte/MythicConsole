import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, MythicAgent, AgentCommandAlias, add_default_options

keylog_parser = Cmd2ArgumentParser(description="Keylog users as root on Linux")
add_default_options(keylog_parser)


class Keylog(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent)
        self._name = "keylog"
        self._description = "Keylog users as root on Linux"
        self._subcommand_parsers: Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser] = {}
        self._aliases = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
        return keylog_parser

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @cmd2.with_argparser(keylog_parser)
    def do_keylog(self, args: argparse.Namespace | str) -> Task:
        task = Task(self._agent.instance, command="keylog", callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = True
        return task
