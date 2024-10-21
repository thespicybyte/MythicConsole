import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

c2_parser = Cmd2ArgumentParser()
c2_subparsers = c2_parser.add_subparsers(title='subcommands', help='subcommand help')

c2_start_parser = c2_subparsers.add_parser('start', help='Start a C2 profile')
c2_start_parser.add_argument('profile', help='The name of the c2 profile you want to configure')
add_default_options(c2_start_parser)

c2_stop_parser = c2_subparsers.add_parser('stop', help='Stop a C2 profile')
c2_stop_parser.add_argument('profile', help='The name of the c2 profile you want to configure')
add_default_options(c2_stop_parser)

c2_update_parser = c2_subparsers.add_parser('update', help='Update C2 Profile')
c2_update_parser.add_argument('profile', help='The name of the c2 profile you want to update')
c2_update_parser.add_argument('name', help='The name of the c2 profile attribute you want to adjust')
c2_update_parser.add_argument('value', help='The new value you want to use')
add_default_options(c2_update_parser)


class C2(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "c2"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "start": c2_start_parser,
            "stop": c2_stop_parser,
            "update": c2_update_parser,
        }
        self._aliases = []

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
        return c2_parser

    @cmd2.with_argparser(c2_parser, preserve_quotes=True)
    def do_c2(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def c2_start(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = c2_start_parser.parse_args(args)

        command_args = {
            "c2_name": args.profile,
            "action": "start"
        }

        task = Task(self._agent.instance, command="update_c2", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    c2_start_parser.set_defaults(func=c2_start)

    def c2_stop(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = c2_start_parser.parse_args(args)

        command_args = {
            "c2_name": args.profile,
            "action": "stop"
        }

        task = Task(self._agent.instance, command="update_c2", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    c2_stop_parser.set_defaults(func=c2_stop)

    def c2_update(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            args = c2_update_parser.parse_args(args)

        command_args = {
            "c2_name": args.profile,
            "config_name": args.name,
            "config_value": args.value
        }
        task = Task(self._agent.instance, command="update_c2", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    c2_update_parser.set_defaults(func=c2_update)
