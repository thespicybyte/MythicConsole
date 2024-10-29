import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

socks_parser = Cmd2ArgumentParser(description="Start or Stop SOCKS5.")
socks_subparsers = socks_parser.add_subparsers(title='subcommands', help='subcommand help')

socks_start_parser = socks_subparsers.add_parser('start', help='Start SOCKS5 proxy')
socks_start_parser.add_argument('--port', type=int, default=7000,
                                help='Port number on Mythic server to open for SOCKS5')
socks_start_parser.add_argument('--username', help='Optionally restrict access to SOCKS port via username/password')
socks_start_parser.add_argument('--password', help='Optionally restrict access to SOCKS port via username/password')
add_default_options(socks_start_parser)

socks_stop_parser = socks_subparsers.add_parser('stop', help='Stop a port forward')
socks_stop_parser.add_argument('--port', type=int, default=7000,
                               help='Port number on Mythic server to open for SOCKS5')
add_default_options(socks_stop_parser)


class Socks(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "socks"
        self._description = "Start or Stop SOCKS5."
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "start": socks_start_parser,
            "stop": socks_stop_parser,
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
        return socks_parser

    @cmd2.with_argparser(socks_parser)
    def do_socks(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def socks_start(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = socks_start_parser.parse_args(args)

        command_args = {
            "action": "start",
            "port": args.port,
            "username": args.username or "",
            "password": args.password or "",
        }

        task = Task(self._agent.instance, command="socks", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    socks_start_parser.set_defaults(func=socks_start)

    def socks_stop(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            args = socks_stop_parser.parse_args(args)

        command_args = {
            "action": "stop",
            "port": args.port,
            "username": "",
            "password": "",
        }

        task = Task(self._agent.instance, command="socks", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    socks_stop_parser.set_defaults(func=socks_stop)
