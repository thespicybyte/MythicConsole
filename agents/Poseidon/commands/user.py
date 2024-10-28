import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

user_parser = Cmd2ArgumentParser()
user_subparsers = user_parser.add_subparsers(title='subcommands', help='subcommand help')

user_get_parser = user_subparsers.add_parser('get', help='Get information regarding the current user context')
add_default_options(user_get_parser)


class User(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "user"
        self._description = "Interact with users on a target"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "get": user_get_parser,
        }
        self._aliases = [
            AgentCommandAlias("getuser", self._name, "get",
                              description="Get information regarding the current user context"),
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
    def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
        return user_parser

    @cmd2.with_argparser(user_parser)
    def do_user(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def user_get(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = user_get_parser.parse_args(args)

        task = Task(self._agent.instance, command="getuser",
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    user_get_parser.set_defaults(func=user_get)
