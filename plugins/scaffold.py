import json
from pathlib import Path

from .loader import RESERVED_NAMES

_MANIFEST_TEMPLATE = """{{
  "schema_version": 1,
  "name": "{name}",
  "payload_type": "{payload_type}",
  "entrypoint": "{name}:{class_name}",
  "version": "0.1.0",
  "author": "{author}",
  "description": "{description}"
}}
"""

_ENTRYPOINT_TEMPLATE = '''from plugins.base import PluginAgent

from .formatter import {class_name}Formatter


class {class_name}(PluginAgent):
    def __init__(self, instance):
        super().__init__("{payload_type}", instance, {class_name}Formatter())
'''

_FORMATTER_TEMPLATE = '''from backend import Formatter, Task, renders


class {class_name}Formatter(Formatter):
    # Tag a method with the command it renders. With no @renders method,
    # every command falls back to plaintext (the zero-code default).
    #
    # @renders("ls")
    # async def ls(self, task: Task) -> str:
    #     raw = await self.get_raw_output(task)
    #     return raw
    pass
'''

_SCRIPT_EXAMPLE_TEMPLATE = '''# A script is a client-side command. Any ScriptCommand subclass defined in a
# file under scripts/ is discovered and loaded automatically -- name the class
# whatever reads well; the filename does not have to match it.
#
# from typing import Dict, List
# from cmd2 import cmd2, Cmd2ArgumentParser
# from rich.console import RenderableType
# from backend.mythic_agent.mythic_agent import AgentCommandAlias, MythicAgent, ScriptCommand
#
# ping_parser = Cmd2ArgumentParser(description="client-side ping script")
#
# class PingScript(ScriptCommand):
#     def __init__(self, agent: MythicAgent):
#         super().__init__(agent=agent)
#         self._name = "ping"
#         self._description = "client-side ping script"
#         self._subcommand_parsers: Dict[str, Cmd2ArgumentParser] = {}
#         self._aliases: List[AgentCommandAlias] = []
#
#     @property
#     def name(self) -> str:
#         return self._name
#
#     @property
#     def description(self) -> str:
#         return self._description
#
#     @property
#     def aliases(self) -> List[AgentCommandAlias]:
#         return self._aliases
#
#     @property
#     def subcommand_parsers(self) -> Dict[str, Cmd2ArgumentParser]:
#         return self._subcommand_parsers
#
#     @property
#     def command_parser(self) -> Cmd2ArgumentParser:
#         return ping_parser
#
#     @cmd2.with_argparser(ping_parser)
#     async def do_ping(self, _args) -> RenderableType:
#         return "pong"
'''

_COMMAND_EXAMPLE_TEMPLATE = '''# A command file is imported explicitly from your entrypoint's
# get_agent_commands override -- it is not auto-discovered. Name the class
# whatever reads well.
#
# from typing import Dict, List
# from cmd2 import cmd2, Cmd2ArgumentParser
# from backend import Task
# from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, \\
#     add_default_options
#
# net_parser = Cmd2ArgumentParser()
#
# class Net(AgentCommand):
#     def __init__(self, agent: MythicAgent):
#         super().__init__(agent=agent)
#         self._name = "net"
#         self._description = "example grouped command"
#         self._subcommand_parsers: Dict[str, Cmd2ArgumentParser] = {}
#         self._aliases: List[AgentCommandAlias] = []
#
#     @property
#     def name(self) -> str:
#         return self._name
#
#     @property
#     def description(self) -> str:
#         return self._description
#
#     @property
#     def aliases(self) -> List[AgentCommandAlias]:
#         return self._aliases
#
#     @property
#     def subcommand_parsers(self) -> Dict[str, Cmd2ArgumentParser]:
#         return self._subcommand_parsers
#
#     @property
#     def command_parser(self) -> Cmd2ArgumentParser:
#         return net_parser
#
#     @cmd2.with_argparser(net_parser)
#     def do_net(self, args) -> Task:
#         task = Task(self._agent.instance, command="net", args="",
#                      callback=self._agent.tasker.callback)
#         task.console_args = args
#         task.background = args.background
#         return task
'''

_README_TEMPLATE = """# {name}

{description}

## Install

```shell
python console.py install ./{name}
```

Then select a callback of payload type `{payload_type}` to use the generated commands.

## Next steps

- Add a `@renders` method in `formatter.py` to customize how a command's output looks.
- Add a `ScriptCommand` subclass under `scripts/` for a client-side command.
- Add an `AgentCommand` subclass under `commands/` and wire it into `get_agent_commands` in
  `{name}.py` for a curated command.

See `customize.md` in the console repo for the full walkthrough.
"""


class ScaffoldError(Exception):
    pass


def _class_name(name: str) -> str:
    return name[:1].upper() + name[1:]


def scaffold(name: str, payload_type: str, *, author: str = "", description: str = "",
            parent: str | Path = ".") -> Path:
    """Generate a new plugin skeleton named `name` for `payload_type` under `parent`/`name`."""
    if not name.isidentifier():
        raise ScaffoldError(f"'{name}' is not a valid plugin name (must be a valid Python identifier)")

    if name in RESERVED_NAMES:
        raise ScaffoldError(f"'{name}' is a reserved name and cannot be used for a plugin")

    target = Path(parent) / name
    if target.exists():
        raise ScaffoldError(f"'{target}' already exists")

    class_name = _class_name(name)

    target.mkdir(parents=True)
    (target / "__init__.py").write_text("")
    (target / "manifest.json").write_text(_MANIFEST_TEMPLATE.format(
        name=name, payload_type=payload_type, class_name=class_name,
        author=author, description=description))
    (target / f"{name}.py").write_text(_ENTRYPOINT_TEMPLATE.format(
        class_name=class_name, payload_type=payload_type))
    (target / "formatter.py").write_text(_FORMATTER_TEMPLATE.format(class_name=class_name))
    (target / "README.md").write_text(_README_TEMPLATE.format(
        name=name, payload_type=payload_type, description=description or "A Mythic Console plugin."))

    commands_dir = target / "commands"
    commands_dir.mkdir()
    (commands_dir / "__init__.py").write_text("")
    (commands_dir / "example.py").write_text(_COMMAND_EXAMPLE_TEMPLATE)

    scripts_dir = target / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("")
    (scripts_dir / "example.py").write_text(_SCRIPT_EXAMPLE_TEMPLATE)

    return target
