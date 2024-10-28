import argparse
from typing import List, Dict

from cmd2 import cmd2, argparse_custom, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

caffeinate_parser = Cmd2ArgumentParser()
add_default_options(caffeinate_parser)
caffeinate_parser.add_argument("--enable", action="store_true", help="Prevent the system from sleeping")


class Caffeinate(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent)
        self._name = "caffeinate"
        self._description = "Prevent the system from sleeping"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {}
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
        return caffeinate_parser

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @cmd2.with_argparser(caffeinate_parser)
    def do_caffeinate(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = caffeinate_parser.parse_args(args)

        command_args = "-enable" if args.enable else ""
        task = Task(self._agent.instance, command=self._name, args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task
