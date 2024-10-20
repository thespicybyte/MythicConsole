import argparse
from typing import List, Dict, Callable

from cmd2 import cmd2, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, MythicAgent, AgentCommandAlias, add_default_options

clipboard_parser = Cmd2ArgumentParser(description="Get the contents of the clipboard")
add_default_options(clipboard_parser)
clipboard_parser.add_argument('--read', nargs='+',
                              help='The various types to fetch from the clipboard. '
                                   'Using * will fetch the content of everything on the clipboard (this could be a lot)')

clipboard_subparsers = clipboard_parser.add_subparsers(title='subcommands', help='subcommand help')

clipboard_monitor_parser = clipboard_subparsers.add_parser('monitor',
                                                           help='Monitor the macOS clipboard for changes every X seconds')
add_default_options(clipboard_monitor_parser)
clipboard_monitor_parser.add_argument('--duration', type=int, default=-1,
                                      help='"Number of seconds to monitor the clipboard, or a negative value to do it '
                                           'indefinitely')


class Clipboard(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent)
        self._name = "clipboard"
        self._subcommand_parsers: Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser] = {
            "monitor": clipboard_monitor_parser
        }
        self._aliases = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
        return clipboard_parser

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @cmd2.with_argparser(clipboard_parser)
    def do_clipboard(self, args) -> Task | Callable:
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

        return self.clipboard(args)

    def clipboard(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = clipboard_parser.parse_args(args)

        command_args = {"read": args.read}
        task = Task(self._agent.instance, command="clipboard", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    def clipboard_monitor(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            subcommand_parser = self.get_subcommand_parser("monitor")
            args = subcommand_parser.parse_args(args)

        command_args = {"duration": args.duration}
        task = Task(self._agent.instance, command="clipboard_monitor", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    clipboard_monitor_parser.set_defaults(func=clipboard_monitor)
