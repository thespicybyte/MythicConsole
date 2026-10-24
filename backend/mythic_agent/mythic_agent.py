import argparse
import json
import os
import importlib
import shlex
import types
from pathlib import Path
from typing import List, Dict, Iterable, Optional, Tuple

from cmd2 import cmd2, with_argparser, Cmd, Cmd2ArgumentParser
from glob import glob
from mythic import mythic

from rich.console import RenderableType
from textual.worker import Worker

from backend import MythicInstance, Task, User, Operation, Payload
from utils.logger import logger
from screens.prompts import TaskPrompt
from . import mythic_command_parsers
from ..callback.queries import CallbackQueries
from ..operation.queries import OperationQueries
from ..payload.queries import PayloadQueries
from ..tasker.tasker import Tasker
from ..formatter.formatter import Formatter, DefaultFormatter
from ..user import UserQueries


class MythicAgent:
    pass


def add_default_options(parser: Cmd2ArgumentParser):
    parser.add_argument('-bg', '--background', action='store_true', help='run task in background')


def remove_background_option(parser: Cmd2ArgumentParser):
    """Strip the -bg/--background flag added by add_default_options (opt-out, e.g. exit)."""
    for action in list(parser._actions):
        if "--background" in action.option_strings:
            parser._remove_action(action)
            for group in parser._action_groups:
                if action in group._group_actions:
                    group._group_actions.remove(action)
            for option_string in action.option_strings:
                parser._option_string_actions.pop(option_string, None)


class AgentCommandAlias:
    def __init__(self, name: str, command: str, subcommand: str = "", description: str = "", options_prefix: str = ""):
        self.name = name
        self.description = description
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


_JSON_OBJECT_TEMPLATES = {
    "CredentialJson": '{"realm": "...", "account": "...", "credential": "...", "type": "plaintext|hash|ticket"}',
    "AgentConnect": '{"host": "...", "agent_uuid": "...", "c2_profile": {"name": "...", "parameters": {...}}}',
    "LinkInfo": '{"host": "...", "callback_uuid": "...", "c2_profile": {"name": "...", "parameters": {...}}}',
}

_SKIP_SERIALIZE_KEYS = {"background", "func", "cmd2_statement", "cmd2_subcommand_func"}


def _json_object_loader(flag: str, template: str):
    """argparse `type=` for a rich param whose server-side shape is a JSON object."""

    def _load(value: str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError) as e:
            raise argparse.ArgumentTypeError(f"{flag} expects a JSON object, e.g. {template}") from e
        if not isinstance(parsed, dict):
            raise argparse.ArgumentTypeError(f"{flag} expects a JSON object, e.g. {template}")
        return parsed

    return _load


def _typed_array_loader(flag: str, choices: Optional[List[str]]):
    """argparse `type=` for TypedArray: a JSON list of [type, value] pairs."""
    sample_type = choices[0] if choices else "type"
    template = f'[["{sample_type}", "value"]]'

    def _load(value: str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError) as e:
            raise argparse.ArgumentTypeError(
                f"{flag} expects a JSON array of [type, value] pairs, e.g. {template}") from e
        if not isinstance(parsed, list):
            raise argparse.ArgumentTypeError(f"{flag} expects a JSON array of [type, value] pairs")
        for item in parsed:
            if not (isinstance(item, list) and len(item) == 2):
                raise argparse.ArgumentTypeError(f"{flag} expects each element to be a [type, value] pair")
            if choices and item[0] not in choices:
                raise argparse.ArgumentTypeError(f"{flag} element type {item[0]!r} must be one of {choices}")
        return parsed

    return _load


