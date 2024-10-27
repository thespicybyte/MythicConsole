import os
import importlib
import shlex
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional

from cmd2 import cmd2, argparse_custom, with_argparser, Cmd, Cmd2ArgumentParser
from glob import glob

from rich.console import RenderableType
from textual.worker import Worker

from backend import MythicInstance, User, Operation, Payload
from utils.logger import logger
from . import mythic_command_parsers
from ..operation.queries import OperationQueries
from ..payload.queries import PayloadQueries
from ..tasker.tasker import Tasker
from ..formatter.formatter import Formatter, DefaultFormatter
from ..user import UserQueries


class MythicAgent:
    pass


def add_default_options(parser: cmd2.argparse_custom.Cmd2ArgumentParser):
    parser.add_argument('-bg', '--background', action='store_true', help='run task in background')


class AgentCommandAlias:
    def __init__(self, name: str, command: str, subcommand: str = "", options_prefix: str = ""):
        self.name = name
        self.command = command
        self.subcommand = subcommand
        self.options_prefix = options_prefix

    def __eq__(self, other) -> bool:
        if not isinstance(other, AgentCommandAlias):
            return False

        if self.command == other.command and self.subcommand == other.subcommand:
            return True

        return False

    def __str__(self) -> str:
        return f"{self.command} {self.subcommand} {self.options_prefix}"

    def __dict__(self):
        return {self.name: self.__str__()}


class AgentCommand(ABC, cmd2.Cmd):
    def __init__(self, agent: MythicAgent):
        super().__init__()
        self._agent: MythicAgent = agent

    def __eq__(self, other) -> bool:
        if not isinstance(other, AgentCommand):
            return False

        return self.name == other.name

    def __str__(self):
        return self.name

    @property
    @abstractmethod
    def name(self) -> str:
        """name of the command"""
        pass

    @property
    @abstractmethod
    def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
        """List of sub command parsers"""
        pass

    @property
    @abstractmethod
    def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
        """return the parser for the command"""

    @property
    @abstractmethod
    def aliases(self) -> List[AgentCommandAlias]:
        """Available aliases for an agent"""
        pass

    def get_subcommands(self) -> List[str]:
        """
        Get the available subcommands for the command

        :return: List of subcommands
        """
        return list(self.subcommand_parsers.keys())

    def get_subcommand_options(self, subcommand: str) -> List[str]:
        """
        Get a list of options for a specified subcommand.

        :param subcommand: subcommand to get options for
        :return: return a list of possible options for a command. If none, return an empty list.
        """
        parser = self.subcommand_parsers.get(subcommand)
        if not parser:
            return []

        return self.get_parser_options(parser)

    def get_subcommand_parser(self, subcommand: str) -> cmd2.argparse_custom.Cmd2ArgumentParser | None:
        return self.subcommand_parsers.get(subcommand)

    @classmethod
    def get_parser_options(cls, parser: Cmd2ArgumentParser) -> List[str]:
        options = []
        for option in parser._actions:
            for flag in option.option_strings:
                options.append(flag)

        return options


ScriptCommand = AgentCommand


