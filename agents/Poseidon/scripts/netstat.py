from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom
from rich.console import RenderableType

from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, ScriptCommand
from agents.Poseidon.commands.command import Command

netstat_parser = Cmd2ArgumentParser(description="get a netstat by calling sockstat")
netstat_parser.add_argument('--test')


class Netstat(ScriptCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "netstat"
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {}
        self._aliases = []
        self.command = Command(agent)

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
        return netstat_parser

    @cmd2.with_argparser(netstat_parser)
    async def do_netstat(self, _args) -> RenderableType:
        task = self.command.command_run("sockstat")
        await task.execute()
        await task.wait_for_completion()
        await task.query()
        output = await self._agent.formatter.format_output(task)
        return output