def _loaded_command_validator(agent: Optional["MythicAgent"]):
    """argparse `type=` for choices_are_loaded_commands: fail-open when the loaded set is unknown,
    matching Task.execute's existing fail-open gate."""

    def _validate(value: str) -> str:
        callback = getattr(getattr(agent, "tasker", None), "callback", None) if agent else None
        loaded = getattr(callback, "loaded_commands", None) if callback else None
        if loaded is not None and value not in loaded:
            raise argparse.ArgumentTypeError(f"'{value}' is not a command loaded on this callback")
        return value

    return _validate


def _serialize(ns) -> dict:
    """Namespace -> scripting dict, skipping cmd2/console bookkeeping keys and unset values."""
    return {key: value for key, value in vars(ns).items()
            if key not in _SKIP_SERIALIZE_KEYS and value is not None}


def _group_params(params: List[dict]) -> Dict[str, List[dict]]:
    """Split a command's server parameters into call styles, keyed by parameter_group_name."""
    groups: Dict[str, List[dict]] = {}
    for param in params:
        group_name = param.get("parameter_group_name") or "Default"
        groups.setdefault(group_name, []).append(param)

    for group_params in groups.values():
        group_params.sort(key=lambda p: p.get("ui_position") or 0)

    return groups


def _add_param_argument(parser: Cmd2ArgumentParser, param: dict, agent: Optional["MythicAgent"] = None,
                        all_command_names: Optional[List[str]] = None) -> None:
    flag = f"--{param.get('cli_name') or param['name']}"
    param_type = param.get("type")
    required = bool(param.get("required"))
    default = param.get("default_value") or None
    help_text = param.get("description") or ""
    choices = param.get("choices") or None
    multiple = param_type == "ChooseMultiple"

    # Dynamic-choice kinds take priority over the static ChooseOne/ChooseMultiple handling below,
    # since a param can be type ChooseOne/ChooseMultiple *and* carry one of these flags.
    if param.get("choices_are_all_commands"):
        kwargs = {"choices": all_command_names} if all_command_names else {}
        help_suffix = f"{help_text} (a command name)".strip()
        if multiple:
            parser.add_argument(flag, nargs="+", required=required, help=help_suffix, **kwargs)
        else:
            parser.add_argument(flag, default=default, required=required, help=help_suffix, **kwargs)
        return

    if param.get("choices_are_loaded_commands"):
        validator = _loaded_command_validator(agent)
        help_suffix = f"{help_text} (a command loaded on this callback)".strip()
        if multiple:
            parser.add_argument(flag, nargs="+", type=validator, required=required, help=help_suffix)
        else:
            parser.add_argument(flag, type=validator, default=default, required=required, help=help_suffix)
        return

    if param.get("dynamic_query_function"):
        help_suffix = f"{help_text} (options are provided by the agent at runtime)".strip()
        if multiple:
            parser.add_argument(flag, nargs="+", required=required, help=help_suffix)
        else:
            parser.add_argument(flag, default=default, required=required, help=help_suffix)
        return

    if param_type == "Boolean":
        # default=None (not the usual False) so an unset flag is omitted from the scripting dict
        # rather than sent as an explicit false.
        parser.add_argument(flag, action="store_true", default=None, help=help_text)
    elif param_type == "Number":
        parser.add_argument(flag, type=int, default=default, required=required, help=help_text)
    elif param_type == "Array":
        parser.add_argument(flag, nargs="+", required=required, help=help_text)
    elif param_type == "ChooseOne":
        parser.add_argument(flag, choices=choices, default=default, required=required, help=help_text)
    elif param_type == "ChooseMultiple":
        parser.add_argument(flag, nargs="+", choices=choices, required=required, help=help_text)
    elif param_type in _JSON_OBJECT_TEMPLATES:
        template = _JSON_OBJECT_TEMPLATES[param_type]
        parser.add_argument(flag, type=_json_object_loader(flag, template), default=default,
                            required=required, metavar="JSON",
                            help=f"{help_text} JSON object, e.g. {template}".strip())
    elif param_type == "TypedArray":
        choices_note = f" (types: {choices})" if choices else ""
        parser.add_argument(flag, type=_typed_array_loader(flag, choices), default=default or [],
                            required=required, metavar="JSON",
                            help=f"{help_text} JSON array of [type, value] pairs{choices_note}".strip())
    elif param_type == "File":
        parser.add_argument(flag, default=default, required=False, metavar="PATH|UUID",
                            help=f"{help_text} (local file to upload, or an existing file UUID)".strip())
    elif param_type == "PayloadList":
        parser.add_argument(flag, default=default, required=required, metavar="PAYLOAD_UUID",
                            help=f"{help_text} (payload UUID - see `payload list`)".strip())
    else:
        parser.add_argument(flag, default=default, required=required, help=help_text)


