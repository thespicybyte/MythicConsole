import io
import sys
from enum import Enum
from typing import Optional, Callable, Any, Coroutine

import cmd2
import pyperclip
from cmd2.exceptions import EmptyStatement
from mythic.mythic_classes import Mythic
from rich.table import Table
from rich.text import Text
from textual import work, events, on
from textual._context import NoActiveAppError
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.reactive import reactive, var
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Header, Input, DataTable, TabbedContent, TabPane
from textual.widgets._data_table import DuplicateKey, CellDoesNotExist
from textual.worker import WorkerFailed

from agents import get_agent
from backend import Callback, MythicInstance, User, Operation, Task, MythicAgent, FormatterNotAvailable
from backend.cmd.mythic_cmd import MythicCmd
from backend.task.task import TaskError
from utils.logger import logger
from widgets.calback_tabs import CallbackTabs
from widgets.callbacks import Callbacks, CallbackTable
from widgets.console import ConsolePanel
from widgets.messages import TabClosed, CopyToClipboard, ClipboardReady, UpdateCurrentCallback
from widgets.session_info import SessionInfo
from widgets.tasks_table import TasksTable, ReplayTask


class ViewMode(Enum):
    HOME = 1
    CALLBACK = 2


class Sidebar(Container):
    view_mode = reactive(ViewMode.HOME, recompose=True)

    def __init__(self, instance: MythicInstance, *children: Widget):
        self.instance = instance
        self.mythic = instance.mythic
        super().__init__(*children)
        self.callbacks_widget = Callbacks(self.instance)
        self.task_table_widget = TasksTable(self.instance)
        self.task_table_widget.visible = False
        self._cmd: Optional[MythicCmd] = None
        self.operation = Operation(instance, operation_id=instance.mythic.current_operation_id)

    def _get_style_width_value(self) -> float:
        """
        Get the percentage of the current width of the sidebar
        :return: width value
        """
        style_width = str(self.styles.width)
        width = style_width.removesuffix("w")
        return float(width)

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield SessionInfo(self.instance, self.operation)
            yield self.callbacks_widget
            yield self.task_table_widget

    def watch_view_mode(self) -> None:
        match self.view_mode:
            case ViewMode.HOME:
                self.task_table_widget.visible = False
            case ViewMode.CALLBACK:
                self.task_table_widget.visible = True

    def shrink(self) -> None:
        """ shrink sidebar width by .5 percent """
        current_width = self.container_size.width

        # no smaller than 30
        if current_width <= 30:
            return

        styled_width = self._get_style_width_value()
        self.styles.width = f"{styled_width - .5}w"

    def grow(self) -> None:
        """ grow sidebar width by .5 percent """
        current_width = self.container_size.width

        # no bigger than 80 wide
        if current_width >= 80:
            return

        styled_width = self._get_style_width_value()

        # no bigger than 45%
        if styled_width >= 45:
            return

        styled_width = self._get_style_width_value()
        self.styles.width = f"{styled_width + .5}w"


