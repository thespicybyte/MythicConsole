import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

parser = Cmd2ArgumentParser()
command_subparsers = parser.add_subparsers(title='subcommands', help='subcommand help')

command_run_parser = command_subparsers.add_parser('run', help='run a command')
add_default_options(command_run_parser)
command_run_parser.add_argument('command', nargs='+', help='command to run')


class Command(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "command"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "run": command_run_parser
        }
        self._aliases = [
            AgentCommandAlias("shell", self._name, "run")
        ]

    @property
    def name(self) -> str:
        return self._name

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @property
    def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
        return parser

    @cmd2.with_argparser(parser)
    def do_command(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def command_run(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            subcommand_parser = self.get_subcommand_parser("run")
            args = subcommand_parser.parse_args(args)

        command_args = " ".join(args.command)
        task = Task(self._agent.instance, command="shell", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    command_run_parser.set_defaults(func=command_run)
