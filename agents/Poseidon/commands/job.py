import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

job_parser = Cmd2ArgumentParser()
job_subparsers = job_parser.add_subparsers(title='subcommands', help='subcommand help')

job_list_parser = job_subparsers.add_parser('list', help='List running/killable jobs')
add_default_options(job_list_parser)

job_kill_parser = job_subparsers.add_parser('kill',
                                            help='Kill a job with the specified ID (from jobs command) - not all jobs are killable though.')
job_kill_parser.add_argument('uuid', help='UUID of job to kil')
add_default_options(job_kill_parser)


class Job(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "job"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "list": job_list_parser,
            "kill": job_kill_parser,
        }
        self._aliases = [
            AgentCommandAlias("jobs", self._name, "list"),
            AgentCommandAlias("jobkill", self._name, "kill"),
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
        return job_parser

    @cmd2.with_argparser(job_parser)
    def do_job(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def job_list(self, args: argparse.Namespace | str) -> Task:
        if isinstance(args, str):
            args = job_list_parser.parse_args(args)

        task = Task(self._agent.instance, command="jobs",
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    job_list_parser.set_defaults(func=job_list)

    def job_kill(self, args: str | argparse.Namespace) -> Task:
        if isinstance(args, str):
            subcommand_parser = job_kill_parser
            args = subcommand_parser.parse_args(args)

        task = Task(self._agent.instance, command="jobkill", args=args.uuid,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    job_kill_parser.set_defaults(func=job_kill)
