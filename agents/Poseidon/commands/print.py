import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

print_parser = Cmd2ArgumentParser()
print_subparsers = print_parser.add_subparsers(title='subcommands', help='subcommand help')

print_c2_parser = print_subparsers.add_parser('c2', help='Print current C2 capabilities and configurations.')
add_default_options(print_c2_parser)

print_p2p_parser = print_subparsers.add_parser('p2p', help='Print current P2P Connections.')
add_default_options(print_p2p_parser)


class Print(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "print"
        self._description = "Show c2 profiles"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "c2": print_c2_parser,
            "p2p": print_p2p_parser,
        }
        self._aliases = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @property
    def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
        return print_parser

    @cmd2.with_argparser(print_parser)
    def do_print(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def print_c2(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = print_c2_parser.parse_args(args)

        task = Task(self._agent.instance, command="print_c2",
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    print_c2_parser.set_defaults(func=print_c2)

    def print_p2p(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            subcommand_parser = print_p2p_parser
            args = subcommand_parser.parse_args(args)

        task = Task(self._agent.instance, command="print_p2p",
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    print_p2p_parser.set_defaults(func=print_p2p)
