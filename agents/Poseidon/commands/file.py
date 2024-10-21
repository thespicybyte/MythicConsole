import argparse
from pathlib import Path
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom
from mythic import mythic

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options
from backend.task.task import TaskError

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
file_head_parser.add_argument('--lines', default=20, type=int,
                              help='Number of lines to read from the beginning of a file')
add_default_options(file_head_parser)

file_tail_parser = file_subparsers.add_parser('tail', help='Read the last X lines from a file')
file_tail_parser.add_argument('path', help='Path to the file to read')
file_tail_parser.add_argument('--lines', default=20, type=int,
                              help='Number of lines to read from the end of a file')
add_default_options(file_tail_parser)

file_move_parser = file_subparsers.add_parser('move', help='Move a file')
file_move_parser.add_argument('source', help='source path')
file_move_parser.add_argument('destination', help='destination path')
add_default_options(file_move_parser)

file_download_parser = file_subparsers.add_parser('download', help='Download a file from the target')
file_download_parser.add_argument('path', nargs='+', help='path to file to download')
add_default_options(file_download_parser)

file_upload_parser = file_subparsers.add_parser('upload', help='Upload a file to the target')
file_upload_parser.add_argument('local_path', help='Local path of file to upload')
file_upload_parser.add_argument('remote_path', help='Remote path of file to upload')
file_upload_parser.add_argument('--overwrite', action='store_true', help='Overwrite if file exists')
add_default_options(file_upload_parser)

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
            "tail": file_tail_parser,
            "remove": file_remove_parser,
            "upload": file_upload_parser,
        }
        self._aliases = [
            AgentCommandAlias("cp", self._name, "copy"),
            AgentCommandAlias("cat", self._name, "cat"),
            AgentCommandAlias("download", self._name, "download"),
            AgentCommandAlias("head", self._name, "head"),
            AgentCommandAlias("tail", self._name, "tail"),
            AgentCommandAlias("mv", self._name, "move"),
            AgentCommandAlias("rm", self._name, "remove"),
            AgentCommandAlias("upload", self._name, "upload"),
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
            args = file_cat_parser.parse_args(args)

        path = " ".join(args.path)
        task = Task(self._agent.instance, command="cat", args=path,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    file_cat_parser.set_defaults(func=file_cat)

    def file_head(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            args = file_cat_parser.parse_args(args)

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

    def file_tail(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            args = file_tail_parser.parse_args(args)

        command_args = {
            "path": args.path,
            "lines": args.lines,
        }

        task = Task(self._agent.instance, command="tail", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    file_tail_parser.set_defaults(func=file_tail)

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

    async def file_upload(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = file_upload_parser.parse_args(args)

        try:
            local_path = Path(args.local_path)
            with open(local_path, 'rb') as f:
                data = f.read()

            file_id = await mythic.register_file(self._agent.instance.mythic, filename=local_path.name, contents=data)

            command_args = {
                "file_id": file_id,
                "remote_path": args.remote_path,
                "overwrite": args.overwrite
            }

            task = Task(self._agent.instance, command="upload", args=command_args,
                        callback_display_id=self._agent.tasker.callback.display_id)

            task.console_args = args
            task.background = args.background
            await task.execute()
            if not task.background:
                await task.wait_for_completion()

            return task
        except Exception as e:
            raise TaskError(e)

    file_upload_parser.set_defaults(func=file_upload)
