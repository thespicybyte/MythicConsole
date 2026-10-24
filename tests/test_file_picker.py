import asyncio
import os
import types
from pathlib import Path

import pytest
from textual.app import App
from textual.screen import Screen
from textual.widgets import DirectoryTree, TabPane

from backend.task.task import Task
from screens.home import Home
from screens.prompts import FilePrompt
from utils import state
from widgets.console import ConsolePanel

CSS_PATH = Path(__file__).resolve().parent.parent / "mythic.tcss"


@pytest.fixture(autouse=True)
def isolated_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


class _PromptHarness(App):
    CSS_PATH = CSS_PATH


# --- FilePrompt modal ---

async def test_file_prompt_shows_a_directory_tree(tmp_path):
    app = _PromptHarness()
    async with app.run_test() as pilot:
        prompt = FilePrompt("file", start_path=str(tmp_path))
        app.push_screen(prompt)
        await pilot.pause()

        assert prompt.query_one(DirectoryTree) is not None


async def test_file_prompt_select_dismisses_with_the_chosen_path(tmp_path):
    chosen = tmp_path / "pick_me.txt"
    chosen.write_text("hi")

    app = _PromptHarness()
    async with app.run_test() as pilot:
        result = {}
        prompt = FilePrompt("file", start_path=str(tmp_path))
        app.push_screen(prompt, callback=lambda value: result.setdefault("value", value))
        await pilot.pause()

        tree = prompt.query_one(DirectoryTree)
        tree.post_message(DirectoryTree.FileSelected(tree.root, chosen))
        await pilot.pause()

        await pilot.click("#select")
        await pilot.pause()

        assert result.get("value") == str(chosen)


async def test_file_prompt_select_is_a_noop_without_a_highlighted_file(tmp_path):
    app = _PromptHarness()
    async with app.run_test() as pilot:
        result = {}
        prompt = FilePrompt("file", start_path=str(tmp_path))
        app.push_screen(prompt, callback=lambda value: result.setdefault("value", value))
        await pilot.pause()

        await pilot.click("#select")
        await pilot.pause()

        assert "value" not in result
        assert app.screen is prompt


async def test_file_prompt_cancel_button_dismisses_with_none(tmp_path):
    app = _PromptHarness()
    async with app.run_test() as pilot:
        result = {}
        prompt = FilePrompt("file", start_path=str(tmp_path))
        app.push_screen(prompt, callback=lambda value: result.setdefault("value", value))
        await pilot.pause()

        await pilot.click("#cancel")
        await pilot.pause()

        assert result.get("value") is None


async def test_file_prompt_escape_dismisses_with_none(tmp_path):
    app = _PromptHarness()
    async with app.run_test() as pilot:
        result = {}
        prompt = FilePrompt("file", start_path=str(tmp_path))
        app.push_screen(prompt, callback=lambda value: result.setdefault("value", value))
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert result.get("value") is None


# --- FilePrompt start directory: cwd default, remembered dir, persistence on pick ---

async def test_file_prompt_defaults_to_cwd_when_no_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    app = _PromptHarness()
    async with app.run_test() as pilot:
        prompt = FilePrompt("file")
        app.push_screen(prompt)
        await pilot.pause()

        assert prompt.start_path == os.getcwd()


async def test_file_prompt_uses_the_remembered_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    remembered = tmp_path / "remembered"
    remembered.mkdir()
    state.set_last_file_dir(str(remembered))

    app = _PromptHarness()
    async with app.run_test() as pilot:
        prompt = FilePrompt("file")
        app.push_screen(prompt)
        await pilot.pause()

        assert prompt.start_path == str(remembered)


async def test_file_prompt_falls_back_to_cwd_on_corrupt_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from utils.environment import Environment

    config_dir = Environment().config_directory()
    with open(os.path.join(config_dir, "state.json"), "w") as f:
        f.write("not json{{{")

    app = _PromptHarness()
    async with app.run_test() as pilot:
        prompt = FilePrompt("file")
        app.push_screen(prompt)
        await pilot.pause()

        assert prompt.start_path == os.getcwd()


async def test_file_prompt_select_persists_the_chosen_files_directory(tmp_path):
    picked_dir = tmp_path / "subdir"
    picked_dir.mkdir()
    chosen = picked_dir / "pick_me.txt"
    chosen.write_text("hi")

    app = _PromptHarness()
    async with app.run_test() as pilot:
        prompt = FilePrompt("file", start_path=str(tmp_path))
        app.push_screen(prompt)
        await pilot.pause()

        tree = prompt.query_one(DirectoryTree)
        tree.post_message(DirectoryTree.FileSelected(tree.root, chosen))
        await pilot.pause()

        await pilot.click("#select")
        await pilot.pause()

        assert state.get_last_file_dir() == str(picked_dir)


async def test_file_prompt_cancel_does_not_persist_a_directory(tmp_path):
    app = _PromptHarness()
    async with app.run_test() as pilot:
        prompt = FilePrompt("file", start_path=str(tmp_path))
        app.push_screen(prompt)
        await pilot.pause()

        await pilot.click("#cancel")
        await pilot.pause()

        assert state.get_last_file_dir() is None


