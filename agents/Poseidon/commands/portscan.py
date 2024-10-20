import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, MythicAgent, AgentCommandAlias, add_default_options

portscan_parser = Cmd2ArgumentParser(description="Scan host(s) for open ports.")
portscan_parser.add_argument('--hosts', nargs='+', help='List of host IPs or CIDR notations')
portscan_parser.add_argument('--ports', nargs='+',
                             help='List of ports to scan. Can use the dash separator to specify a range.')
add_default_options(portscan_parser)


class Portscan(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent)
        self._name = "portscan"
        self._subcommand_parsers: Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser] = {}
        self._aliases = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
        return portscan_parser

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @cmd2.with_argparser(portscan_parser)
    def do_portscan(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = portscan_parser.parse_args(args)

        command_args = {
            "hosts": args.hosts,
            "ports": args.ports
        }
        task = Task(self._agent.instance, command="portscan", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task
