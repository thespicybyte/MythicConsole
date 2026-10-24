# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Mythic Console is a [Textual](https://textual.textualize.io/) terminal UI for interacting with a
[Mythic C2](https://github.com/its-a-feature/Mythic) server. It is an alternate operator interface to
the Mythic web UI, not a replacement. It talks to Mythic through the `mythic` PyPI library (a GraphQL
client), so this codebase issues tasks and reads results — it is not the C2 server itself.

## Commands

```shell
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python console.py            # run the app
```

Requires Python 3.11+ (`cmd2` 4.x and the updated `mythic`/`textual` stack need it). There is no
linter or build step in this repo.

```shell
pip install -r requirements-dev.txt
pytest                         # run the default (offline) test suite
pytest tests/test_environment.py::test_log_level_mapping   # run a single test
pytest -m live                 # live/Pilot tests — need .env + a reachable Mythic server
```

The default suite needs no Mythic server: the two objects that reach the network
(`Task.get_responses`, `MythicInstance.login`) are mocked via fixtures in `tests/conftest.py`. Tests
marked `@pytest.mark.live` (under `tests/live/`) are opt-in and deselected by default.

`textual-dev` is a dependency, so the Textual tooling is available for debugging a running TUI:

```shell
textual console              # in one terminal: live log/console
textual run --dev console.py # in another: run the app connected to it
```

Runtime config comes from environment variables or a `.env` file (parsed in `utils/environment.py`),
not CLI flags: `MYTHIC_CONSOLE_USER`, `MYTHIC_CONSOLE_PASSWORD`, `MYTHIC_SERVER_URL` prefill the login
screen; `DOWNLOAD_DIRECTORY`, `LOG_DIRECTORY`, `LOG_FILE`, `LOG_LEVEL` configure downloads and logging.
Logs default to `.console.log` in the cwd.

## Architecture

The app is a state machine (`State` enum in `console.py`) that pushes Textual screens: `LoginScreen`
authenticates and produces a `MythicInstance`; on success `Home` is pushed. `MythicInstance`
(`backend/mythic_instance/`) holds the authenticated `mythic.Mythic` client and the asyncio loop, and is
threaded through almost every backend object as the handle to the server.

**Backend domain layer** (`backend/`). Each Mythic concept is its own package — `callback`, `task`,
`response`, `payload`, `payload_type`, `operation`, `user`, `file_browser`. The recurring pattern is a
domain class (e.g. `Task`, `Callback`) paired with a `queries.py` and `fragments.py` that hold the raw
GraphQL. When changing what data is fetched, edit the `fragments`/`queries` alongside the class; don't
inline GraphQL elsewhere. `backend/__init__.py` re-exports the public classes, so import from `backend`
(e.g. `from backend import Task, Callback`) rather than deep module paths.

- `Tasker` (`backend/tasker/`) issues a command to the currently selected `Callback` via
  `mythic.issue_task` and returns a `Task`.
- `Task` (`backend/task/`) wraps one Mythic task: it can `wait_for_completion`, stream responses, and
  download files. A `Task` carries `console_args` (the parsed argparse namespace) and `background` so the
  formatter can later re-render output using the original command arguments.

**Agent / command layer** (`backend/mythic_agent/mythic_agent.py`, the largest and most important file).
This is where per-agent command sets are defined and dynamically loaded:

- `MythicAgent` is the base class for a supported agent. It owns a `Tasker` and a `Formatter`.
- `AgentCommand` is an ABC that also subclasses `cmd2.Cmd`; each command is one class providing a cmd2
  argparse parser, optional subcommand parsers, and `AgentCommandAlias`es for tab completion. A
  `do_<name>` method builds and returns a `Task` (it does **not** execute it — the UI calls `.execute()`).
- `ScriptCommand` is the variant for multi-step client-side scripts.
- `MythicCommands` holds global, agent-independent commands (e.g. `payload list/download`).
- **Commands are generated, not globbed**: `MythicAgent.get_agent_commands` fetches the payload
  type's full command catalog from the Mythic server and builds one `AgentCommand` per command via
  `AgentCommand.from_server`, which also auto-binds `do_<name>`. A plugin curates on top of this by
  overriding `get_agent_commands`, calling `super()`, and patching the returned `AgentCommands`
  mapping (pop/add by name). Scripts are the one piece still loaded by naming convention:
  `get_script_classes` globs `agents/<Name>/scripts/*.py` (or a plugin's own `scripts/*.py`) and
  imports each by a strict **filename → class name** convention — the class is named by
  capitalizing the filename (`ping.py` → `Ping`). A mismatched name silently fails to load (logged
  as a warning), so keep script file and class names in sync.

**Formatters** (`backend/formatter/`). A `Formatter` turns a completed `Task` into a Rich
`RenderableType` for the console. A subclass tags render methods with `@renders("<command>")`
instead of overriding `format_output`; the base `format_output` dispatches to the tagged method by
command name and falls back to `format_plaintext` for anything untagged. Base helpers:
`format_plaintext`, `format_pretty`, `build_table`, `get_raw_output`.

**Agent registration** (`agents/`). `agents/__init__.py` `get_agent(instance, payload_type_name)`
looks up an installed plugin for that payload type; if none is installed, it returns a generated
`MythicAgent(payload_type_name, instance, DefaultFormatter())`. There are no hard-coded agent names.
Supporting a new payload type needs zero code — the generated baseline just works. Poseidon is no
longer in this repo; it ships as its own plugin, installed like any other. Optional curation (a
custom command, formatter, or script) ships as a plugin too: a `PluginAgent` subclass plus a
`manifest.json`. Full walkthrough is in `customize.md`.

**UI layer**. `screens/` (`home.py` is the main operator screen; `login.py`; `prompts.py` holds
`TaskPrompt`/`YesNoPrompt` modal confirmations) and `widgets/` (console panel, callback tabs, tables,
session info, themes). `Home` runs background Textual workers to monitor new callbacks and task updates
live. `mythic.tcss` is the stylesheet. A `Task` can set `verify_prompt` to force a modal confirmation
before a dangerous command (e.g. `exit`) runs.

## Key conventions

- A `do_<command>` method returns an unexecuted `Task`; the screen layer executes it. Stash any data the
  formatter will need on the `Task` (`console_args`, `args`) at build time.
- Call `add_default_options(parser)` on every command parser to get the shared `-bg/--background` flag.
- Scripts are loaded by naming convention, not registration — a script file is picked up
  automatically only if its class name matches the file name. Commands are generated from the
  server catalog, not file-loaded; a plugin curates them by patching `get_agent_commands`'s result.
