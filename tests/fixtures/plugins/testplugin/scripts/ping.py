from typing import Dict, List

from cmd2 import cmd2, Cmd2ArgumentParser
from rich.console import RenderableType

from backend.mythic_agent.mythic_agent import AgentCommandAlias, MythicAgent, ScriptCommand

ping_parser = Cmd2ArgumentParser(description="client-side ping script")


class Ping(ScriptCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "ping"
        self._description = "client-side ping script"
        self._subcommand_parsers: Dict[str, Cmd2ArgumentParser] = {}
        self._aliases: List[AgentCommandAlias] = []

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
    def subcommand_parsers(self) -> Dict[str, Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> Cmd2ArgumentParser:
        return ping_parser

    @cmd2.with_argparser(ping_parser)
    async def do_ping(self, _args) -> RenderableType:
        return "pong"
