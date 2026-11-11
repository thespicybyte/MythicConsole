import argparse
import json
import os
import importlib
import shlex
import tempfile
import types
from pathlib import Path
from typing import List, Dict, Iterable, Optional, Tuple

from cmd2 import cmd2, with_argparser, Cmd, Cmd2ArgumentParser
from glob import glob
from mythic import mythic

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text
from textual.app import active_app
from textual.worker import Worker
from textual_console import ArgparseCompleter, set_completer

from mythic_console.backend import MythicInstance, Task, User, Operation, Payload, Callback, DisabledCommandsProfile
from mythic_console.utils.logger import logger
from mythic_console.utils.environment import Environment
from mythic_console.utils.severity import Severity, severity_style, success, warning, error
from mythic_console.screens.forms import ParamForm, FieldSpec, field_spec_from_param
from mythic_console.screens.prompts import BACK, TaskPrompt, ChoicePrompt, YesNoPrompt
from mythic_console.screens.build_summary import BuildSummary
from mythic_console.screens.select_commands import SelectCommands
from . import mythic_command_parsers
from ..c2_profile.queries import C2ProfileQueries
from ..callback.queries import CallbackQueries
from ..operation.queries import OperationQueries
from ..disabled_commands_profile.queries import DisabledCommandsProfileQueries
from ..payload.queries import PayloadQueries
from ..payload_type.queries import PayloadTypeQueries
from ..tasker.tasker import Tasker
from ..formatter.formatter import Formatter, DefaultFormatter
from ..user import UserQueries


async def _prompt(screen):
    """Push a modal from within a command coroutine's worker and await its dismissal value.
    The only place this module reaches for the running App."""
    return await active_app.get().push_screen_wait(screen)


def _user_from_identifier(instance: MythicInstance, identifier: str) -> User:
    if identifier.isdigit():
        return User(instance, user_id=int(identifier))
    return User(instance, username=identifier)


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

    def _loaded_names(self) -> Optional[set[str]]:
        callback = getattr(self.tasker, "callback", None)
        return getattr(callback, "loaded_commands", None) if callback else None

    def surfaced_commands(self) -> List[AgentCommand]:
        """Catalog commands the operator can actually run on this callback. Fail-open: the full
        catalog when the loaded set is unknown, the loaded subset when it is known."""
        loaded = self._loaded_names()
        commands = self._get_commands()
        if loaded is None:
            return commands
        return [command for command in commands if command.name in loaded]

    def surfaced_aliases(self) -> List[AgentCommandAlias]:
        """Aliases whose target command is surfaced; fail-open when the loaded set is unknown."""
        loaded = self._loaded_names()
        if loaded is None:
            return list(self.aliases)
        return [alias for alias in self.aliases if alias.command in loaded]

    def _get_surfaced_alias_names(self) -> List[str]:
        return [alias.name for alias in self.surfaced_aliases()]

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
            for command in self.surfaced_commands():
                items.append(command.name)
            for alias_name in self._get_surfaced_alias_names():
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
                if parser:
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


_PAYLOAD_BUILD_TIMEOUT_SECONDS = 600


def _config_is_complete(config: dict) -> bool:
    """A config is complete once it has both `selected_os` and `filename`."""
    return bool(config.get("selected_os")) and bool(config.get("filename"))


def _quick_build_command(payload_type_name: str, config: dict) -> str:
    """A single-line, copy-pasteable `payload build` command that reproduces this exact build
    (compact JSON, not pretty-printed)."""
    quick = {
        "payload_type": payload_type_name,
        "selected_os": config.get("selected_os"),
        "filename": config.get("filename"),
        "build_parameters": config.get("build_parameters") or {},
        "c2_profiles": config.get("c2_profiles") or [],
        "commands": config.get("commands"),
        "description": config.get("description", ""),
    }
    compact = json.dumps(quick, separators=(",", ":"))
    return f"payload build {payload_type_name} --config '{compact}'"


def _build_ok(message: str, payload_type_name: str, config: dict) -> Text:
    """A success message followed by a dim, reusable quick-build line."""
    out = success(message)
    out.append("\n")
    out.append(f"[*] quick build: {_quick_build_command(payload_type_name, config)}", style="dim")
    return out


def _build_error(message: str) -> Text:
    """An error/cancel message."""
    return error(message)


def _theme_key_and_status_styles() -> tuple[str, str, str]:
    """(key style, success style, error style) from the running app's active theme, so output
    written to the console (a Rich RenderableType, not a themed Content/Static widget) still
    tracks the theme. Falls back to plain colors when no app is running (e.g. tests)."""
    try:
        key_style = f"bold {active_app.get().current_theme.primary}"
    except LookupError:
        key_style = "bold cyan"
    return key_style, severity_style(Severity.SUCCESS), severity_style(Severity.ERROR)


def _load_config(value: str) -> dict:
    """`--config` accepts a file path or a raw JSON string. An on-disk path wins first, since a
    bare filename (e.g. `build.json`) isn't valid JSON itself and shouldn't be misread as one."""
    if os.path.isfile(value):
        with open(value) as f:
            return json.loads(f.read())
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        raise ValueError(f"--config is neither a readable file nor valid JSON: {value!r}")


