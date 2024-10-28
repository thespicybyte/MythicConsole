import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

env_parser = Cmd2ArgumentParser()
env_subparsers = env_parser.add_subparsers(title='subcommands', help='subcommand help')

env_set_parser = env_subparsers.add_parser('set', help='set an environment variable')
env_set_parser.add_argument('parameter', help='Parameter name')
env_set_parser.add_argument('value', help='Value')
add_default_options(env_set_parser)

env_get_parser = env_subparsers.add_parser('get', help='get all environment')
add_default_options(env_get_parser)

env_unset_parser = env_subparsers.add_parser('unset', help='Unset an environment variable')
env_unset_parser.add_argument('parameter', help='Parameter name')
add_default_options(env_unset_parser)


class Environment(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "environment"
        self._description = "Interact with environment variables"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "set": env_set_parser,
            "get": env_get_parser,
            "unset": env_unset_parser,
        }
        self._aliases = [
            AgentCommandAlias("setenv", self._name, "set", description="set an environment variable"),
            AgentCommandAlias("getenv", self._name, "get", description="get all environment"),
            AgentCommandAlias("unsetenv", self._name, "unset", description="Unset an environment variable")
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
        return env_parser

    @cmd2.with_argparser(env_parser, preserve_quotes=True)
    def do_environment(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def env_set(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = env_set_parser.parse_args(args)

        command_args = f"{args.parameter} {args.value}"

        task = Task(self._agent.instance, command="setenv", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    env_set_parser.set_defaults(func=env_set)

    def env_get(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            subcommand_parser = env_get_parser
            args = subcommand_parser.parse_args(args)

        task = Task(self._agent.instance, command="getenv",
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    env_get_parser.set_defaults(func=env_get)

    def env_unset(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = env_unset_parser.parse_args(args)

        command_args = args.parameter

        task = Task(self._agent.instance, command="unsetenv", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    env_unset_parser.set_defaults(func=env_unset)