def _dispatch_group(command: "AgentCommand", ns) -> Task:
    """set_defaults(func=...) target for a parameter-group subparser."""
    return command._build_task(ns)


def _build_parsers(name: str, groups: Dict[str, List[dict]], agent: Optional["MythicAgent"] = None,
                   all_command_names: Optional[List[str]] = None):
    if len(groups) <= 1:
        parser = Cmd2ArgumentParser()
        for group_params in groups.values():
            for param in group_params:
                _add_param_argument(parser, param, agent, all_command_names)
        add_default_options(parser)
        return parser, {}

    parser = Cmd2ArgumentParser()
    subparsers = parser.add_subparsers(title='subcommands', help='subcommand help')
    subcommand_parsers: Dict[str, Cmd2ArgumentParser] = {}
    for group_name, group_params in groups.items():
        sub = subparsers.add_parser(group_name, help=f"{name} ({group_name})")
        for param in group_params:
            _add_param_argument(sub, param, agent, all_command_names)
        add_default_options(sub)
        sub.set_defaults(func=_dispatch_group)
        subcommand_parsers[group_name] = sub

    return parser, subcommand_parsers


class AgentCommand(cmd2.Cmd):
    """A command an operator can run against an agent: a hand-written subclass, or an instance
    built by from_server() with a parser generated from the Mythic server's command metadata."""

    def __init__(self, agent: MythicAgent, name: str = None, description: str = "",
                 command_parser: Cmd2ArgumentParser = None,
                 subcommand_parsers: Dict[str, Cmd2ArgumentParser] = None,
                 aliases: List[AgentCommandAlias] = None):
        super().__init__()
        self._agent: MythicAgent = agent
        self._name = name
        self._description = description
        self._command_parser = command_parser
        self._subcommand_parsers: Dict[str, Cmd2ArgumentParser] = subcommand_parsers or {}
        self._aliases: List[AgentCommandAlias] = aliases or []
        self._params: List[dict] = []
        self._file_param_keys: set = set()
        self._required_file_param_keys: Dict[str, str] = {}
        self._flag_param_map: Dict[Optional[str], Dict[str, dict]] = {}
        self.verify_prompt: Optional[TaskPrompt] = None
        self.force_background = False

        if self._name and self._command_parser is not None:
            self._bind_do()

    def __eq__(self, other) -> bool:
        if not isinstance(other, AgentCommand):
            return False

        return self.name == other.name

    def __str__(self):
        return self.name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def subcommand_parsers(self) -> Dict[str, Cmd2ArgumentParser]:
        return self._subcommand_parsers

    @property
    def command_parser(self) -> Cmd2ArgumentParser:
        return self._command_parser

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._aliases

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

    def get_subcommand_parser(self, subcommand: str) -> Cmd2ArgumentParser | None:
        return self.subcommand_parsers.get(subcommand)

    @classmethod
    def get_parser_options(cls, parser: Cmd2ArgumentParser) -> List[str]:
        options = []
        for option in parser._actions:
            for flag in option.option_strings:
                options.append(flag)

        return options

    @classmethod
    def from_server(cls, agent: MythicAgent, spec: dict,
                    all_command_names: Optional[List[str]] = None) -> "AgentCommand":
        """Build a generated command from one server `command` row (cmd/description/commandparameters)."""
        params = spec.get("commandparameters") or []
        groups = _group_params(params)
        parser, subparsers = _build_parsers(spec["cmd"], groups, agent, all_command_names)

        command = cls(agent, name=spec["cmd"], description=spec.get("description") or "",
                      command_parser=parser, subcommand_parsers=subparsers, aliases=[])
        command._params = params
        command._file_param_keys = {
            (p.get("cli_name") or p["name"]).replace("-", "_")
            for p in params if p.get("type") == "File"
        }
        command._required_file_param_keys = {
            (p.get("cli_name") or p["name"]).replace("-", "_"): (p.get("cli_name") or p["name"])
            for p in params if p.get("type") == "File" and bool(p.get("required"))
        }
        # Keyed per parameter group so a flag that repeats across groups (grouped commands)
        # resolves against the right group's param when completing its value.
        command._flag_param_map = {
            (None if len(groups) <= 1 else group_name): {
                f"--{p.get('cli_name') or p['name']}": p for p in group_params
            }
            for group_name, group_params in groups.items()
        }
        return command

    def get_value_candidates(self, flag: str, subcommand: str = None) -> Optional[List[str]]:
        """Candidate values for a value-bearing flag, or None if it's free-form."""
        group_map = self._flag_param_map.get(subcommand) or self._flag_param_map.get(None)
        if not group_map:
            return None

        param = group_map.get(flag)
        if not param:
            return None

        if param.get("choices_are_all_commands"):
            return self._agent._get_command_names() if self._agent else []
        if param.get("choices_are_loaded_commands"):
            callback = getattr(self._agent.tasker, "callback", None) if self._agent else None
            loaded = getattr(callback, "loaded_commands", None) if callback else None
            return sorted(loaded) if loaded else []
        if param.get("dynamic_query_function"):
            return self._agent.get_dynamic_choices(self._name, param.get("name")) if self._agent else []
        if param.get("type") == "PayloadList":
            return list(getattr(self._agent, "_payload_uuid_cache", None) or [])

        choices = param.get("choices")
        return list(choices) if choices else None

    def _build_task(self, ns) -> Task:
        args = _serialize(ns)
        task = Task(self._agent.instance, command=self._name, args=args,
                    callback=self._agent.tasker.callback)
        task.console_args = ns
        task.background = self.force_background or getattr(ns, "background", False)
        if self.verify_prompt:
            task.verify_prompt = self.verify_prompt

        for key in self._file_param_keys:
            value = args.get(key)
            if isinstance(value, str) and os.path.isfile(value):
                task.file_params[key] = value

        for key, label in self._required_file_param_keys.items():
            if args.get(key) is None:
                task.pending_file_params[key] = label

        return task

    def _bind_do(self):
        has_groups = bool(self._subcommand_parsers)

        def _do(_self, ns):
            if has_groups:
                func = getattr(ns, "func", None)
                return func(self, ns) if func is not None else None

            return self._build_task(ns)

        _do.__name__ = f"do_{self._name}"
        _do.__qualname__ = _do.__name__
        bound = with_argparser(self._command_parser)(_do)
        setattr(self, _do.__name__, types.MethodType(bound, self))


