from typing import Dict, List

from cmd2 import cmd2, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

net_parser = Cmd2ArgumentParser()
net_subparsers = net_parser.add_subparsers(title='subcommands', help='subcommand help')

net_echo_parser = net_subparsers.add_parser('echo', help='echo text')
add_default_options(net_echo_parser)
net_echo_parser.add_argument('--text', required=True, help='text to echo')

net_connect_parser = net_subparsers.add_parser('connect', help='connect to a peer')
add_default_options(net_connect_parser)
net_connect_parser.add_argument('--port', type=int, required=True, help='port')


class Net(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "net"
        self._description = "synthetic grouped command covering echo/connect"
        self._subcommand_parsers: Dict[str, Cmd2ArgumentParser] = {
            "echo": net_echo_parser,
            "connect": net_connect_parser,
        }
        self._aliases = [
            AgentCommandAlias("echo", self._name, "echo", description="echo text"),
            AgentCommandAlias("connect", self._name, "connect", description="connect to a peer"),
        ]

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
    def subcommand_parsers(self) -> Dict[str, Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> Cmd2ArgumentParser:
        return net_parser

    @cmd2.with_argparser(net_parser)
    def do_net(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def net_echo(self, args) -> Task:
        if isinstance(args, str):
            args = net_echo_parser.parse_args(args)

        task = Task(self._agent.instance, command="echo", args=args.text,
                    callback=self._agent.tasker.callback)
        task.console_args = args
        task.background = args.background
        return task

    net_echo_parser.set_defaults(func=net_echo)

    def net_connect(self, args) -> Task:
        if isinstance(args, str):
            args = net_connect_parser.parse_args(args)

        task = Task(self._agent.instance, command="connect", args=str(args.port),
                    callback=self._agent.tasker.callback)
        task.console_args = args
        task.background = args.background
        return task

    net_connect_parser.set_defaults(func=net_connect)
