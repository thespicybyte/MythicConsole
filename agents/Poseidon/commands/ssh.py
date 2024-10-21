from typing import List, Dict

from cmd2 import cmd2, argparse_custom, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

ssh_parser = Cmd2ArgumentParser()
directory_subparsers = ssh_parser.add_subparsers(title='subcommands', help='subcommand help')

ssh_execute_parser = directory_subparsers.add_parser('execute', help='list a directory')
add_default_options(ssh_execute_parser)
ssh_execute_parser.add_argument('--hosts', nargs='+', default=["127.0.0.1"], help='Hosts that you will auth to')
ssh_execute_parser.add_argument('--username', required=True,
                                help='Authenticate to the designated hosts using this username')
ssh_execute_parser.add_argument('--command', required=True, help='command to run on  host')
ssh_execute_parser.add_argument('--port', type=int, default=22, help='SSH Port if different than 22')
exec_auth_group = ssh_execute_parser.add_mutually_exclusive_group()
exec_auth_group.add_argument('--password', help='Authenticate to the designated hosts using this password')
exec_auth_group.add_argument('--key', help='Authenticate to the designated hosts using this private key')

ssh_copy_parser = directory_subparsers.add_parser('copy', help='SCP a file to remote host')
add_default_options(ssh_copy_parser)
ssh_copy_parser.add_argument('source', help='path to file to copy')
ssh_copy_parser.add_argument('destination', help='destination to copy file to')
ssh_copy_parser.add_argument('--hosts', nargs='+', default=["127.0.0.1"], help='Hosts that you will auth to')
ssh_copy_parser.add_argument('--username', help='Authenticate to the designated hosts using this username')
ssh_copy_parser.add_argument('--port', type=int, default=22, help='SSH Port if different than 22')
copy_auth_group = ssh_copy_parser.add_mutually_exclusive_group()
copy_auth_group.add_argument('--password', help='Authenticate to the designated hosts using this password')
copy_auth_group.add_argument('--key', help='Authenticate to the designated hosts using this private key')


class Ssh(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "ssh"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "execute": ssh_execute_parser,
            "copy": ssh_copy_parser,
        }
        self._aliases = [
            AgentCommandAlias("scp", self._name, "copy"),
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
        return ssh_parser

    @cmd2.with_argparser(ssh_parser)
    def do_ssh(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def ssh_execute(self, args) -> Task:
        if isinstance(args, str):
            args = ssh_execute_parser.parse_args(args)

        command_args = {
            "username": args.username,
            "password": args.password,
            "private_key": args.key,
            "hosts": args.hosts,
            "port": args.port,
            "command": args.command
        }
        task = Task(self._agent.instance, command="sshauth", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    ssh_execute_parser.set_defaults(func=ssh_execute)

    def ssh_copy(self, args) -> Task:
        if isinstance(args, str):
            args = ssh_copy_parser.parse_args(args)

        command_args = {
            "username": args.username,
            "password": args.password,
            "private_key": args.key,
            "hosts": args.hosts,
            "port": args.port,
            "source": args.source,
            "destination": args.destination,
        }
        task = Task(self._agent.instance, command="sshauth", args=command_args,
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.console_args = args
        task.background = args.background
        return task

    ssh_copy_parser.set_defaults(func=ssh_copy)
