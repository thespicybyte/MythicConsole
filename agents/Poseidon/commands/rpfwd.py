import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

rpfwd_parser = Cmd2ArgumentParser(description="Start or Stop a Reverse Port Forward.")
file_subparsers = rpfwd_parser.add_subparsers(title='subcommands', help='subcommand help')

rpfwd_start_parser = file_subparsers.add_parser('start', help='Start a port forward')
rpfwd_start_parser.add_argument('remote_ip', help='Remote IP to connect to when a new connection comes in')
rpfwd_start_parser.add_argument('--local-port', type=int, default=7000,
                                help='Local port to open on host where agent is running')
rpfwd_start_parser.add_argument('--remote-port', type=int, default=7000,
                                help='Remote port to connect to when a new connection comes in')
add_default_options(rpfwd_start_parser)

rpfwd_stop_parser = file_subparsers.add_parser('stop', help='Stop a port forward')
rpfwd_stop_parser.add_argument('--local-port', type=int, default=7000,
                               help='Local port to open on host where agent is running')
add_default_options(rpfwd_stop_parser)


class Rpfwd(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "rpfwd"
        self._description = "Start or Stop a Reverse Port Forward."
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "start": rpfwd_start_parser,
            "stop": rpfwd_stop_parser,
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
        return rpfwd_parser

    @cmd2.with_argparser(rpfwd_parser)
    def do_rpfwd(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def rpfwd_start(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = rpfwd_start_parser.parse_args(args)

        command_args = {
            "action": "start",
            "port": args.local_port,
            "remote_ip": args.remote_ip,
            "remote_port": args.remote_port
        }

        task = Task(self._agent.instance, command="rpfwd", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    rpfwd_start_parser.set_defaults(func=rpfwd_start)

    def rpfwd_stop(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            subcommand_parser = rpfwd_stop_parser
            args = subcommand_parser.parse_args(args)

        command_args = {
            "action": "stop",
            "port": args.local_port,
        }

        task = Task(self._agent.instance, command="rpfwd", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    rpfwd_stop_parser.set_defaults(func=rpfwd_stop)
