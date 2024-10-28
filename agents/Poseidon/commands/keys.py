import argparse
from random import choice
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

keys_parser = Cmd2ArgumentParser(description="Interact with the linux keyring")
keys_subparsers = keys_parser.add_subparsers(title='subcommands', help='subcommand help')

keys_session_parser = keys_subparsers.add_parser('session', help='Interact with session keyring')
add_default_options(keys_session_parser)

keys_user_parser = keys_subparsers.add_parser('user', help='Interact with user keyring')
add_default_options(keys_user_parser)

keys_process_parser = keys_subparsers.add_parser('process', help='Interact with process keyring')
add_default_options(keys_process_parser)

keys_threads_parser = keys_subparsers.add_parser('threads', help='Interact with threads keyring')
add_default_options(keys_threads_parser)

key_search_parser = keys_subparsers.add_parser('search', help='Search keys for a keyword')
key_search_parser.add_argument("typename", choices=["keyring", "user", "login", "session"],
                               help="Choose the type of the key")
key_search_parser.add_argument("keyword", help="Name of the key to search for")
add_default_options(key_search_parser)


class Keys(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "keys"
        self._description = "Interact with the linux keyring"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "session": keys_session_parser,
            "user": keys_user_parser,
            "process": keys_process_parser,
            "threads": keys_threads_parser,
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
        return keys_parser

    @cmd2.with_argparser(keys_parser)
    def do_keys(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def session(self, args: argparse.Namespace | str) -> Task:
        return self.dump(args, "dumpsession")

    keys_session_parser.set_defaults(func=session)

    def user(self, args: str | argparse.Namespace) -> Task:
        return self.dump(args, "dumpuser")

    keys_user_parser.set_defaults(func=user)

    def process(self, args: str | argparse.Namespace) -> Task:
        return self.dump(args, "dumpprocess")

    keys_process_parser.set_defaults(func=user)

    def threads(self, args: str | argparse.Namespace) -> Task:
        return self.dump(args, "dumpthreads")

    keys_threads_parser.set_defaults(func=user)

    def dump(self, args, command: str) -> Task:
        if isinstance(args, str):
            subcommand_parser = keys_user_parser
            args = subcommand_parser.parse_args(args)

        command_args = {"command": command}
        task = Task(self._agent.instance, command="keys", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    def search(self, args) -> Task:
        if isinstance(args, str):
            subcommand_parser = keys_user_parser
            args = subcommand_parser.parse_args(args)

        command_args = {
            "keyword": args.keyword,
            "typename": args.typename
        }
        task = Task(self._agent.instance, command="keys", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task
