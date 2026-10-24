# Extending Mythic Console

Mythic Console generates commands for any connected callback from the Mythic server's own command
catalog, so a new agent works with zero code. Curation is optional: add polish one piece at a time,
only where the generated behavior is not good enough. The curation you write ships as a **plugin**,
a standalone package installed into the console, not a file you add to this repo. Poseidon is the
fully-curated end of that spectrum — it ships as its own plugin.

## Zero-code: connect a callback, get commands

When you select a callback, the console calls `get_agent(instance, callback.payload_type_name)`
(`agents/__init__.py`). If no plugin is installed for that payload type, you get a generated
`MythicAgent` with a `DefaultFormatter`:

```python
return MythicAgent(payload_type_name, instance, DefaultFormatter())
```

`MythicAgent.load_commands` then calls `get_agent_commands`, which queries
`mythic.get_all_commands_for_payloadtype` for every command the payload type defines and builds an
`AgentCommand` for each one with `AgentCommand.from_server`. `from_server` reads each command's
`commandparameters` and builds a `Cmd2ArgumentParser` from them — booleans, numbers, arrays,
choice lists, files, and so on all map to the right argparse flag automatically. A `do_<name>`
method is bound for you, so the command is immediately usable.

`DefaultFormatter` defines no renderers, so `format_output` falls back to `format_plaintext` for
every command. Output is plaintext until you add a renderer (see "Customize how output renders"
below).

Connect a callback of any Mythic-supported payload type and you get a full set of commands and
readable output. Nothing to create, nothing to register.

### Catalog vs. loaded commands

The commands generated this way are the full **catalog**: everything the payload type defines on
the Mythic server, whether or not the specific callback currently has it loaded. The console
separately caches which commands are actually loaded on the callback
(`MythicAgent._cache_loaded_commands`, via `CallbackQueries.get_loaded_commands`), and a parameter
flagged `choices_are_loaded_commands` is checked against that set. That check is fail-open: if the
loaded set isn't known, the value is allowed through. In short, a generated command may appear that
isn't currently loaded on the callback — there's no load-gating UI in the console yet.

## Add polish incrementally

Everything below is independent and opt-in. Add only what a given agent needs. All of it is
delivered as a **plugin** (see "Package it as a plugin"): the console loads the generated commands
first, then your plugin's overrides patch on top of them.

### 1. Curate a command group

Replace generated flags with friendlier names, subcommands, or aliases. Override
`get_agent_commands`, start from the generated set, then drop and add commands:

```python
async def get_agent_commands(self) -> AgentCommands:
    cmds = await super().get_agent_commands()
    for name in ("echo", "connect"):
        cmds.pop(name, None)
    cmds["net"] = Net(self)
    return cmds
```

`Net` here is a hand-written `AgentCommand` with its own subcommands and aliases (grouping the
`echo`/`connect` generated commands under one `net` command):

```python
from typing import Dict, List

from cmd2 import cmd2, Cmd2ArgumentParser

from backend import Task
from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options

net_parser = Cmd2ArgumentParser()
net_subparsers = net_parser.add_subparsers(title='subcommands', help='subcommand help')

net_echo_parser = net_subparsers.add_parser('echo', help='echo text')
add_default_options(net_echo_parser)
net_echo_parser.add_argument('--text', required=True, help='text to echo')

net_connect_parser = net_subparsers.add_parser('connect', help='connect to a peer')
add_default_options(net_connect_parser)
net_connect_parser.add_argument('--port', type=int, required=True, help='port')


class Net(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent=agent)
        self._name = "net"
        self._description = "grouped command covering echo/connect"
        self._subcommand_parsers: Dict[str, Cmd2ArgumentParser] = {
            "echo": net_echo_parser,
            "connect": net_connect_parser,
        }
        self._aliases = [
            AgentCommandAlias("echo", self._name, "echo", description="echo text"),
            AgentCommandAlias("connect", self._name, "connect", description="connect to a peer"),
        ]

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
        return net_parser

    @cmd2.with_argparser(net_parser)
    def do_net(self, args):
        func = getattr(args, 'func', None)
        if func is not None:
            return func(self, args)

    def net_echo(self, args) -> Task:
        if isinstance(args, str):
            args = net_echo_parser.parse_args(args)

        task = Task(self._agent.instance, command="echo", args=args.text,
                    callback=self._agent.tasker.callback)
        task.console_args = args
        task.background = args.background
        return task

    net_echo_parser.set_defaults(func=net_echo)

    def net_connect(self, args) -> Task:
        if isinstance(args, str):
            args = net_connect_parser.parse_args(args)

        task = Task(self._agent.instance, command="connect", args=str(args.port),
                    callback=self._agent.tasker.callback)
        task.console_args = args
        task.background = args.background
        return task

    net_connect_parser.set_defaults(func=net_connect)
```

Note the `Task(..., callback=self._agent.tasker.callback)` constructor — build a `Task` this way,
not with `callback_display_id=...`.

### 2. Customize how output renders

Subclass `Formatter` and tag a method with `@renders("<command>")`. `format_output` dispatches to
the tagged method by command name; any command without a tagged method still falls back to
`format_plaintext` automatically, so you only write renderers for the commands you want to improve:

```python
from rich.text import Text

from backend import Formatter, Task, renders


class MyAgentFormatter(Formatter):
    @renders("echo")
    async def echo(self, task: Task) -> Text:
        raw = await self.get_raw_output(task)
        return Text(raw.upper())
```