ScriptCommand = AgentCommand


class AgentCommands:
    """One agent's command set (generated + curated): name-keyed mapping for dict-patch overrides
    that iterates as command objects. Distinct from MythicCommands (the global cmd2.Cmd set)."""

    def __init__(self, commands: Iterable[AgentCommand] = ()):
        self._by_name: Dict[str, AgentCommand] = {c.name: c for c in commands}

    def __getitem__(self, name: str) -> AgentCommand:
        return self._by_name[name]

    def __setitem__(self, name: str, command: AgentCommand):
        self._by_name[name] = command

    def __delitem__(self, name: str):
        del self._by_name[name]

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def __iter__(self):
        return iter(self._by_name.values())

    def __len__(self) -> int:
        return len(self._by_name)

    def pop(self, name: str, *default):
        return self._by_name.pop(name, *default)

    def get(self, name: str, default=None):
        return self._by_name.get(name, default)

    def add(self, command: AgentCommand):
        self._by_name[command.name] = command

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return [alias for command in self for alias in command.aliases]


_CMD_ATTRS = """
cmd description help_cmd attributes supported_ui_features
commandparameters {
  name cli_name type required default_value description
  parameter_group_name ui_position choices
  choices_are_all_commands choices_are_loaded_commands dynamic_query_function
}
"""


