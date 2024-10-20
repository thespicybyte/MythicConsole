import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, MythicAgent, AgentCommandAlias, add_default_options

config_parser = Cmd2ArgumentParser(description="View current config and host information")
add_default_options(config_parser)


class Config(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent)
        self._name = "config"
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
        return config_parser

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @cmd2.with_argparser(config_parser)
    def do_config(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = config_parser.parse_args(args)

        task = Task(self._agent.instance, command="config",
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task