`Formatter` also provides `format_pretty` (pretty-print JSON output), `build_table` (render rows as
a Rich table), and `get_raw_output` (the decoded response text, for writing your own renderer) as
helpers.

### 3. Confirm dangerous commands (verify_prompt)

Every `AgentCommand` has a `verify_prompt` attribute (`None` by default). Set it on the command
instance and the console shows that modal and waits for confirmation before the task executes:

```python
from screens.prompts import YesNoPrompt

net = Net(self)
net.verify_prompt = YesNoPrompt(question="Run this command?")
```

On a hand-written command, set it in `__init__` instead:

```python
class Exit(AgentCommand):
    def __init__(self, agent: MythicAgent):
        super().__init__(agent)
        self._name = "exit"
        self.verify_prompt = YesNoPrompt(question="Exit/kill the current session?")
```

### 4. Add a client-side script (ScriptCommand)

A script is an `AgentCommand` whose `do_<name>` can return a renderable directly instead of a
`Task` — useful for a client-side action that doesn't need a server round trip. `ScriptCommand` is
`AgentCommand` itself (`ScriptCommand = AgentCommand`); what makes a command a script is where the
file lives.

Place it at `scripts/<name>.py`; the class name is the capitalized filename (`ping.py` → `Ping`):

```python
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
```

`do_ping` returns the string `"pong"` directly, with no `Task` involved. A script can return a
`Task` instead when it does need to round-trip to the server.

### 5. Hand-write a full agent class (override everything)

For full control, subclass `PluginAgent` (not `MythicAgent` directly — see below) and override
whatever you need:

```python
from backend.mythic_agent.mythic_agent import AgentCommands
from plugins.base import PluginAgent

from .commands.net import Net
from .formatter import MyAgentFormatter


class MyAgent(PluginAgent):
    def __init__(self, instance):
        super().__init__("myagent", instance, MyAgentFormatter())

    async def get_agent_commands(self) -> AgentCommands:
        cmds = await super().get_agent_commands()
        cmds["net"] = Net(self)
        return cmds
```

This is the shape Poseidon uses: a curated command set, a full formatter, verify prompts, and
scripts, all on top of the same generated baseline.

## Package it as a plugin

A plugin is a Python package with a `manifest.json` at its root. All fields except `author` and
`description` are required (`plugins/manifest.py`):

```json
{
  "schema_version": 1,
  "name": "myagent",
  "payload_type": "myagent",
  "entrypoint": "myagent:MyAgent",
  "version": "0.1.0",
  "author": "you",
  "description": "optional"
}
```

- `schema_version` must be `1`.
- `name` must be a valid Python identifier.
- `payload_type` is the Mythic payload type name this plugin handles.
- `entrypoint` is `"<module>:<Class>"`; the class must subclass `MythicAgent` — use `PluginAgent`
  (`plugins/base.py`) as that base, since it resolves the plugin's own `commands/`/`scripts/`
  directories instead of the in-repo `agents/<Name>/` layout `MythicAgent` assumes.
- `version` is the plugin's version string.

Lay the package out like this:

```
myagent/
├── manifest.json
├── myagent.py        # entrypoint module: the MyAgent(PluginAgent) class
├── formatter.py
├── commands/
│   └── net.py
└── scripts/
    └── ping.py
```

Install it from the shell:

```shell
python console.py install https://github.com/<you>/<your-agent-plugin> [--branch BRANCH] [--subdir DIR]
python console.py install /path/to/local/clone
python console.py plugin list
python console.py plugin remove <name>
```

or from inside the console: `plugin install <url|path>`, `plugin list`, `plugin remove <name>`.

Installing or removing a plugin reloads the plugin registry immediately, but a callback you already
selected keeps the agent it was given at selection time — reselect the callback (or select a new one
of that payload type) to pick up the change. Plugins are discovered at startup from the plugins
directory (`${XDG_CONFIG_HOME:-~/.config}/mythicconsole/plugins`, overridable with
`PLUGIN_DIRECTORY`); `install`/`plugin install` write there too.

## Poseidon: the fully-curated reference

Poseidon no longer lives in this repo — it ships as its own plugin, installed the same way as any
other plugin described above. It curates its command groups, supplies a full formatter, sets
`verify_prompt` on dangerous commands, and adds client-side scripts. If you want to see every
technique above used together in a real agent, read its source.

## Reference: generated parameter mapping

`_add_param_argument` (`backend/mythic_agent/mythic_agent.py`) maps each Mythic command parameter
type to an argparse treatment when building a generated command's parser:

| Mythic parameter type                     | argparse treatment                                        |
|--------------------------------------------|------------------------------------------------------------|
| `Boolean`                                  | `store_true` flag                                           |
| `Number`                                   | `int`-typed flag                                             |
| `Array`                                    | flag with `nargs="+"`                                       |
| `ChooseOne`                                | flag with `choices=[...]`                                   |
| `ChooseMultiple`                           | flag with `nargs="+"`, `choices=[...]`                       |
| `File`                                     | flag taking a local path or an existing file UUID            |
| `PayloadList`                              | flag taking a payload UUID                                   |
| `TypedArray`                                | flag taking a JSON array of `[type, value]` pairs            |
| JSON-object types (e.g. `CredentialJson`)   | flag taking a JSON object, validated against a template      |
| `choices_are_all_commands`                 | flag whose choices are every command name on the agent       |
| `choices_are_loaded_commands`               | flag validated against the callback's currently loaded commands (fail-open) |
| dynamic (`dynamic_query_function`)          | flag whose choices are supplied by the agent at runtime       |

Anything not listed above falls back to a plain string flag.
