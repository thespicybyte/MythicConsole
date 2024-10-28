import argparse
from typing import List, Dict, Callable

from cmd2 import cmd2, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, MythicAgent, AgentCommandAlias, add_default_options

curl_parser = Cmd2ArgumentParser(description="Execute a single web request")
curl_parser.add_argument('--url', default='https://www.google.com', help='URL to request')
curl_parser.add_argument('--method', default='GET', choices=["GET", "POST", "PUT", "DELETE"], help='URL to request')
curl_parser.add_argument('--headers', nargs='+', help='Array of headers in Key: Value entries')
curl_parser.add_argument('--body', default="", help='Array of headers in Key: Value entries')
add_default_options(curl_parser)

curl_subparsers = curl_parser.add_subparsers(title='subcommands', help='subcommand help')
curl_env_set_parser = curl_subparsers.add_parser('env-set',
                                                 help='Set environment variables to use in subsequent curl requests')
curl_env_set_parser.add_argument('values', nargs='+', help='Array of environment values in KEY=Value entries')
add_default_options(curl_env_set_parser)

curl_env_get_parser = curl_subparsers.add_parser('env-get',
                                                 help='Get environment variables to use in subsequent curl requests')
add_default_options(curl_env_get_parser)

curl_env_clear_parser = curl_subparsers.add_parser('env-clear',
                                                   help='Clear environment variables to use in subsequent curl requests')
curl_env_clear_parser.add_argument('--values', nargs='+', help='Array of environment names to clear')
curl_env_clear_parser.add_argument('--all', action='store_true', help='Clear all environment variables')
add_default_options(curl_env_clear_parser)


class Curl(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent)
        self._name = "curl"
        self._description = "Execute a single web request"
        self._subcommand_parsers: Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser] = {
            "env-set": curl_env_set_parser,
            "env-get": curl_env_get_parser,
            "env-clear": curl_env_clear_parser,
        }
        self._aliases = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
        return curl_parser

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @cmd2.with_argparser(curl_parser)
    def do_curl(self, args) -> Task | Callable:
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

        return self.curl(args)

    def curl(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = curl_parser.parse_args(args)

        command_args = {
            "body": args.body,
            "headers": args.headers,
            "method": args.method,
            "url": args.url
        }

        task = Task(self._agent.instance, command="curl", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    def curl_env_get(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = curl_env_get_parser.parse_args(args)

        task = Task(self._agent.instance, command="curl_env_get",
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    curl_env_get_parser.set_defaults(func=curl_env_get)

    def curl_env_set(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = curl_env_set_parser.parse_args(args)

        command_args = {
            "setEnv": args.values
        }
        task = Task(self._agent.instance, command="curl_env_set", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    curl_env_set_parser.set_defaults(func=curl_env_set)

    def curl_env_clear(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = curl_env_clear_parser.parse_args(args)

        command_args = {
            "clearEnv": args.values if args.values else [],
            "clearAllEnv": True if args.all else False
        }
        task = Task(self._agent.instance, command="curl_env_clear", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    curl_env_clear_parser.set_defaults(func=curl_env_clear)