# noinspection PyRedeclaration
class MythicAgent:
    def __init__(self, name: str, instance: MythicInstance, formatter: Formatter, tasker: Tasker = None):
        self.instance = instance
        self.mythic = instance.mythic
        self.name = name
        self.formatter = formatter
        self.tasker = Tasker(instance)
        self._commands: List[AgentCommand] = []
        self._aliases: List[AgentCommandAlias] = []
        self._scripts: List[ScriptCommand] = []
        self._current_foreground_task: Optional[Worker] = None

        if tasker:
            self.tasker = tasker

        self._set_commands()

    @property
    def commands(self) -> List[AgentCommand]:
        return self._commands

    @commands.setter
    def commands(self, commands: List[AgentCommand]):
        self._commands = commands

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

    @aliases.setter
    def aliases(self, aliases: List[AgentCommandAlias]):
        self._aliases = aliases

    @property
    def scripts(self) -> List[ScriptCommand]:
        return self._scripts

    @scripts.setter
    def scripts(self, scripts: List[ScriptCommand]):
        self._scripts = scripts

    @property
    def current_foreground_task(self) -> Worker:
        return self._current_foreground_task

    @current_foreground_task.setter
    def current_foreground_task(self, worker: Worker):
        self._current_foreground_task = worker

    def _get_commands(self) -> List[AgentCommand]:
        return self._commands or []

    def _get_aliases_names(self) -> List[str]:
        items = []
        for alias in self._aliases:
            items.append(alias.name)

        return items

    def _get_script_names(self) -> List[str]:
        items = []
        for script in self._scripts:
            items.append(script.name)

        return items

    def get_command(self, command: str) -> AgentCommand | None:
        for cmd in self._commands:
            if cmd.name == command:
                return cmd

        return None

    def get_alias(self, command: str) -> AgentCommandAlias | None:
        for alias in self._aliases:
            if alias.name == command:
                return alias

        return None

    def get_script(self, command: str) -> ScriptCommand | None:
        for script in self._scripts:
            if script.name == command:
                return script

        return None

    def is_command(self, value: str) -> bool:
        for command in self._commands:
            if command.name == value:
                return True
        return False

    def is_alias(self, value: str) -> bool:
        for alias in self._aliases:
            if alias.name == value:
                return True
        return False

    def is_script(self, value: str) -> bool:
        for script in self._scripts:
            if script.name == value:
                return True
        return False

    def get_completer_items(self, line: str) -> List[str]:
        items = []
        if line.endswith("\""):
            return items

        try:
            tokens = shlex.split(line)
        except:
            return items

        if len(tokens) == 1:
            # return only commands and aliases
            for command in self._get_commands():
                items.append(command.name)
            for alias_name in self._get_aliases_names():
                items.append(alias_name)
            for script_name in self._get_script_names():
                items.append(script_name)

        elif len(tokens) == 2:
            # check if command is in aliases, if so, get subcommand from alias_name, remove prefix options from subcommand options
            # if command is not in aliases, return command's subcommand
            command = tokens[0]
            alias = self.get_alias(command)
            if alias:
                command = alias.command
                subcommand = alias.subcommand
                option_tokens = shlex.split(alias.options_prefix)
                subcommand_parser = self.get_subcommand_parser(alias.command, subcommand)
                if subcommand_parser:
                    for option in subcommand_parser._actions:
                        for option_token in option_tokens:
                            if not option_token.startswith("-"):
                                continue
                            if option_token not in option.option_strings:
                                items += option.option_strings
                                continue

                        items += option.option_strings

            script = self.get_script(command)
            if script:
                parser = script.get_subcommand_parser(command)
                for option in parser._actions:
                    items += option.option_strings

            for subcommand in self.get_subcommands(command):
                items.append(subcommand)

            agent_command = self.get_command(command)
            if agent_command:
                command_parser = agent_command.command_parser
                if command_parser:
                    for option in command_parser._actions:
                        items += option.option_strings

        else:
            # return the subcommands options
            command = tokens[0]

            subcommand = None
            if self.is_alias(command):
                alias = self.get_alias(command)
                command = alias.command
                subcommand = alias.subcommand

            if not subcommand:
                if self.get_subcommands(command):
                    subcommand = tokens[1]

            options = self.get_subcommand_options(command, subcommand)
            for option in options:
                if option in tokens:
                    continue
                for token in tokens:
                    if token == option:
                        continue
                    if option in items:
                        continue
                items.append(option)

        return items

    def get_subcommands(self, command_name: str) -> List[str]:
        for command in self._commands:
            if command.name == command_name:
                return command.get_subcommands()

        return []

    def get_subcommand_options(self, command_name: str, subcommand_name: str = None):
        if not subcommand_name:
            parser = self.get_command_parser(command_name)
            return self.get_parser_options(parser)

        for command in self._commands:
            if command.name == command_name:
                return command.get_subcommand_options(subcommand_name)

        return []

    def get_subcommand_parser(self, command_name: str,
                              subcommand_name: str) -> cmd2.argparse_custom.Cmd2ArgumentParser | None:
        for command in self._commands:
            if command.name == command_name:
                return command.get_subcommand_parser(subcommand_name)

        return None

    def get_command_parser(self, command_name: str) -> cmd2.argparse_custom.Cmd2ArgumentParser | None:
        for command in self._commands:
            if command.name == command_name:
                return command.command_parser

        return None

    @classmethod
    def get_parser_options(cls, parser: Cmd2ArgumentParser) -> List[str]:
        options = []
        for option in parser._actions:
            for flag in option.option_strings:
                options.append(flag)

        return options

    def get_command_classes(self) -> List[AgentCommand]:
        command_files = self.get_command_files()
        self.commands = []
        self.aliases = []

        for path in command_files:
            module_name = path.stem
            if "_" in module_name:
                tokens = module_name.split("_")
                class_name = ""
                for token in tokens:
                    class_name += token.capitalize()
            else:
                class_name = module_name.capitalize()

            try:
                # Dynamically load the module
                module_path = f"agents.{self.name.capitalize()}.commands.{module_name}"
                module = importlib.import_module(module_path)

                # Get the class from the module
                command_class = getattr(module, class_name, None)

                if command_class is None:
                    logger.debug(f"Class {class_name} not found in {module_name}.py")
                    continue

                # verify class is an AgentCommand
                if not issubclass(command_class, AgentCommand):
                    logger.debug(f"{command_class.__name__} is not an AgentCommand")
                    continue

                agent_command = command_class(self)
                self.commands.append(agent_command)
                self.aliases += agent_command.aliases

            except (ImportError, AttributeError) as e:
                logger.warning(f"Failed to load class {class_name} from {module_name}.py: {e}")

        return self.commands

    def get_script_classes(self) -> List[ScriptCommand]:
        script_files = self.get_script_files()
        self.scripts = []

        for path in script_files:
            module_name = path.stem
            class_name = module_name.capitalize()
            try:
                # Dynamically load the module
                module_path = f"agents.{self.name.capitalize()}.scripts.{module_name}"
                module = importlib.import_module(module_path)

                # Get the class from the module
                script_class = getattr(module, class_name, None)

                if script_class is None:
                    logger.debug(f"Class {class_name} not found in {module_name}.py")
                    continue

                # verify class is an AgentCommand
                if not issubclass(script_class, ScriptCommand):
                    logger.debug(f"{script_class.__name__} is not an ScriptCommand")
                    continue

                script = script_class(self)
                self.scripts.append(script)

            except (ImportError, AttributeError) as e:
                logger.warning(f"Failed to load class {class_name} from {module_name}.py: {e}")

        return self.commands

    def get_command_files(self) -> List[Path]:
        """
        Enumerate the agents `commands` directory for a list of files that should contain
        :return: List of paths
        """
        return self.get_files("commands")

    def get_script_files(self) -> List[Path]:
        return self.get_files("scripts")

    def get_files(self, folder: str) -> List[Path]:
        target_files = []
        project_dir = Path(__file__).parent.parent.parent
        agents_dir = os.path.join(project_dir, "agents")
        agent_dir = os.path.join(agents_dir, self.name.capitalize())
        folder_path = os.path.join(agent_dir, folder)

        if not os.path.dirname(folder_path):
            logger.debug(f"could not set agent {folder}: {folder_path} not found")
            return target_files

        files = glob(f"{folder_path}/*.py")
        for file in files:
            path = Path(file)
            if path.name == "__init__.py":
                continue
            target_files.append(path)

        return target_files

    def _set_commands(self):
        self.get_command_classes()
        self.get_script_classes()


