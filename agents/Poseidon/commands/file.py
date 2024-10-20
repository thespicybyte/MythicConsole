import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

file_parser = Cmd2ArgumentParser()
file_subparsers = file_parser.add_subparsers(title='subcommands', help='subcommand help')

file_copy_parser = file_subparsers.add_parser('copy', help='Copy a file')
file_copy_parser.add_argument('source', help='source path')
file_copy_parser.add_argument('destination', help='destination path')
add_default_options(file_copy_parser)

file_cat_parser = file_subparsers.add_parser('cat', help='Cat a file')
file_cat_parser.add_argument('path', nargs='+', help='Path to file to cat')
add_default_options(file_cat_parser)

file_head_parser = file_subparsers.add_parser('head', help='Read the first X lines from a file')
file_head_parser.add_argument('path', help='Path to the file to read')
file_head_parser.add_argument('lines', type=int, help='Number of lines to read from the beginning of a file')
add_default_options(file_head_parser)

file_move_parser = file_subparsers.add_parser('move', help='Move a file')
file_move_parser.add_argument('source', help='source path')
file_move_parser.add_argument('destination', help='destination path')
add_default_options(file_move_parser)

file_download_parser = file_subparsers.add_parser('download', help='Download a file from the target')
file_download_parser.add_argument('path', nargs='+', help='path to file to download')
add_default_options(file_download_parser)

file_remove_parser = file_subparsers.add_parser('remove', help='Remove a file')
file_remove_parser.add_argument('path', nargs='+', help='path to file to remove')
add_default_options(file_remove_parser)


class File(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "file"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "copy": file_copy_parser,
            "download": file_download_parser,
            "move": file_move_parser,
            "cat": file_cat_parser,
            "head": file_head_parser,
            "remove": file_remove_parser,
        }
        self._aliases = [
            AgentCommandAlias("cp", self._name, "copy"),
            AgentCommandAlias("cat", self._name, "cat"),
            AgentCommandAlias("download", self._name, "download"),
            AgentCommandAlias("head", self._name, "head"),
            AgentCommandAlias("mv", self._name, "move"),
            AgentCommandAlias("rm", self._name, "remove"),
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
        return file_parser

    @cmd2.with_argparser(file_parser)
    def do_file(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def file_copy(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = file_copy_parser.parse_args(args)

        command_args = {
            "source": args.source,
            "destination": args.destination
        }

        task = Task(self._agent.instance, command="cp", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    file_copy_parser.set_defaults(func=file_copy)

    def file_cat(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            subcommand_parser = file_cat_parser
            args = subcommand_parser.parse_args(args)

        path = " ".join(args.path)
        task = Task(self._agent.instance, command="cat", args=path,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    file_cat_parser.set_defaults(func=file_cat)

    def file_head(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            subcommand_parser = file_cat_parser
            args = subcommand_parser.parse_args(args)

        command_args = {
            "path": args.path,
            "lines": args.lines,
        }
        task = Task(self._agent.instance, command="head", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    file_head_parser.set_defaults(func=file_head)

    def file_move(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = file_move_parser.parse_args(args)

        command_args = {
            "source": args.source,
            "destination": args.destination
        }

        task = Task(self._agent.instance, command="mv", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    file_move_parser.set_defaults(func=file_move)

    def file_download(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = file_download_parser.parse_args(args)

        path = " ".join(args.path)
        task = Task(self._agent.instance, command="download", args=path,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    file_download_parser.set_defaults(func=file_download)

    def file_remove(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = file_download_parser.parse_args(args)

        path = " ".join(args.path)
        task = Task(self._agent.instance, command="rm", args=path,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    file_remove_parser.set_defaults(func=file_remove)