# --- FilePrompt left/right keys: re-root toward the filesystem root / open a directory ---

async def test_file_prompt_left_key_rerootes_to_the_parent_directory(tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    app = _PromptHarness()
    async with app.run_test() as pilot:
        prompt = FilePrompt("file", start_path=str(nested))
        app.push_screen(prompt)
        await pilot.pause()

        tree = prompt.query_one(DirectoryTree)
        assert tree.path == nested

        await pilot.press("left")
        await asyncio.sleep(0.2)
        await pilot.pause()

        assert tree.path == nested.parent

        await pilot.press("left")
        await asyncio.sleep(0.2)
        await pilot.pause()

        assert tree.path == nested.parent.parent


async def test_file_prompt_left_key_at_filesystem_root_is_a_noop():
    app = _PromptHarness()
    async with app.run_test() as pilot:
        prompt = FilePrompt("file", start_path="/")
        app.push_screen(prompt)
        await pilot.pause()

        tree = prompt.query_one(DirectoryTree)
        await pilot.press("left")
        await pilot.pause()

        assert str(tree.path) == "/"


async def test_file_prompt_right_key_expands_the_cursor_directory(tmp_path):
    nested = tmp_path / "a"
    nested.mkdir()
    (nested / "child.txt").write_text("hi")

    app = _PromptHarness()
    async with app.run_test() as pilot:
        prompt = FilePrompt("file", start_path=str(tmp_path))
        app.push_screen(prompt)
        await asyncio.sleep(0.2)
        await pilot.pause()

        tree = prompt.query_one(DirectoryTree)
        root_node = tree.root
        assert not root_node.children[0].is_expanded

        tree.cursor_line = 1
        await pilot.press("right")
        await asyncio.sleep(0.2)
        await pilot.pause()

        assert root_node.children[0].is_expanded


# --- screens/home.py wiring: pre-execute file-picker loop ---
# Exercises Home.execute_cmd's new picker loop against a minimal screen carrying
# only what that method touches (prompt/current_callback/displayed_tabs/cmd), rather
# than mounting the full Home (whose compose() pulls in Sidebar/SessionInfo/Callbacks,
# which need a live MythicInstance).

class _ExecHarness(Screen):
    execute_cmd = Home.execute_cmd

    def __init__(self, instance, task_response):
        super().__init__()
        self.prompt = "> "
        self.current_callback = None
        self.current_agent = None
        self.cmd = types.SimpleNamespace(onecmd=lambda *_a, **_k: task_response)
        self.console_panel = ConsolePanel(instance=instance)
        self.displayed_tabs = {"Mythic": TabPane("Mythic", self.console_panel, id="home")}

    def compose(self):
        yield self.displayed_tabs["Mythic"]


class _ExecHarnessApp(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance, task_response):
        super().__init__()
        self.harness = _ExecHarness(instance, task_response)

    def on_mount(self):
        self.push_screen(self.harness)


def _pending_task(fake_instance, pending_key="file", label="file"):
    callback = types.SimpleNamespace(display_id=1, loaded_commands=None)
    task = Task(fake_instance, command="stash", args={}, callback=callback)
    task.pending_file_params = {pending_key: label}
    return task


async def test_picker_cancel_aborts_before_execute(fake_instance, monkeypatch):
    def _never_execute(*_args, **_kwargs):
        raise AssertionError("Task.execute must not be called when the picker is cancelled")

    monkeypatch.setattr(Task, "execute", _never_execute)

    task = _pending_task(fake_instance)
    app = _ExecHarnessApp(fake_instance, task)

    async with app.run_test() as pilot:
        await pilot.pause()
        monkeypatch.setattr(app, "push_screen_wait", lambda *_a, **_k: _async_none())

        await app.harness.execute_cmd("stash")

        assert task.file_params == {}


async def test_picker_feeds_the_chosen_path_into_file_params_before_execute(fake_instance, monkeypatch, tmp_path):
    import mythic.mythic
    from backend.task.queries import TaskQueries

    chosen = tmp_path / "payload.bin"
    chosen.write_bytes(b"data")

    async def _register_file(_mythic, filename, contents):
        assert filename == "payload.bin"
        assert contents == b"data"
        return "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    captured = {}

    async def _issue(_mythic, command_name, args, callback_display_id):
        captured["args"] = dict(args)
        return 42

    async def _query(self):
        self.completed = True

    monkeypatch.setattr(mythic.mythic, "register_file", _register_file)
    monkeypatch.setattr(TaskQueries, "execute", _issue)
    monkeypatch.setattr(Task, "query", _query)

    task = _pending_task(fake_instance)
    task.background = True
    app = _ExecHarnessApp(fake_instance, task)

    async with app.run_test() as pilot:
        await pilot.pause()
        monkeypatch.setattr(app, "push_screen_wait", lambda *_a, **_k: _async_value(str(chosen)))

        await app.harness.execute_cmd("stash")

        assert task.file_params == {"file": str(chosen)}
        assert captured["args"]["file"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert task.id == 42


async def _async_none():
    return None


async def _async_value(value):
    return value