# noinspection PyRedeclaration
class MythicAgent:
    def __init__(self, name: str, instance: MythicInstance, formatter: Formatter, tasker: Tasker = None):
        self.instance = instance
        self.mythic = instance.mythic
        self.name = name
        self.formatter = formatter
        self.tasker = Tasker(instance)
        self._commands: AgentCommands = AgentCommands()
        self._scripts: List[ScriptCommand] = []
        self._current_foreground_task: Optional[Worker] = None
        self._payload_uuid_cache: List[str] = []
        self._dynamic_query_cache: Dict[Tuple[str, str], List[str]] = {}

        if tasker:
            self.tasker = tasker

    @property
    def commands(self) -> AgentCommands:
        return self._commands

    @commands.setter
    def commands(self, commands: AgentCommands):
        self._commands = commands

    @property
    def aliases(self) -> List[AgentCommandAlias]:
        return self._commands.aliases

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
        return list(self._commands)

    def _get_command_names(self) -> List[str]:
        return [command.name for command in self._get_commands()]

    def get_dynamic_choices(self, command_name: str, param_name: str) -> List[str]:
        """Cached options for a `dynamic_query_function` param. Empty when not (yet) resolved -
        value completion then degrades cleanly to free-form, matching an offline/unresolved state."""
        return list(self._dynamic_query_cache.get((command_name, param_name), []))

    def _get_aliases_names(self) -> List[str]:
        return [alias.name for alias in self.aliases]

    def _get_script_names(self) -> List[str]:
        items = []
        for script in self._scripts:
            items.append(script.name)

        return items

    def get_command(self, command: str) -> AgentCommand | None:
        return self._commands.get(command)

    def get_alias(self, command: str) -> AgentCommandAlias | None:
        for alias in self.aliases:
            if alias.name == command:
                return alias

        return None

    def get_script(self, command: str) -> ScriptCommand | None:
        for script in self._scripts:
            if script.name == command:
                return script

        return None

    def is_command(self, value: str) -> bool:
        return value in self._commands

    def is_alias(self, value: str) -> bool:
        return any(alias.name == value for alias in self.aliases)

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

        # A trailing space means the current word is empty: count it as one more
        # (empty) token so "cmd " lists subcommands and "cmd sub " lists its options.
        count = len(tokens) + (1 if tokens and line[-1:].isspace() else 0)

        if count <= 1:
            items.append("help")
            # return only commands and aliases
            for command in self._get_commands():
                items.append(command.name)
            for alias_name in self._get_aliases_names():
                items.append(alias_name)
            for script_name in self._get_script_names():
                items.append(script_name)

        elif count == 2:
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

            # A value-expecting flag immediately before the cursor ("--flag " or a partial word
            # right after one) completes to that flag's candidates instead of the usual
            # flag/subcommand options. Free-form flags (get_value_candidates returns None) and
            # unknown commands fall through to the existing logic below.
            trailing_space = bool(tokens) and line[-1:].isspace()
            preceding_flag = tokens[-1] if trailing_space else (tokens[-2] if len(tokens) >= 2 else None)
            if preceding_flag and preceding_flag.startswith("-"):
                agent_command = self.get_command(command)
                if agent_command:
                    candidates = agent_command.get_value_candidates(preceding_flag, subcommand)
                    if candidates is not None:
                        return candidates

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
        command = self._commands.get(command_name)
        return command.get_subcommands() if command else []

    def get_subcommand_options(self, command_name: str, subcommand_name: str = None):
        if not subcommand_name:
            parser = self.get_command_parser(command_name)
            return self.get_parser_options(parser) if parser else []

        command = self._commands.get(command_name)
        return command.get_subcommand_options(subcommand_name) if command else []

    def get_subcommand_parser(self, command_name: str,
                              subcommand_name: str) -> Cmd2ArgumentParser | None:
        command = self._commands.get(command_name)
        return command.get_subcommand_parser(subcommand_name) if command else None

    def get_command_parser(self, command_name: str) -> Cmd2ArgumentParser | None:
        command = self._commands.get(command_name)
        return command.command_parser if command else None

    @classmethod
    def get_parser_options(cls, parser: Cmd2ArgumentParser) -> List[str]:
        options = []
        for option in parser._actions:
            for flag in option.option_strings:
                options.append(flag)

        return options

    async def _fetch_server_commands(self) -> List[dict]:
        return await mythic.get_all_commands_for_payloadtype(
            self.mythic, self.name, custom_return_attributes=_CMD_ATTRS)

    async def get_agent_commands(self) -> AgentCommands:
        specs = await self._fetch_server_commands()
        all_command_names = [spec["cmd"] for spec in specs]
        return AgentCommands(AgentCommand.from_server(self, spec, all_command_names) for spec in specs)

    async def load_commands(self):
        self.commands = await self.get_agent_commands()
        self.get_script_classes()
        await self._cache_loaded_commands()
        await self._cache_payload_uuids()

    async def _cache_loaded_commands(self):
        callback = self.tasker.callback
        if not callback or not callback.display_id:
            return
        try:
            loaded = await CallbackQueries.get_loaded_commands(self.mythic, callback.display_id)
        except Exception as e:
            logger.warning(f"could not cache loaded commands: {e}")
            return
        if loaded:
            callback.loaded_commands = set(loaded)

    async def _cache_payload_uuids(self):
        """Warm the PayloadList value-completion cache. The completer is synchronous, so a
        network-backed candidate source has to be resolved and cached up front, here."""
        operation_id = getattr(self.mythic, "current_operation_id", None)
        if not operation_id:
            return
        try:
            self._payload_uuid_cache = await PayloadQueries.get_all_payload_uuids(self.mythic, operation_id)
        except Exception as e:
            logger.warning(f"could not cache payload uuids: {e}")

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

        return self.scripts

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


