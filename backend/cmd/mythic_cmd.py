from typing import Optional, List, Union, Coroutine

from cmd2 import Cmd, Statement

import utils
from backend import MythicAgent, MythicInstance
from backend.mythic_agent.mythic_agent import MythicCommands
from utils.logger import logger


class MythicCmd(Cmd):
    def __init__(self, instance: MythicInstance):
        super().__init__()
        self._instance = instance
        self._current_agent: Optional[MythicAgent] = None
        self._loaded_commands: List[str] = []
        self._aliases = []

    @property
    def current_agent(self) -> MythicAgent | None:
        return self._current_agent

    @current_agent.setter
    def current_agent(self, new_agent: MythicAgent):
        self._current_agent = new_agent

    def unload_agent_commands(self):
        for loaded_command in self._loaded_commands:
            try:
                delattr(self, loaded_command)
                logger.debug(f"successfully unloaded command: {loaded_command}")
            except AttributeError as e:
                logger.debug(f"failed to unload {loaded_command}: {e}")
                continue

        self._loaded_commands = []
        alias_names = []
        for alias_name in self.aliases.keys():
            alias_names.append(alias_name)

        for alias_name in alias_names:
            del self.aliases[alias_name]

    def load_mythic_commands(self):
        self.unload_agent_commands()
        mythic_commands = MythicCommands(self._instance)
        methods = mythic_commands.commands
        for method_name in methods:
            method = getattr(mythic_commands, method_name)
            setattr(self, method_name, method)
            self._loaded_commands.append(method_name)
            logger.info(f"successfully loaded command: {method_name.removeprefix('do_')}")

        for alias in mythic_commands.get_aliases():
            alias_function = alias.command
            if alias.subcommand:
                alias_function += f" {alias.subcommand}"
            if alias.options_prefix:
                alias_function += f" {alias.options_prefix}"

            self.aliases[alias.name] = alias_function

        return

    def load_and_register_agent_commands(self):
        """Load command files and register them as commands in the Cmd application."""

        self.unload_agent_commands()

        if not self.current_agent:
            return

        command_classes = self.current_agent.get_command_classes()

        for command in command_classes:
            command_class = command.__class__
            command_name = utils.camel_to_snake(command_class.__name__).lower()

            method_name = f"do_{command_name}"

            if hasattr(command, method_name):
                method = getattr(command, method_name)
                setattr(self, method_name, method)
                self._loaded_commands.append(method_name)
                logger.info(f"successfully loaded command: {command_name}")

            for alias in command.aliases:
                alias_function = alias.command
                if alias.subcommand:
                    alias_function += f" {alias.subcommand}"
                if alias.options_prefix:
                    alias_function += f" {alias.options_prefix}"

                self.aliases[alias.name] = alias_function

        # script_classes = self.current_agent.scripts()
        for script in self.current_agent.scripts:
            script_class = script.__class__
            command_name = script_class.__name__.lower()

            method_name = f"do_{command_name}"

            if hasattr(script, method_name):
                method = getattr(script, method_name)
                setattr(self, method_name, method)
                self._loaded_commands.append(method_name)
                logger.info(f"successfully loaded script: {command_name}")

    def onecmd(self, statement: Union[Statement, str], *, add_to_history: bool = True) -> Coroutine | None:
        """This executes the actual do_* method for a command.

        If the command provided doesn't exist, then it executes default() instead.

        Modified to return the result of the command to the caller

        :param statement: intended to be a Statement instance parsed command from the input stream, alternative
                          acceptance of a str is present only for backward compatibility with cmd
        :param add_to_history: If True, then add this command to history. Defaults to True.
        :return: a flag indicating whether the interpretation of commands should stop
        """
        # For backwards compatibility with cmd, allow a str to be passed in
        if not isinstance(statement, Statement):
            statement = self._input_line_to_statement(statement)

        result = None
        func = self.cmd_func(statement.command)
        if func:
            # Check to see if this command should be stored in history
            if (
                    statement.command not in self.exclude_from_history
                    and statement.command not in self.disabled_commands
                    and add_to_history
            ):
                self.history.append(statement)

            # result = await func(statement)
            return func(statement)

        # else:
        #     stop = self.default(statement)

        return result
