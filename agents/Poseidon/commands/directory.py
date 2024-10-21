from typing import List, Dict

from cmd2 import cmd2, argparse_custom, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

directory_parser = Cmd2ArgumentParser()
directory_subparsers = directory_parser.add_subparsers(title='subcommands', help='subcommand help')

directory_list_parser = directory_subparsers.add_parser('list', help='list a directory')
add_default_options(directory_list_parser)
directory_list_parser.add_argument('path', nargs='+', help='path to list')

directory_change_parser = directory_subparsers.add_parser('change', help='change a directory')
add_default_options(directory_change_parser)
directory_change_parser.add_argument('path', nargs='+', help='path to list')

directory_create_parser = directory_subparsers.add_parser('create', help='create a directory')
add_default_options(directory_create_parser)
directory_create_parser.add_argument('path', nargs='+', help='directory to create')

directory_working_parser = directory_subparsers.add_parser('working', help='Print the current working directory')
add_default_options(directory_working_parser)


class Directory(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "directory"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "list": directory_list_parser,
            "change": directory_list_parser,
            "create": directory_create_parser,
            "working": directory_working_parser,
        }
        self._aliases = [
            AgentCommandAlias("ls", self._name, "list"),
            AgentCommandAlias("cd", self._name, "change"),
            AgentCommandAlias("mkdir", self._name, "create"),
            AgentCommandAlias("pwd", self._name, "working"),
        ]

    @property
    def name(self) -> str:
        return self._name

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @property
    def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
        return directory_parser

    @cmd2.with_argparser(directory_parser)
    def do_directory(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def directory_list(self, args) -> Task:
        if isinstance(args, str):
            parser = self.get_subcommand_parser("list")
            args = parser.parse_args(args)

        command_args = " ".join(args.path)
        task = Task(self._agent.instance, command="ls", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    directory_list_parser.set_defaults(func=directory_list)

    def directory_change(self, args) -> Task:
        if isinstance(args, str):
            parser = directory_change_parser
            args = parser.parse_args(args)

        command_args = " ".join(args.path)
        task = Task(self._agent.instance, command="cd", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    directory_change_parser.set_defaults(func=directory_change)

    def directory_create(self, args) -> Task:
        if isinstance(args, str):
            parser = directory_change_parser
            args = parser.parse_args(args)

        command_args = " ".join(args.path)
        task = Task(self._agent.instance, command="mkdir", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    directory_create_parser.set_defaults(func=directory_create)

    def directory_pwd(self, args) -> Task:
        if isinstance(args, str):
            args = directory_working_parser.parse_args(args)

        task = Task(self._agent.instance, command="pwd",
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    directory_working_parser.set_defaults(func=directory_pwd)
