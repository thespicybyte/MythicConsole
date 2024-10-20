import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, MythicAgent, AgentCommandAlias, add_default_options
from utils.logger import logger

execute_library_parser = Cmd2ArgumentParser(description="Load a dylib from disk and run a function within it.")
add_default_options(execute_library_parser)


class ExecuteLibrary(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent)
        self._name = "execute-library"
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
        return execute_library_parser

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @cmd2.with_argparser(execute_library_parser)
    def do_execute_library(self, args: argparse.Namespace | str) -> Task:
        logger.warning("execute_library not yet implemented")
        return None
        # if isinstance(args, str):
        #     args = execute_library_parser.parse_args(args)
        #
        # path = " ".join(args.path)
        # task = Task(self._agent.instance, command="execute_library", args=path,
        #             callback_display_id=self._agent.tasker.callback.display_id)
        #
        # task.background = args.background
        #
        # return task