class MythicCommands(Cmd):
    """Global, agent-independent console commands (operation/payload/user), a cmd2.Cmd.
    Unrelated to AgentCommands (a per-agent command collection)."""

    def __init__(self, instance: MythicInstance):
        super().__init__()
        self.instance = instance
        self._commands: List[str] = []
        self._aliases = [
            AgentCommandAlias("op", "operation"),
        ]
        self._command_parsers: Dict[str, Cmd2ArgumentParser] = {
            "operation": mythic_command_parsers.operation_parser,
        }
        self._subcommand_parsers: Dict[str, Cmd2ArgumentParser] = {
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

    def get_command_parser(self, command: str) -> Cmd2ArgumentParser | None:
        return self._command_parsers.get(command)

    def get_subcommand_parser(self, subcommand: str) -> Cmd2ArgumentParser | None:
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
        try:
            tokens = shlex.split(line)
        except:
            return items

        # A trailing space means the current word is empty: count it as one more
        # (empty) token so "cmd " lists subcommands and "cmd sub " lists its options.
        count = len(tokens) + (1 if tokens and line[-1:].isspace() else 0)

        if count <= 1:
            # items.append("help")
            for command in self.commands:
                items.append(command.removeprefix("do_"))
            for alias_name in self._get_aliases_names():
                items.append(alias_name)

        elif count == 2:
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