class MythicCommands(Cmd):
    def __init__(self, instance: MythicInstance):
        super().__init__()
        self.instance = instance
        self._commands: List[str] = []
        self._aliases = [
            AgentCommandAlias("op", "operation"),
        ]
        self._command_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "operation": mythic_command_parsers.operation_parser,
        }
        self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
            "operation list": mythic_command_parsers.operation_list_parser,
            "user list": mythic_command_parsers.user_list_parser,
            "user create": mythic_command_parsers.user_create_parser,
            "payload list": mythic_command_parsers.payload_list_parser,
            "payload download": mythic_command_parsers.payload_download_parser,
        }

    @property
    def commands(self) -> List[str]:
        if not self._commands:
            methods = dir(self)
            commands = [method for method in methods if
                        method.startswith('do_') and callable(getattr(self, method))]
            self._commands = commands

        return self._commands

    @commands.setter
    def commands(self, commands: List[str]):
        self._commands = commands

    def get_aliases(self) -> list[AgentCommandAlias]:
        return self._aliases

    def get_alias(self, command: str) -> AgentCommandAlias | None:
        for alias in self._aliases:
            if alias.name == command:
                return alias

        return None

    def get_subcommands(self, command: str) -> list[str]:
        subcommands = []
        for key in self._subcommand_parsers.keys():
            if key.startswith(command):
                values = key.split(" ")
                if len(values) == 2:
                    subcommands.append(values[1])

        return subcommands

    def get_command_parser(self, command: str) -> cmd2.argparse_custom.Cmd2ArgumentParser | None:
        return self._command_parsers.get(command)

    def get_subcommand_parser(self, subcommand: str) -> cmd2.argparse_custom.Cmd2ArgumentParser | None:
        return self._subcommand_parsers.get(subcommand)

    def get_subcommand_options(self, command_name: str, subcommand_name: str):
        options = []
        if subcommand_name:
            parser = self.get_subcommand_parser(f"{command_name} {subcommand_name}")
        else:
            options += self.get_subcommands(command_name)
            parser = self.get_command_parser(command_name)

        if not parser:
            return []

        for option in parser._actions:
            for flag in option.option_strings:
                options.append(flag)

        return options

    def _get_aliases_names(self) -> List[str]:
        items = []
        for alias in self._aliases:
            items.append(alias.name)

        return items

    def get_completer_items(self, line: str) -> List[str]:
        items = []
        tokens = shlex.split(line)

        if len(tokens) == 1:
            for command in self.commands:
                items.append(command.removeprefix("do_"))
            for alias_name in self._get_aliases_names():
                items.append(alias_name)

        elif len(tokens) == 2:
            # check if command is in aliases, if so, get subcommand from alias_name, remove prefix options from subcommand options
            # if command is not in aliases, return command's subcommand
            command = tokens[0]
            alias_name = self.get_alias(command)
            if alias_name:
                items = self.get_subcommand_options(alias_name.command, alias_name.subcommand)

            for subcommand in self._subcommand_parsers.keys():
                if subcommand.startswith(f"{command} "):
                    items.append(subcommand.removeprefix(f"{command} "))

        else:
            # return the subcommands options
            command = tokens[0]
            subcommand = tokens[1]
            items = self.get_subcommand_options(command, subcommand)

        return items

    @with_argparser(mythic_command_parsers.user_parser)
    def do_user(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    async def _user_list(self, _args):
        try:
            user_ids = await UserQueries.get_all_users(self.instance.mythic)
            user_info = []
            for user_id in sorted(user_ids):
                user = User(self.instance, user_id=user_id)
                await user.query()
                user_info.append([str(user.id), user.username, user.current_operation_name or "", str(user.admin)])

            headers = ["id", "username", "active operation", "admin"]
            return DefaultFormatter().build_table(*user_info, headers=headers, title="Users")
        except Exception as e:
            logger.error(e)
            return f"Error: {e}"

    mythic_command_parsers.user_list_parser.set_defaults(func=_user_list)

    async def _user_create(self, args) -> RenderableType:
        try:
            user = User(self.instance, username=args.username)
            await user.create(args.password)
            await user.query()

            user_info = [[str(user.id), user.username, user.current_operation_name or "", str(user.admin)]]

            headers = ["id", "username", "current operation", "admin"]
            return DefaultFormatter().build_table(*user_info, headers=headers, title="Users")
        except Exception as e:
            logger.error(e)
            return f"Error: {e}"

    mythic_command_parsers.user_create_parser.set_defaults(func=_user_create)

    @with_argparser(mythic_command_parsers.operation_parser)
    def do_operation(self, args):
        func = getattr(args, 'func', None)
        if func:
            return func(self, args)

    async def _operation_list(self, _args):
        try:
            operation_ids = await OperationQueries.get_all_operations(self.instance.mythic)
            operation_info = []
            for operation_id in sorted(operation_ids):
                operation = Operation(self.instance, operation_id=operation_id)
                await operation.query()
                operation_info.append([str(operation.id), operation.name, str(operation.deleted)])

            headers = ["id", "operation name", "deleted"]
            return DefaultFormatter().build_table(*operation_info, headers=headers, title="Operations")
        except Exception as e:
            logger.error(e)
            return f"Error: {e}"

    mythic_command_parsers.operation_list_parser.set_defaults(func=_operation_list)

    @with_argparser(mythic_command_parsers.payload_parser)
    def do_payload(self, args):
        func = getattr(args, 'func', None)
        if func:
            return func(self, args)

    async def _payload_list(self, _args):
        try:
            if not self.instance.mythic.current_operation_id:
                return "Error: Operation not set"

            payload_ids = await PayloadQueries.get_all_payloads(self.instance.mythic,
                                                                self.instance.mythic.current_operation_id)
            payload_info = []
            for payload_id in sorted(payload_ids):
                payload = Payload(self.instance, payload_id=payload_id)
                await payload.query()
                payload_info.append([str(payload.id), payload.creation_time, payload.payload_type_name,
                                     payload.description, "\n".join(payload.payload_c2profiles),
                                     payload.username, payload.uuid, payload.build_phase])

            headers = ["id", "creation time", "payload type", "description", "profiles",
                       "username", "payload uuid", "build status"]

            return DefaultFormatter().build_table(*payload_info, headers=headers, title="Payloads")
        except Exception as e:
            logger.error(e)
            return f"Error: {e}"

    mythic_command_parsers.payload_list_parser.set_defaults(func=_payload_list)

    async def _payload_download(self, args):
        try:
            path = " ".join(args.path)
            path = Path(path)

            if not os.path.isdir(path.parent):
                os.makedirs(path.parent, exist_ok=True)

            payload = Payload(self.instance, payload_id=args.id)
            await payload.query()
            await payload.download(path)
            return f"[+] Payload {args.id} saved to {path}"

        except Exception as e:
            logger.error(e)
            return f"[-] Error: {e}"

    mythic_command_parsers.payload_download_parser.set_defaults(func=_payload_download)