class Home(Screen):
    AUTO_FOCUS = "#prompt"
    stdout = reactive("")
    prompt = var("> ")
    current_callback: reactive[Callback | None] = reactive[Callback](None)
    active_callbacks: dict[str, Callback] = {}
    displayed_tabs = reactive({})
    last_tab_id = var("home")
    current_tab_id = var("home")
    current_agent: Optional[MythicAgent] = None

    def __init__(self, instance: MythicInstance):
        self.instance = instance
        self.current_user = User(instance, instance.username)
        self.current_operation = Operation(instance, operation_id=instance.mythic.current_operation_id)
        self.mythic: Mythic = self.instance.mythic
        self.system_copy: Callable[[Any], None] | None = None
        self.system_paste: Callable[[], str] | None = None
        self.clipboard: str = ""
        self.cmd = MythicCmd(instance)
        super().__init__()
        self.displayed_tabs["Mythic"] = TabPane("Mythic", ConsolePanel(instance=instance), id="home")
        self._determine_clipboard()

    BINDINGS = [
        Binding(key="ctrl+s", action="toggle_sidebar", description="toggle sidebar", key_display="^s"),
        Binding(key="ctrl+l", action="app.logout", description="logout", key_display="^l"),
        Binding(key="ctrl+pagedown", action="previous_tab", description="previous tab", key_display="^pagedown"),
        Binding(key="ctrl+pageup", action="next_tab", description="next tab", key_display="^pageup"),
        Binding(key="ctrl+q", action="close_tab", description="close tab", key_display="^q"),
        Binding(key="alt+left", action="shrink_sidebar", description="shrink sidebar", show=False),
        Binding(key="alt+right", action="grow_sidebar", description="grow sidebar", show=False),
        Binding(key="ctrl+q", action="close_tab", description="close tab", key_display="^q"),
        Binding(key="ctrl+z", action="background_current_task", description="background", key_display="^z"),
    ]

    async def _on_mount(self, _event: events.Mount) -> None:
        self.monitor_callbacks()
        worker = self._get_active_callbacks()
        await worker.wait()
        self._get_and_monitor_tasks()
        self._monitor_tasks()

    @on(ClipboardReady)
    def _set_clipboard(self, message: ClipboardReady) -> None:
        self.system_copy = message.copy
        self.system_paste = message.paste

    @on(CopyToClipboard)
    def _copy_to_clipboard(self, message: CopyToClipboard):
        content = message.content
        try:
            self.system_copy(content)
            if message.success_message:
                self.app.notify(message.success_message, timeout=2)
        except pyperclip.PyperclipException as e:
            logger.error(e)
            self.app.notify(f"error copying to clipboard: {e}", severity="error", timeout=5)
        message.stop()

    @work(thread=True)
    def _determine_clipboard(self) -> None:
        copy, paste = pyperclip.determine_clipboard()
        try:
            self.post_message(ClipboardReady(copy=copy, paste=paste))
        except NoActiveAppError:
            # not sure what causes this, but handling this doesn't seem to break anything
            logger.error("no app error")

    @on(TabClosed)
    def tab_closed(self, message: TabClosed):
        tab_id = message.tab_id
        if "callback" not in tab_id:
            return

        callback_uuid = tab_id.removeprefix("callback-")
        del self.displayed_tabs[callback_uuid]

    def watch_current_tab_id(self):
        logger.info(f"new tab id: {self.current_tab_id}")

    def watch_last_tab_id(self):
        logger.info(f"new last tab id: {self.last_tab_id}")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Sidebar(self.instance)
        with CallbackTabs(self.instance):
            for _name, pane in self.displayed_tabs.items():
                yield pane
        yield Footer()

    @on(ConsolePanel.NewInput)
    async def _new_input(self, event: ConsolePanel.NewInput):
        cmd = event.data
        self.execute_cmd(cmd)

    def action_toggle_sidebar(self) -> None:
        self.query_one(Sidebar).toggle_class("-hidden")

    @work()
    async def _get_active_callbacks(self):
        callback_table = self.query_one("#callback_table", DataTable)
        callback_uuids = await self.instance.get_active_callbacks()
        for callback_uuid in callback_uuids:
            cb = Callback(self.instance, callback_uuid=callback_uuid)
            await cb.query()
            # await cb.get_all_tasks()
            callback_table.add_row(cb.display_id, cb.hostname, cb.payload_type_name, cb.uuid, key=cb.uuid)
            if cb.uuid not in self.active_callbacks.keys():
                self.active_callbacks[cb.uuid] = cb

    @work()
    async def _get_and_monitor_tasks(self) -> None:
        """
        Get all the tasks Mythic has. Put the task in the correct callback instance so we don't have to query them again.
        This function will then continue to monitor for new tasks
        """
        logger.debug("monitoring for tasks")
        async for task_id in self.instance.get_and_monitor_new_tasks():
            task = Task(self.instance, task_id=task_id)
            await task.query()
            if task.callback_uuid not in self.active_callbacks.keys():
                continue

            callback = self.active_callbacks[task.callback_uuid]
            if task in callback.tasks:
                continue
            callback.tasks.append(task)
            self.post_message(TasksTable.NewTask(task))
            # if self.current_callback:
            #     if self.current_callback.uuid == task.callback_uuid:
            #         task_table.add_row(task.id, task.uuid, )

    @work()
    async def _monitor_tasks(self) -> None:
        """Monitor for task updates"""
        async for task_id in self.instance.monitor_tasks_updates():
            task = Task(self.instance, task_id=task_id)
            await task.query()
            await self._update_task(task)

    @work()
    async def monitor_callbacks(self):
        callback_table = self.query_one("#callback_table", DataTable)
        async for uuid in self.instance.monitor_new_callbacks():
            if uuid in self.active_callbacks.keys():
                continue
            cb = Callback(self.instance, callback_uuid=uuid)
            await cb.query()
            callback_table.add_row(cb.display_id, cb.hostname, cb.payload_type_name, cb.uuid, key=cb.uuid)
            self.active_callbacks[cb.uuid] = cb

    async def _update_task(self, task: Task):
        tasked_callback = self.active_callbacks.get(task.callback_uuid)

        if not tasked_callback:
            logger.warning(f"could not add task to task table: callback {task.callback_display_id} not found")
            return

        if self.current_callback:
            # add task to task table if active
            if self.current_callback.uuid == tasked_callback.uuid:
                task_table = self.query_one("#tasks_table", DataTable)
                try:
                    task_table.update_cell(row_key=task.uuid, column_key="status", value=task.status)
                except CellDoesNotExist:
                    logger.warning("could not find row to update task status")
                    pass

        if task not in tasked_callback.tasks:
            tasked_callback.tasks.append(task)
            return

        for index, cb_task in enumerate(tasked_callback.tasks):
            if task.uuid == cb_task.uuid:
                tasked_callback.tasks[index] = task
                break

    @work(exit_on_error=False)
    async def execute_cmd(self, cmd: str):
        stderr_capture = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = stderr_capture

        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = stdout_capture

        current_agent: Optional[MythicAgent] = None
        console_panel: Optional[ConsolePanel] = None
        prompt = None
        try:
            if self.current_callback:
                console_panel = self.current_callback.console_panel
                current_agent = self.current_callback.console_panel.agent
            else:
                pane = self.displayed_tabs.get("Mythic")
                console_panel = pane.query_one(ConsolePanel)

            prompt = console_panel.query_one(Input)
            prompt.disabled = True

            console_panel.write_string(f"{self.prompt}{cmd}")

            if cmd.strip() == "help":
                self._show_help(console_panel, current_agent)
                return

            tokens = cmd.split()
            actual_command = cmd
            if len(tokens) >= 1:
                actual_command = tokens[0].replace("-", "_")
                actual_command = f"{actual_command} {' '.join(tokens[1:])}"
            resp = self.cmd.onecmd(actual_command.strip())
            if not resp:
                console_panel.write_string(f"No such command '{cmd.strip()}'")
                return

            worker = None
            if isinstance(resp, Task):
                if resp.verify_prompt:
                    if not await self.app.push_screen_wait(resp.verify_prompt):
                        logger.debug("user bailed on task")
                        return

                worker = self.run_worker(resp.execute(), exit_on_error=False)
                await worker.wait()
                if resp.background:
                    return
                await resp.query()
                worker = self.run_worker(resp.wait_for_completion(), name=f"{resp.command_name}_{resp.id}",
                                         exit_on_error=False)

            if isinstance(resp, Coroutine):
                worker = self.run_worker(resp, exit_on_error=False)

            if not worker:
                return

            if current_agent:
                current_agent.current_foreground_task = worker

            await worker.wait()

            if current_agent:
                current_agent.current_foreground_task = None

            if worker.is_cancelled:
                logger.debug("task was cancelled")
                return

            output = None
            if isinstance(resp, Task):
                await resp.query()
                output = await self.current_agent.formatter.format_output(resp)

            if isinstance(resp, Coroutine):
                output = worker.result
                # this happens when task function needs to await something, such as upload
                if isinstance(output, Task):
                    await output.query()
                    output = await self.current_agent.formatter.format_output(output)

            if output:
                console_panel.write_string(output)

        except cmd2.Cmd2ArgparseError:
            sys.stderr = old_stderr
            error_message = stderr_capture.getvalue().strip()
            if error_message and console_panel:
                console_panel.write_string(error_message)

            sys.stdout = old_stdout
            stdout = stdout_capture.getvalue().strip()
            if stdout and console_panel:
                console_panel.write_string(stdout)

        except WorkerFailed as worker_error:
            if isinstance(worker_error.error, TaskError):
                if console_panel:
                    console_panel.write_string(f"Task Failed: {worker_error.error}")
            logger.exception(worker_error.error)
        except FormatterNotAvailable as e:
            if console_panel:
                console_panel.write_string(Text(e))
            logger.error(e)
        except EmptyStatement:
            pass
        except Exception as e:
            if console_panel:
                console_panel.write_string(f"Unhandled exception: {e}")
            logger.exception(e)
        finally:
            if prompt:
                prompt.disabled = False
                prompt.focus()

    @classmethod
    def _show_help(cls, console_panel: ConsolePanel, current_agent: Optional[MythicAgent] = None):
        command_table = Table()
        command_table.add_column("Command")
        command_table.add_column("Description", overflow="fold")

        alias_table = Table()
        alias_table.add_column("Alias")
        alias_table.add_column("Target")
        alias_table.add_column("Description", overflow="fold")

        if current_agent:
            command_table.title = f"{current_agent.name.capitalize()} Commands"
            for command in current_agent.commands:
                command_table.add_row(command.name, command.description)

            console_panel.write_string(command_table)

            alias_table.title = f"{current_agent.name.capitalize()} Aliases"
            for alias in sorted(current_agent.aliases, key=lambda a: a.name):
                target = f"{alias.command} {alias.subcommand}"
                if alias.options_prefix:
                    target += f" {alias.options_prefix}"
                alias_table.add_row(alias.name, target, alias.description)

            console_panel.write_string("\n")
            console_panel.write_string(alias_table)
            return

        command_table.title = "Mythic Commands"
        command_table.add_row("operation", "View, change, and create operations")
        command_table.add_row("payload", "Create, download, show payloads")
        command_table.add_row("user", "View/modify operators/spectators")
        console_panel.write_string(command_table)

    @on(TasksTable.NewTask)
    def _new_task(self, message: TasksTable.NewTask) -> None:
        """
        A new task was received from Mythic. This function will handle adding that task to the Tasks widget
        :param message: NewTask message
        """
        task = message.task
        message.stop()
        if not self.current_callback:
            return

        if task.callback_uuid == self.current_callback.uuid:
            task_table = self.query_one("#tasks_table", DataTable)
            try:
                task_table.add_row(task.id, task.username, task.status, task.command_name, task.params,
                                   key=task.uuid)
            except DuplicateKey:
                pass

    @on(CallbackTable.RowUpdated)
    async def _row_updated(self, message: CallbackTable.RowUpdated):
        # TODO: do we need this? UpdateCurrentCallback is also being called after this...
        logger.debug("updating callback because row updated")
        uuid = message.callback_uuid

        if self.current_callback:
            if uuid == self.current_callback.uuid:
                return

        callback = self.active_callbacks.get(uuid)
        if not callback:
            callback = Callback(self.instance, callback_uuid=uuid)
            worker = self.run_worker(callback.query())
            await worker.wait()
            self.active_callbacks[uuid] = callback

        self.current_callback = callback

        if callback.uuid in self.displayed_tabs.keys():
            self.query_one(TabbedContent).active = f"callback-{callback.uuid}"
            return

        title = f"Callback {callback.display_id}"
        new_tab = TabPane(title, callback.console_panel, id=f"callback-{callback.uuid}")
        self.displayed_tabs[callback.uuid] = new_tab
        await self.query_one(TabbedContent).add_pane(self.displayed_tabs[callback.uuid])
        self.query_one(TabbedContent).active = f"callback-{callback.uuid}"

    @on(UpdateCurrentCallback)
    async def update_current_callback(self, message: UpdateCurrentCallback):
        callback_uuid = message.callback_uuid
        if not callback_uuid:
            self.current_tab_id = None
            self.current_callback = None
            self.cmd.load_mythic_commands()
            return

        logger.debug(f"update current callback: {callback_uuid}")
        callback = self.active_callbacks.get(callback_uuid)
        if not callback:
            logger.debug("new callback")
            callback = Callback(self.instance, callback_uuid=callback_uuid)
            await callback.query()
            self.active_callbacks[callback_uuid] = callback

        tab_key = f"callback-{callback.uuid}"
        if callback_uuid in self.active_callbacks.keys():
            self.query_one(TabbedContent).active = tab_key
        else:
            title = f"Callback {callback.display_id}"
            new_tab = TabPane(title, ConsolePanel(), id=tab_key)
            self.displayed_tabs[callback.uuid] = new_tab
            await self.query_one(TabbedContent).add_pane(self.displayed_tabs[callback.uuid])
            self.query_one(TabbedContent).active = tab_key

        self.current_callback = callback
        agent = get_agent(self.instance, callback.payload_type_name)
        self.current_agent = agent
        self.current_agent.tasker.set_callback(self.current_callback)
        self.cmd.current_agent = self.current_agent
        self.cmd.load_and_register_agent_commands()

    @on(TabbedContent.TabActivated)
    def update_selected_callback(self, event: TabbedContent.TabActivated) -> None:
        """
        When a new tab is activated, switch the view mode to update the sidebar depending on what type of tab it is.
        If the tab is the home tab, callbacks table is updated to not display the cursor.

        :param event: instance `TabActivated` class
        """
        tab_key = event.tab.id

        if "home" in tab_key:
            logger.debug(tab_key)
            self.query_one(Sidebar).view_mode = ViewMode.HOME
            self.query_one("#callback_table", DataTable).show_cursor = False
            # self.query_one(Input).focus()
            return

        row_key = tab_key.removeprefix("--content-tab-callback-")
        try:
            self.query_one("#callback_table", DataTable).show_cursor = True
            self.query_one(Callbacks).current_tab_id = row_key
            self.query_one(Sidebar).view_mode = ViewMode.CALLBACK
            self._populate_sidebar()
            # self.query_one(Input).focus()

        except Exception as e:
            logger.error(e)
            logger.debug(row_key)

    @on(ReplayTask)
    async def _replay_task_output(self, replay: ReplayTask):
        task = replay.task
        callback: Callback = self.current_callback
        current_agent = callback.console_panel.agent
        if current_agent.current_foreground_task:
            return

        output = await current_agent.formatter.format_output(task)
        callback.console_panel.write_string(
            f"\n--- Replay Task {task.display_id}: {task.command_name} {task.params or ''} ---\n")
        callback.console_panel.write_string(output)
        callback.console_panel.write_string("")

    def _populate_sidebar(self):
        logger.debug("populating sidebar tasks")
        self._populate_sidebar_tasks()

    @work()
    async def _populate_sidebar_tasks(self):
        task_table = self.query_one("#tasks_table", DataTable)
        task_table.loading = True
        task_table.clear()
        for t in self.current_callback.tasks:
            try:
                task_table.add_row(t.id, t.username, t.status, t.command_name, t.params, key=t.uuid)
            except DuplicateKey:
                continue
        task_table.loading = False

    def action_close_tab(self):
        self.query_one(CallbackTabs).close_tab()

    def action_previous_tab(self):
        self.query_one(CallbackTabs).previous_tab()

    def action_next_tab(self):
        self.query_one(CallbackTabs).next_tab()

    def action_shrink_sidebar(self):
        self.query_one(Sidebar).shrink()

    def action_grow_sidebar(self):
        self.query_one(Sidebar).grow()

    def action_background_current_task(self):
        callback: Callback = self.current_callback
        if not callback:
            return
        current_agent = callback.console_panel.agent
        if not current_agent:
            return
        worker = current_agent.current_foreground_task
        if not worker:
            return
        worker.cancel()
        logger.debug(f"command '{worker.name}' cancelled")