def _normalize_build_parameters(raw) -> List[dict]:
    """`payload build` config `build_parameters` -> the `[{"name":..., "value":...}, ...]` shape
    `mythic.create_payload` wants. Accepts the canonical `{name: value}` dict, or a list already in
    the lib's shape (e.g. straight from `exportPayloadConfig`), unchanged."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [{"name": name, "value": value} for name, value in raw.items()]
    if isinstance(raw, list):
        return raw
    raise ValueError(f"build_parameters must be an object or a list, got {type(raw).__name__}")


def _normalize_c2_profile_parameters(raw: Optional[dict]) -> dict:
    """Unwrap the crypto-parameter echo shape (`{"value":..., "enc_key":..., "dec_key":...}`) that
    `exportPayloadConfig` emits for crypto_type params, since `create_payload` wants the plain value."""
    normalized = {}
    for name, value in (raw or {}).items():
        if isinstance(value, dict) and "value" in value:
            value = value["value"]
        normalized[name] = value
    return normalized


def _normalize_c2_profiles(raw) -> List[dict]:
    """`payload build` config `c2_profiles` -> the `[{"c2_profile":..., "c2_profile_parameters":...}]`
    shape `mythic.create_payload` wants. Accepts either the canonical `{"name":..., "parameters":...}`
    entries or raw `exportPayloadConfig` entries (`{"c2_profile":..., "c2_profile_parameters":...}`)."""
    profiles = []
    for entry in raw or []:
        name = entry.get("name") or entry.get("c2_profile")
        if not name:
            raise ValueError(f"c2_profiles entry missing 'name'/'c2_profile': {entry}")
        parameters = entry.get("parameters")
        if parameters is None:
            parameters = entry.get("c2_profile_parameters")
        profiles.append({
            "c2_profile": name,
            "c2_profile_parameters": _normalize_c2_profile_parameters(parameters),
        })
    return profiles


class MythicCommands(Cmd):
    """Global, agent-independent console commands (operation/payload/user), a cmd2.Cmd.
    Unrelated to AgentCommands (a per-agent command collection)."""

    _payload_type_cache: List[str] = []
    _user_cache: List[str] = []
    _operation_cache: List[str] = []
    _blocklist_cache: List[str] = []
    _blocklist_command_cache: List[str] = []

    def __init__(self, instance: MythicInstance):
        super().__init__()
        self.instance = instance
        self._commands: List[str] = []
        self._aliases = [
            AgentCommandAlias("op", "operation"),
        ]
        self._command_parsers: Dict[str, Cmd2ArgumentParser] = {
            "operation": mythic_command_parsers.operation_parser,
            "profiles": mythic_command_parsers.profiles_parser,
            "user": mythic_command_parsers.user_parser,
            "payload": mythic_command_parsers.payload_parser,
            "callback": mythic_command_parsers.callback_parser,
        }
        self._subcommand_parsers: Dict[str, Cmd2ArgumentParser] = {
            "operation list": mythic_command_parsers.operation_list_parser,
            "operation info": mythic_command_parsers.operation_info_parser,
            "operation set": mythic_command_parsers.operation_set_parser,
            "operation create": mythic_command_parsers.operation_create_parser,
            "operation update": mythic_command_parsers.operation_update_parser,
            "operation operator": mythic_command_parsers.operation_operator_parser,
            "operation operator add": mythic_command_parsers.operation_operator_add_parser,
            "operation operator remove": mythic_command_parsers.operation_operator_remove_parser,
            "operation operator role": mythic_command_parsers.operation_operator_role_parser,
            "operation blocklist": mythic_command_parsers.operation_blocklist_parser,
            "operation blocklist list": mythic_command_parsers.operation_blocklist_list_parser,
            "operation blocklist show": mythic_command_parsers.operation_blocklist_show_parser,
            "operation blocklist create": mythic_command_parsers.operation_blocklist_create_parser,
            "operation blocklist add": mythic_command_parsers.operation_blocklist_add_parser,
            "operation blocklist remove": mythic_command_parsers.operation_blocklist_remove_parser,
            "operation blocklist assign": mythic_command_parsers.operation_blocklist_assign_parser,
            "operation blocklist unassign": mythic_command_parsers.operation_blocklist_unassign_parser,
            "operation blocklist delete": mythic_command_parsers.operation_blocklist_delete_parser,
            "profiles list": mythic_command_parsers.profiles_list_parser,
            "user list": mythic_command_parsers.user_list_parser,
            "user create": mythic_command_parsers.user_create_parser,
            "user info": mythic_command_parsers.user_info_parser,
            "user set": mythic_command_parsers.user_set_parser,
            "user set admin": mythic_command_parsers.user_set_admin_parser,
            "user set active": mythic_command_parsers.user_set_active_parser,
            "user delete": mythic_command_parsers.user_delete_parser,
            "payload list": mythic_command_parsers.payload_list_parser,
            "payload types": mythic_command_parsers.payload_types_parser,
            "payload download": mythic_command_parsers.payload_download_parser,
            "payload build": mythic_command_parsers.payload_build_parser,
            "callback export": mythic_command_parsers.callback_export_parser,
            "callback import": mythic_command_parsers.callback_import_parser,
        }

        self._completer_parsers: Dict[str, Cmd2ArgumentParser] = dict(self._command_parsers)
        for alias in self._aliases:
            if not alias.subcommand:
                self._completer_parsers[alias.name] = self._command_parsers[alias.command]
        self._completer = ArgparseCompleter(self._completer_parsers, show_help_option=True)

        payload_type_action = next(
            action for action in mythic_command_parsers.payload_build_parser._actions
            if action.dest == "payload_type"
        )
        set_completer(payload_type_action, lambda word: list(self._payload_type_cache))

        for parser in (
            mythic_command_parsers.user_info_parser,
            mythic_command_parsers.user_set_admin_parser,
            mythic_command_parsers.user_set_active_parser,
            mythic_command_parsers.user_delete_parser,
        ):
            identifier_action = next(a for a in parser._actions if a.dest == "identifier")
            set_completer(identifier_action, lambda word: list(self._user_cache))

        for parser in (
            mythic_command_parsers.operation_operator_add_parser,
            mythic_command_parsers.operation_operator_remove_parser,
            mythic_command_parsers.operation_operator_role_parser,
        ):
            username_action = next(a for a in parser._actions if a.dest == "username")
            set_completer(username_action, lambda word: list(self._user_cache))

        for parser in (
            mythic_command_parsers.operation_info_parser,
            mythic_command_parsers.operation_set_parser,
            mythic_command_parsers.operation_update_parser,
            mythic_command_parsers.operation_operator_add_parser,
            mythic_command_parsers.operation_operator_remove_parser,
            mythic_command_parsers.operation_operator_role_parser,
        ):
            operation_action = next(a for a in parser._actions if a.dest == "operation")
            set_completer(operation_action, lambda word: list(self._operation_cache))

        for parser in (
            mythic_command_parsers.operation_blocklist_show_parser,
            mythic_command_parsers.operation_blocklist_create_parser,
            mythic_command_parsers.operation_blocklist_add_parser,
            mythic_command_parsers.operation_blocklist_remove_parser,
            mythic_command_parsers.operation_blocklist_assign_parser,
            mythic_command_parsers.operation_blocklist_unassign_parser,
            mythic_command_parsers.operation_blocklist_delete_parser,
        ):
            name_action = next(a for a in parser._actions if a.dest == "name")
            set_completer(name_action, lambda word: list(self._blocklist_cache))

        for parser in (
            mythic_command_parsers.operation_blocklist_create_parser,
            mythic_command_parsers.operation_blocklist_add_parser,
            mythic_command_parsers.operation_blocklist_remove_parser,
        ):
            command_action = next(a for a in parser._actions if a.dest == "command")
            set_completer(command_action, lambda word: list(self._blocklist_command_cache))

        for parser in (
            mythic_command_parsers.operation_blocklist_assign_parser,
            mythic_command_parsers.operation_blocklist_unassign_parser,
        ):
            operator_action = next(a for a in parser._actions if a.dest == "operator")
            set_completer(operator_action, lambda word: list(self._user_cache))

    @property
    def commands(self) -> List[str]:
        if not self._commands:
            commands: List[str] = []
            for klass in type(self).__mro__:
                if klass is Cmd:
                    break
                for name, attr in vars(klass).items():
                    if name.startswith('do_') and callable(attr) and name not in commands:
                        commands.append(name)
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

    def get_completer_items(self, line: str):
        return self._completer(line)

    @with_argparser(mythic_command_parsers.user_parser)
    def do_user(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    async def _user_list(self, args):
        try:
            user_ids = await UserQueries.get_all_users(self.instance.mythic, include_deleted=args.all)
            user_info = []
            for user_id in sorted(user_ids):
                user = User(self.instance, user_id=user_id)
                await user.query()
                row = [str(user.id), user.username, user.current_operation_name or "", str(user.admin)]
                if args.all:
                    row.append(str(user.deleted))
                user_info.append(row)

            headers = ["id", "username", "active operation", "admin"]
            if args.all:
                headers.append("deleted")
            return DefaultFormatter().build_table(*user_info, headers=headers, title="Users")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

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
            return error(f"Error: {e}")

    mythic_command_parsers.user_create_parser.set_defaults(func=_user_create)

    async def _user_info(self, args) -> RenderableType:
        try:
            user = _user_from_identifier(self.instance, args.identifier)
            await user.query()

            rows = [
                ["id", str(user.id)],
                ["username", user.username],
                ["admin", str(user.admin)],
                ["active", str(user.active)],
                ["deleted", str(user.deleted)],
                ["current operation", user.current_operation_name or ""],
                ["creation time", user.creation_time or ""],
                ["last login", user.last_login or ""],
            ]
            return DefaultFormatter().build_table(*rows, headers=["field", "value"],
                                                   title=f"User {user.username}")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.user_info_parser.set_defaults(func=_user_info)

    async def _user_set_admin(self, args) -> RenderableType:
        try:
            is_admin = args.value == "true"
            user = _user_from_identifier(self.instance, args.identifier)
            await user.query()
            if not is_admin and not args.force:
                if not await _prompt(YesNoPrompt(f"Revoke admin from '{user.username}'?")):
                    return warning("Cancelled")

            await user.set_admin_status(is_admin)
            await user.query()

            user_info = [[str(user.id), user.username, str(user.admin)]]
            return DefaultFormatter().build_table(*user_info, headers=["id", "username", "admin"],
                                                   title="Users")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.user_set_admin_parser.set_defaults(func=_user_set_admin)

    async def _user_set_active(self, args) -> RenderableType:
        try:
            is_active = args.value == "true"
            user = _user_from_identifier(self.instance, args.identifier)
            await user.query()
            if not is_active and not args.force:
                if not await _prompt(YesNoPrompt(f"Disable account '{user.username}'?")):
                    return warning("Cancelled")

            await user.set_active_status(is_active)
            await user.query()

            user_info = [[str(user.id), user.username, str(user.active)]]
            return DefaultFormatter().build_table(*user_info, headers=["id", "username", "active"],
                                                   title="Users")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.user_set_active_parser.set_defaults(func=_user_set_active)

    async def _user_delete(self, args) -> RenderableType:
        try:
            user = _user_from_identifier(self.instance, args.identifier)
            await user.query()
            if not args.force and not await _prompt(YesNoPrompt(f"Delete user '{user.username}'?")):
                return warning("Cancelled")

            await user.delete()
            await user.query()

            user_info = [[str(user.id), user.username, str(user.active), str(user.deleted)]]
            return DefaultFormatter().build_table(*user_info, headers=["id", "username", "active", "deleted"],
                                                   title="Users")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.user_delete_parser.set_defaults(func=_user_delete)

    @with_argparser(mythic_command_parsers.operation_parser)
    def do_operation(self, args):
        func = getattr(args, 'func', None)
        if func:
            return func(self, args)

    async def _operation_list(self, args):
        try:
            await self.cache_operations()
            verbose = getattr(args, "verbose", False)
            active_operation_id = getattr(self.instance.mythic, "current_operation_id", None)

            operation_ids = await OperationQueries.get_all_operations(self.instance.mythic,
                                                                      include_deleted=verbose)
            operation_info = []
            row_styles = {}
            for index, operation_id in enumerate(sorted(operation_ids)):
                operation = Operation(self.instance, operation_id=operation_id)
                await operation.query()

                if verbose:
                    row = [str(operation.id), operation.name, operation.lead or "",
                           str(len(operation.operators)), str(operation.complete),
                           operation.channel or "", operation.webhook or "",
                           str(operation.alert_count), str(operation.deleted)]
                else:
                    row = [str(operation.id), operation.name]

                if active_operation_id is not None and operation.id == active_operation_id:
                    row_styles[index] = severity_style(Severity.SUCCESS)

                operation_info.append(row)

            if verbose:
                headers = ["id", "operation name", "lead", "operators", "complete", "channel",
                           "webhook", "alert count", "deleted"]
            else:
                headers = ["id", "operation name"]

            return DefaultFormatter().build_table(*operation_info, headers=headers, title="Operations",
                                                  row_styles=row_styles)
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_list_parser.set_defaults(func=_operation_list)

    async def _resolve_operation(self, token: str) -> Operation:
        operation = Operation(self.instance, operation_id=int(token)) if token.isdigit() \
            else Operation(self.instance, name=token)
        await operation.query()
        return operation

    async def _operation_info(self, args) -> RenderableType:
        try:
            operation = await self._resolve_operation(args.operation)

            rows = [
                ["id", str(operation.id)],
                ["name", operation.name],
                ["lead", operation.lead or ""],
                ["channel", operation.channel or ""],
                ["webhook", operation.webhook or ""],
                ["complete", str(operation.complete)],
                ["deleted", str(operation.deleted)],
                ["callbacks", str(len(operation.callbacks))],
            ]
            for member in operation.operator_roles:
                rows.append([f"operator: {member['username']}", member["role"]])

            return DefaultFormatter().build_table(*rows, headers=["field", "value"],
                                                   title=f"Operation {operation.name}")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_info_parser.set_defaults(func=_operation_info)

    async def _operation_set(self, args) -> RenderableType:
        try:
            operation = await self._resolve_operation(args.operation)
            user = await UserQueries.query_by_username(self.instance.mythic, self.instance.mythic.username)
            await operation.select(user["id"])
            self.instance.mythic.current_operation_id = operation.id
            await self.cache_blocklists()
            await self.cache_blocklist_commands()
            return success(f"Set active operation to '{operation.name}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_set_parser.set_defaults(func=_operation_set)

    async def _operation_create(self, args) -> RenderableType:
        try:
            operation = Operation(self.instance, name=args.name)
            await operation.create()
            if args.lead:
                await operation.update(lead_operator_username=args.lead)

            await self.cache_operations()
            return success(f"Created '{args.name}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_create_parser.set_defaults(func=_operation_create)

    async def _operation_update(self, args) -> RenderableType:
        try:
            operation = await self._resolve_operation(args.operation)

            if (args.delete or args.complete) and not args.force:
                action = "Delete" if args.delete else "Mark complete"
                if not await _prompt(YesNoPrompt(f"{action} '{operation.name}'?")):
                    return warning("Cancelled")

            complete = True if args.complete else (False if args.incomplete else None)
            deleted = True if args.delete else (False if args.restore else None)

            await operation.update(
                lead_operator_username=args.lead,
                new_operation_name=args.name,
                channel=args.channel,
                webhook=args.webhook,
                complete=complete,
                deleted=deleted,
            )

            await self.cache_operations()
            return success(f"Updated '{operation.name}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_update_parser.set_defaults(func=_operation_update)

    async def _operation_operator_add(self, args) -> RenderableType:
        try:
            operation = await self._resolve_operation(args.operation)
            await operation.add_operator(args.username)
            return success(f"Added '{args.username}' to '{operation.name}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_operator_add_parser.set_defaults(func=_operation_operator_add)

    async def _operation_operator_remove(self, args) -> RenderableType:
        try:
            operation = await self._resolve_operation(args.operation)
            if not args.force and not await _prompt(
                    YesNoPrompt(f"Remove '{args.username}' from '{operation.name}'?")):
                return warning("Cancelled")

            await operation.remove_operator(args.username)
            return success(f"Removed '{args.username}' from '{operation.name}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_operator_remove_parser.set_defaults(func=_operation_operator_remove)

    async def _operation_operator_role(self, args) -> RenderableType:
        try:
            operation = await self._resolve_operation(args.operation)
            await operation.update_operator(args.username, args.role)
            return success(f"Set '{args.username}' role to '{args.role}' in '{operation.name}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_operator_role_parser.set_defaults(func=_operation_operator_role)

    @classmethod
    def set_blocklist_cache(cls, names: List[str]) -> None:
        cls._blocklist_cache[:] = names

    async def cache_blocklists(self):
        operation_id = getattr(self.instance.mythic, "current_operation_id", None)
        if not operation_id:
            return
        try:
            names = await DisabledCommandsProfileQueries.get_all_profile_names(self.instance.mythic, operation_id)
            self.set_blocklist_cache(names)
        except Exception as e:
            logger.warning(f"could not cache block lists: {e}")

    @classmethod
    def set_blocklist_command_cache(cls, names: List[str]) -> None:
        cls._blocklist_command_cache[:] = names

    async def cache_blocklist_commands(self):
        operation_id = getattr(self.instance.mythic, "current_operation_id", None)
        if not operation_id:
            return
        try:
            payload_types = await PayloadTypeQueries.query_all_payload_types(self.instance.mythic)
            names = set()
            for payload_type in payload_types or []:
                if payload_type.get("deleted") or not payload_type.get("name"):
                    continue
                commands = await mythic.get_all_commands_for_payloadtype(
                    self.instance.mythic, payload_type["name"], custom_return_attributes="cmd attributes")
                for command in commands:
                    if command.get("cmd"):
                        names.add(command["cmd"])
            self.set_blocklist_command_cache(sorted(names))
        except Exception as e:
            logger.warning(f"could not cache block list commands: {e}")

    def _blocklist(self) -> DisabledCommandsProfile:
        operation_id = self.instance.mythic.current_operation_id
        if not operation_id:
            raise Exception("Operation not set")
        return DisabledCommandsProfile(self.instance, operation_id)

    async def _blocklist_list(self, _args) -> RenderableType:
        try:
            profile = self._blocklist()
            rows = await profile.list()
            await self.cache_blocklists()

            grouped: Dict[str, Dict] = {}
            for row in rows:
                name = row.get("name")
                if not name:
                    continue
                entry = grouped.setdefault(name, {"commands": 0, "operators": set()})
                entry["commands"] += 1
                for assignment in row.get("operatoroperations") or []:
                    username = (assignment.get("operator") or {}).get("username")
                    if username:
                        entry["operators"].add(username)

            table_rows = []
            for name in sorted(grouped):
                entry = grouped[name]
                table_rows.append([name, str(entry["commands"]), ", ".join(sorted(entry["operators"]))])

            headers = ["name", "commands", "assigned operators"]
            return DefaultFormatter().build_table(*table_rows, headers=headers, title="Block Lists")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_blocklist_list_parser.set_defaults(func=_blocklist_list)

    async def _blocklist_show(self, args) -> RenderableType:
        try:
            profile = self._blocklist()
            rows = await profile.show(args.name)
            await self.cache_blocklists()

            operators = set()
            table_rows = []
            for row in rows:
                command = row.get("command") or {}
                payload_type = (command.get("payloadtype") or {}).get("name") or ""
                table_rows.append([str(row.get("id")), command.get("cmd") or "", payload_type])
                for assignment in row.get("operatoroperations") or []:
                    username = (assignment.get("operator") or {}).get("username")
                    if username:
                        operators.add(username)

            title = f"Block List {args.name}"
            if operators:
                title += f" (assigned: {', '.join(sorted(operators))})"

            headers = ["row id", "command", "payload type"]
            return DefaultFormatter().build_table(*table_rows, headers=headers, title=title)
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_blocklist_show_parser.set_defaults(func=_blocklist_show)

    async def _blocklist_create(self, args) -> RenderableType:
        try:
            profile = self._blocklist()
            command_ids = [await profile.resolve_command_id(cmd, args.payload_type) for cmd in args.command]
            await profile.create(args.name, command_ids)
            await self.cache_blocklists()
            return success(f"Created block list '{args.name}' with {len(command_ids)} command(s)")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_blocklist_create_parser.set_defaults(func=_blocklist_create)

    async def _blocklist_add(self, args) -> RenderableType:
        try:
            profile = self._blocklist()
            command_id = await profile.resolve_command_id(args.command, args.payload_type)
            await profile.add(args.name, command_id)
            await self.cache_blocklists()
            return success(f"Added '{args.command}' to block list '{args.name}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_blocklist_add_parser.set_defaults(func=_blocklist_add)

    async def _blocklist_remove(self, args) -> RenderableType:
        try:
            if not args.force and not await _prompt(
                    YesNoPrompt(f"Allow '{args.command}' again by removing it from '{args.name}'?")):
                return warning("Cancelled")

            profile = self._blocklist()
            command_id = await profile.resolve_command_id(args.command, args.payload_type)
            await profile.remove(args.name, command_id)
            return success(f"Removed '{args.command}' from block list '{args.name}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_blocklist_remove_parser.set_defaults(func=_blocklist_remove)

    async def _blocklist_assign(self, args) -> RenderableType:
        try:
            user = await UserQueries.query_by_username(self.instance.mythic, args.operator)
            user_id = user.get("id")
            if not user_id:
                raise Exception(f"could not resolve operator '{args.operator}'")

            profile = self._blocklist()
            await profile.assign(args.name, user_id)
            return success(f"Assigned block list '{args.name}' to '{args.operator}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_blocklist_assign_parser.set_defaults(func=_blocklist_assign)

    async def _blocklist_unassign(self, args) -> RenderableType:
        try:
            if not args.force and not await _prompt(
                    YesNoPrompt(f"Unassign block list '{args.name}' from '{args.operator}'?")):
                return warning("Cancelled")

            user = await UserQueries.query_by_username(self.instance.mythic, args.operator)
            user_id = user.get("id")
            if not user_id:
                raise Exception(f"could not resolve operator '{args.operator}'")

            profile = self._blocklist()
            await profile.unassign(user_id)
            return success(f"Unassigned block list '{args.name}' from '{args.operator}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_blocklist_unassign_parser.set_defaults(func=_blocklist_unassign)

    async def _blocklist_delete(self, args) -> RenderableType:
        try:
            if not args.force and not await _prompt(YesNoPrompt(f"Delete block list '{args.name}'?")):
                return warning("Cancelled")

            profile = self._blocklist()
            await profile.delete(args.name)
            await self.cache_blocklists()
            return success(f"Deleted block list '{args.name}'")
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.operation_blocklist_delete_parser.set_defaults(func=_blocklist_delete)

    @with_argparser(mythic_command_parsers.profiles_parser)
    def do_profiles(self, args):
        func = getattr(args, 'func', None)
        if func:
            return func(self, args)

    async def _profiles_list(self, _args):
        try:
            profiles = await C2ProfileQueries.query_all_c2_profiles(self.instance.mythic)
            key_style, success_style, error_style = _theme_key_and_status_styles()
            cards = []
            for profile in sorted(profiles or [], key=lambda p: p.get("name") or ""):
                container_running = bool(profile.get("container_running"))
                server_running = bool(profile.get("running"))
                is_p2p = bool(profile.get("is_p2p"))
                description = (profile.get("description") or "").strip()

                body = Text()
                body.append("container running: ", style=key_style)
                body.append("yes" if container_running else "no",
                             style=success_style if container_running else error_style)
                body.append("\n")
                if not is_p2p:
                    body.append("server running: ", style=key_style)
                    body.append("yes" if server_running else "no",
                                 style=success_style if server_running else error_style)
                    body.append("\n")
                body.append("p2p: ", style=key_style)
                body.append("yes" if is_p2p else "no")
                if description:
                    body.append("\n\n")
                    body.append(description)

                cards.append(Panel(body, title=profile.get("name")))

            if not cards:
                return "No c2 profiles found"

            return Group(*cards)
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.profiles_list_parser.set_defaults(func=_profiles_list)

    @with_argparser(mythic_command_parsers.payload_parser)
    def do_payload(self, args):
        func = getattr(args, 'func', None)
        if func:
            return func(self, args)

    async def _payload_list(self, _args):
        try:
            if not self.instance.mythic.current_operation_id:
                return error("Error: Operation not set")

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
            return error(f"Error: {e}")

    mythic_command_parsers.payload_list_parser.set_defaults(func=_payload_list)

    async def _payload_types(self, _args):
        try:
            payload_types = await PayloadTypeQueries.query_all_payload_types(self.instance.mythic)
            key_style, success_style, error_style = _theme_key_and_status_styles()
            cards = []
            for payload_type in payload_types or []:
                if payload_type.get("deleted"):
                    continue

                agent_type = payload_type.get("agent_type") or ""
                supported_os = ", ".join(payload_type.get("supported_os") or [])
                running = bool(payload_type.get("container_running"))
                note = (payload_type.get("note") or "").strip()

                body = Text()
                body.append("agent type: ", style=key_style)
                body.append(f"{agent_type}\n")
                body.append("supported OS: ", style=key_style)
                body.append(f"{supported_os}\n")
                body.append("container running: ", style=key_style)
                body.append("yes" if running else "no", style=success_style if running else error_style)
                if note:
                    body.append("\n\n")
                    body.append(note)

                cards.append(Panel(body, title=payload_type.get("name")))

            if not cards:
                return "No payload types found"

            return Group(*cards)
        except Exception as e:
            logger.error(e)
            return error(f"Error: {e}")

    mythic_command_parsers.payload_types_parser.set_defaults(func=_payload_types)

    async def _payload_download(self, args):
        try:
            path = " ".join(args.path)
            path = Path(path)

            if not os.path.isdir(path.parent):
                os.makedirs(path.parent, exist_ok=True)

            payload = Payload(self.instance, payload_id=args.id)
            await payload.query()
            await payload.download(path)
            return success(f"[+] Payload {args.id} saved to {path}")

        except Exception as e:
            logger.error(e)
            return error(f"[-] Error: {e}")

    mythic_command_parsers.payload_download_parser.set_defaults(func=_payload_download)

    async def cache_payload_types(self):
        """Warm the `payload build <payload_type>` positional completion cache. The completer is
        synchronous, so the candidate list is resolved and cached up front, mirroring
        MythicAgent._cache_payload_uuids."""
        operation_id = getattr(self.instance.mythic, "current_operation_id", None)
        if not operation_id:
            return
        try:
            payload_types = await PayloadTypeQueries.query_all_payload_types(self.instance.mythic)
            self._payload_type_cache[:] = [p["name"] for p in payload_types or [] if p.get("name")]
        except Exception as e:
            logger.warning(f"could not cache payload types: {e}")

    @classmethod
    def set_user_cache(cls, usernames: List[str]) -> None:
        cls._user_cache[:] = usernames

    async def cache_users(self):
        try:
            self.set_user_cache(await UserQueries.get_all_usernames(self.instance.mythic))
        except Exception as e:
            logger.warning(f"could not cache users: {e}")

    @classmethod
    def set_operation_cache(cls, names: List[str]) -> None:
        cls._operation_cache[:] = names

    async def cache_operations(self):
        try:
            names = await OperationQueries.get_all_operation_names(self.instance.mythic)
            self.set_operation_cache(names)
            logger.debug(f"refreshed operation cache: {len(names)} names")
        except Exception as e:
            logger.warning(f"could not cache operations: {e}")

    async def _payload_build(self, args) -> RenderableType:
        try:
            if not self.instance.mythic.current_operation_id:
                return _build_error("Error: Operation not set")

            payload_type_name = args.payload_type

            config = {}
            if args.config:
                config = _load_config(args.config)

            config_payload_type = config.get("payload_type")
            if config_payload_type and config_payload_type != payload_type_name:
                return _build_error(
                    f"[-] Error: config payload_type '{config_payload_type}' conflicts with "
                    f"requested payload type '{payload_type_name}'")

            if not _config_is_complete(config):
                config = await self._payload_build_questionnaire(payload_type_name, config)
                if config is None:
                    return warning("[-] build cancelled")

            return await self._run_build(args, payload_type_name, config)
        except Exception as e:
            logger.error(e)
            return _build_error(f"[-] Error: {e}")

    async def _run_build(self, args, payload_type_name: str, config: dict) -> RenderableType:
        """The build/download core: a complete canonical config in, a built-and-downloaded
        payload (or an early background-mode return) out. Shared by the non-interactive
        complete-config path and the questionnaire path."""
        selected_os = config.get("selected_os")
        if not selected_os:
            return _build_error("[-] Error: config is missing required field 'selected_os'")

        filename = config.get("filename")
        if not filename:
            return _build_error("[-] Error: config is missing required field 'filename'")

        try:
            build_parameters = _normalize_build_parameters(config.get("build_parameters"))
            c2_profiles = _normalize_c2_profiles(config.get("c2_profiles"))
        except ValueError as e:
            return _build_error(f"[-] Error: {e}")

        commands = config.get("commands")
        description = config.get("description", "")

        if args.background:
            resp = await mythic.create_payload(
                self.instance.mythic,
                payload_type_name=payload_type_name,
                filename=filename,
                operating_system=selected_os,
                c2_profiles=c2_profiles,
                commands=commands,
                build_parameters=build_parameters,
                description=description,
                return_on_complete=False,
            )
            return _build_ok(
                f"[+] Build started: uuid={resp.get('uuid')} status={resp.get('status')}",
                payload_type_name, config)

        resp = await mythic.create_payload(
            self.instance.mythic,
            payload_type_name=payload_type_name,
            filename=filename,
            operating_system=selected_os,
            c2_profiles=c2_profiles,
            commands=commands,
            build_parameters=build_parameters,
            description=description,
            return_on_complete=True,
            timeout=_PAYLOAD_BUILD_TIMEOUT_SECONDS,
        )

        if resp is None:
            return _build_error("[-] Error: timed out waiting for payload build to complete")

        build_phase = resp.get("build_phase")
        uuid = resp.get("uuid")
        if build_phase != "success":
            detail = "\n".join(part for part in (resp.get("build_message"), resp.get("build_stderr")) if part)
            return _build_error(f"[-] Build failed (phase={build_phase}): {detail}")

        if args.output:
            output_path = Path(args.output)
        else:
            fd, temp_name = tempfile.mkstemp(prefix="payload_", suffix=f"_{filename}")
            os.close(fd)
            output_path = Path(temp_name)

        if not os.path.isdir(output_path.parent):
            os.makedirs(output_path.parent, exist_ok=True)

        payload = Payload(self.instance, payload_uuid=uuid)
        await payload.download(output_path)

        return _build_ok(
            f"[+] Payload built and saved to {output_path} (uuid={uuid})",
            payload_type_name, config)

    async def _payload_build_questionnaire(self, payload_type_name: str, config: dict) -> Optional[dict]:
        """Walk the operator through whatever `config` doesn't already answer via a handful of
        aggregated form modals (one for the payload itself, one per selected C2 profile, one for
        the command set), pre-filling every field from `config`, then return the assembled
        canonical config (`{payload_type, selected_os, filename, build_parameters, c2_profiles,
        commands, description}`) for `_run_build`. None means the operator cancelled somewhere
        along the way."""
        payload_type = await PayloadTypeQueries.query_by_name(self.instance.mythic, payload_type_name)
        build_param_schema = await PayloadTypeQueries.query_build_parameters(
            self.instance.mythic, payload_type_name)
        supported_os = payload_type.get("supported_os") or []

        existing_profiles = {entry["name"]: entry.get("parameters") or {}
                             for entry in (config.get("c2_profiles") or [])}

        # Fetched lazily the first time their stage is reached (and cached here), so
        # cancelling at the first form costs no extra server round-trips.
        available: Optional[List[dict]] = None
        supports_multiple = False
        profile_descriptions: dict = {}
        catalog: Optional[List[dict]] = None

        # Running answers, seeded from `config` and carried across Back/forward moves so no
        # step is ever lost. Each stage pre-fills its form from here and writes back on OK.
        state = {
            "selected_os": config.get("selected_os"),
            "filename": config.get("filename") or payload_type_name,
            "build_parameters": dict(config.get("build_parameters") or {}),
            "chosen_names": list(existing_profiles),
            "profile_params": {name: dict(params) for name, params in existing_profiles.items()},
            "commands": config.get("commands"),
        }

        def profiles_needing_params() -> List[dict]:
            return [p for p in available
                    if p["name"] in state["chosen_names"] and (p.get("c2profileparameters"))]

        stage = "payload"
        profile_cursor = 0
        while True:
            if stage == "payload":
                if supported_os:
                    os_spec = FieldSpec(name="selected_os", parameter_type="ChooseOne", choices=supported_os,
                                        initial=state["selected_os"], required=True, label="Operating system")
                else:
                    os_spec = FieldSpec(name="selected_os", parameter_type="String",
                                        initial=state["selected_os"], required=True, label="Operating system")
                filename_spec = FieldSpec(name="filename", parameter_type="String", required=True,
                                          label="Filename", initial=state["filename"])
                payload_specs = [os_spec, filename_spec]
                payload_specs += [field_spec_from_param(param, initial=state["build_parameters"].get(param["name"]))
                                  for param in build_param_schema]

                answers = await _prompt(ParamForm(f"Build '{payload_type_name}'", payload_specs))
                if answers is None:
                    return None
                state["selected_os"] = answers.pop("selected_os")
                state["filename"] = answers.pop("filename")
                state["build_parameters"] = answers
                stage = "profiles"

            elif stage == "profiles":
                if available is None:
                    supported = await PayloadTypeQueries.query_supported_c2_profiles(
                        self.instance.mythic, payload_type_name)
                    available = supported["profiles"]
                    if not available:
                        available = await C2ProfileQueries.query_all_c2_profiles(self.instance.mythic)
                    supports_multiple = supported["supports_multiple"]
                    profile_descriptions = {p["name"]: p.get("description") or "" for p in available}

                if supports_multiple:
                    result = await _prompt(ChoicePrompt(
                        "C2 profile(s)", [p["name"] for p in available], mode="multi",
                        preselected=state["chosen_names"], descriptions=profile_descriptions,
                        show_back=True))
                    if result is BACK:
                        stage = "payload"
                        continue
                    if result is None:
                        return None
                    if not result:
                        # Nothing picked: a payload needs at least one profile, so re-show.
                        continue
                    state["chosen_names"] = list(result)
                else:
                    profile_spec = FieldSpec(name="profile", parameter_type="ChooseOne", required=True,
                                             choices=[p["name"] for p in available],
                                             initial=(state["chosen_names"][0] if state["chosen_names"] else None))
                    result = await _prompt(ParamForm("C2 profile", [profile_spec],
                                                     groups_as_sections=False, show_back=True))
                    if result is BACK:
                        stage = "payload"
                        continue
                    if not result or not result.get("profile"):
                        return None
                    state["chosen_names"] = [result["profile"]]
                profile_cursor = 0
                stage = "profile_params"

            elif stage == "profile_params":
                needing = profiles_needing_params()
                if not needing or profile_cursor >= len(needing):
                    stage = "commands"
                    continue
                if profile_cursor < 0:
                    stage = "profiles"
                    continue
                profile = needing[profile_cursor]
                name = profile["name"]
                existing = state["profile_params"].get(name, {})
                specs = [field_spec_from_param(param, initial=existing.get(param["name"]))
                         for param in profile["c2profileparameters"]]
                answers = await _prompt(ParamForm(f"{name} parameters", specs, show_back=True))
                if answers is None:
                    return None
                if answers is BACK:
                    profile_cursor -= 1
                    continue
                state["profile_params"][name] = answers
                profile_cursor += 1

            elif stage == "commands":
                if catalog is None:
                    catalog = await self._fetch_build_command_catalog(payload_type_name)
                included = state["commands"] if isinstance(state["commands"], list) else None
                # Effective build-parameter values (operator entry, else the param default) so
                # SelectCommands can apply Mythic's `filter_by_build_parameter` command rules.
                effective_build_params = {
                    param["name"]: state["build_parameters"].get(param["name"], param.get("default_value"))
                    for param in build_param_schema}
                result = await _prompt(SelectCommands(
                    catalog, included=included, selected_os=state["selected_os"],
                    build_parameters=effective_build_params, show_back=True))
                if result is SelectCommands.CANCELLED:
                    return None
                if result is BACK:
                    needing = profiles_needing_params()
                    if needing:
                        profile_cursor = len(needing) - 1
                        stage = "profile_params"
                    else:
                        stage = "profiles"
                    continue
                state["commands"] = result
                stage = "confirm"

            elif stage == "confirm":
                c2_profiles = [{"name": p["name"],
                                "parameters": state["profile_params"].get(p["name"], {})}
                               for p in available if p["name"] in state["chosen_names"]]
                confirmed = await _prompt(BuildSummary(
                    payload_type=payload_type_name, selected_os=state["selected_os"],
                    filename=state["filename"], build_parameters=state["build_parameters"],
                    c2_profiles=c2_profiles, commands=state["commands"],
                    description=config.get("description", ""), show_back=True))
                if confirmed is BACK:
                    stage = "commands"
                    continue
                if not confirmed:
                    return None

                return {
                    "payload_type": payload_type_name,
                    "selected_os": state["selected_os"],
                    "filename": state["filename"],
                    "build_parameters": state["build_parameters"],
                    "c2_profiles": c2_profiles,
                    "commands": state["commands"],
                    "description": config.get("description", ""),
                }

    async def _fetch_build_command_catalog(self, payload_type_name: str) -> List[dict]:
        return await mythic.get_all_commands_for_payloadtype(
            self.instance.mythic, payload_type_name, custom_return_attributes=_CMD_ATTRS)

    add_default_options(mythic_command_parsers.payload_build_parser)
    mythic_command_parsers.payload_build_parser.set_defaults(func=_payload_build)

    @with_argparser(mythic_command_parsers.callback_parser)
    def do_callback(self, args):
        func = getattr(args, 'func', None)
        if func:
            return func(self, args)

    async def _callback_export(self, args):
        try:
            path = " ".join(args.path) if args.path else None
            if not path:
                path = os.path.join(Environment().download_directory(),
                                    f"callback_{args.id}_export.json")
            path = Path(path)
            if not os.path.isdir(path.parent):
                os.makedirs(path.parent, exist_ok=True)

            callback = Callback(self.instance, callback_id=args.id)
            await callback.export(str(path))
            return success(f"[+] Callback {args.id} config exported to {path}")
        except Exception as e:
            logger.error(e)
            return error(f"[-] Error: {e}")

    mythic_command_parsers.callback_export_parser.set_defaults(func=_callback_export)

    async def _callback_import(self, args):
        try:
            path = " ".join(args.path)
            if not os.path.isfile(path):
                return error(f"[-] Error: file not found: {path}")

            with open(path, "r") as f:
                config_json = json.loads(f.read())

            await CallbackQueries.import_callback(self.instance.mythic, config_json)
            return success(f"[+] Callback config imported from {path}")
        except json.JSONDecodeError as e:
            logger.error(e)
            return error(f"[-] Error: invalid config JSON in {path}: {e}")
        except Exception as e:
            logger.error(e)
            return error(f"[-] Error: {e}")

    mythic_command_parsers.callback_import_parser.set_defaults(func=_callback_import)
