from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import TabPane

from mythic_console.screens.home import Home
from mythic_console.widgets.calback_tabs import CallbackTabs
from mythic_console.widgets.console import ConsolePanel


class _TabFocusScreen(Screen):
    """Carries Home's real update_selected_callback handler, resolving the active tab's
    ConsolePanel through a real CallbackTabs with two callback tabs."""

    update_selected_callback = Home.update_selected_callback
    _focus_active_console_input = Home._focus_active_console_input
    _focus_callback_table = Home._focus_callback_table

    def __init__(self, instance):
        super().__init__()
        self._instance = instance

    def compose(self) -> ComposeResult:
        with CallbackTabs(self._instance):
            yield TabPane("one", ConsolePanel(instance=self._instance), id="callback-one")
            yield TabPane("two", ConsolePanel(instance=self._instance), id="callback-two")


class _Harness(App):
    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.tab_screen: _TabFocusScreen | None = None

    def on_mount(self) -> None:
        self.tab_screen = _TabFocusScreen(self._instance)
        self.push_screen(self.tab_screen)


async def test_tab_switch_restores_focus_to_console_input(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.tab_screen
        tabs = screen.query_one(CallbackTabs)

        start_pane = tabs.active_pane
        start_panel = start_pane.query_one(ConsolePanel)
        assert app.focused is start_panel.console_input

        inactive_pane = next(pane for pane in (tabs.get_pane("callback-one"), tabs.get_pane("callback-two"))
                              if pane is not start_pane)
        target_panel = inactive_pane.query_one(ConsolePanel)
        assert app.focused is not target_panel.console_input

        tabs.next_tab()
        await pilot.pause()

        assert tabs.active_pane is inactive_pane
        assert app.focused is target_panel.console_input
