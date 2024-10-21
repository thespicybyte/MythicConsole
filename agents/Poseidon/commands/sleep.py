import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, MythicAgent, AgentCommandAlias, add_default_options

sleep_parser = Cmd2ArgumentParser(description="Update the sleep interval of the agent.")
add_default_options(sleep_parser)
sleep_parser.add_argument('--interval', type=int, help='Interval Seconds')
sleep_parser.add_argument('--jitter', type=int, help='Jitter Percentage')


class Sleep(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent)
        self._name = "sleep"
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
        return sleep_parser

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @cmd2.with_argparser(sleep_parser)
    def do_sleep(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = sleep_parser.parse_args(args)

        command_args = {
            "interval": args.interval,
            "jitter": args.jitter,
        }

        task = Task(self._agent.instance, command="sleep", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task
