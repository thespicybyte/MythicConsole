import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

process_parser = Cmd2ArgumentParser()
process_subparsers = process_parser.add_subparsers(title='subcommands', help='subcommand help')

process_list_parser = process_subparsers.add_parser('list',
                                                    help='Get a process listing (with optional regex filtering).')
process_list_parser.add_argument('--regex', help='Regular expression filter to limit which processes are returned')
add_default_options(process_list_parser)

process_kill_parser = process_subparsers.add_parser('kill', help='Kill a process by specifying a PID')
process_kill_parser.add_argument('pid', type=int, help='process id to kill')
add_default_options(process_kill_parser)

process_start_parser = process_subparsers.add_parser('start', help='Execute a command from disk with arguments.')
process_start_parser.add_argument('path', help='Absolute path to the program to run')
process_start_parser.add_argument('--args', nargs=argparse.REMAINDER, help='Array of arguments to pass to the program.')
process_start_parser.add_argument('--env', nargs=argparse.REMAINDER,
                                  help='Array of environment variables to set in the format of Key=Val.')
add_default_options(process_start_parser)


class Process(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "process"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "list": process_list_parser,
            "kill": process_kill_parser,
            "start": process_start_parser,
        }
        self._aliases = [
            AgentCommandAlias("ps", self._name, "list"),
            AgentCommandAlias("kill", self._name, "kill"),
            AgentCommandAlias("run", self._name, "start"),
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
        return process_parser

    @cmd2.with_argparser(process_parser)
    def do_process(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def process_list(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = process_list_parser.parse_args(args)

        command_args = ""
        if args.regex:
            command_args = {"regex_filter": args.regex}

        task = Task(self._agent.instance, command="ps", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    process_list_parser.set_defaults(func=process_list)

    def process_kill(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            args = process_kill_parser.parse_args(args)

        task = Task(self._agent.instance, command="kill", args=str(args.pid),
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    process_kill_parser.set_defaults(func=process_kill)

    def process_start(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            args = process_kill_parser.parse_args(args)

        # if a '-' were passed as an arg to be passed to the command, argparse gets upset.
        env = args.env or []
        command_args = args.args or []

        if args.args:
            for index, token in enumerate(args.args):
                if token == "--env":
                    env = args.args[index + 1:]
                    command_args = args.args[:index]
                    break

        if args.env:
            for index, token in enumerate(args.env):
                if token == "--args":
                    command_args = args.env[index + 1:]
                    env = args.env[:index]
                    break

        command_args = {
            "path": args.path,
            "args": command_args,
            "env": env,
        }
        task = Task(self._agent.instance, command="run", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    process_start_parser.set_defaults(func=process_start)
