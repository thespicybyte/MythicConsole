import argparse
from typing import List, Dict

from cmd2 import cmd2, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, MythicAgent, AgentCommandAlias
from screens.prompts import YesNoPrompt

exit_parser = Cmd2ArgumentParser(description="Exit the current session and kill the agent")


class Exit(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent)
        self._name = "exit"
        self._description = "Exit the current session and kill the agent"
        self._subcommand_parsers: Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser] = {}
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
        return exit_parser

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @cmd2.with_argparser(exit_parser)
    def do_exit(self, _args: argparse.Namespace | str) -> Task:
        task = Task(self._agent.instance, command="exit",
                    callback_display_id=self._agent.tasker.callback.display_id)

        task.verify_prompt = YesNoPrompt(question="Exit/kill the current session?")
        task.background = True
        return task
