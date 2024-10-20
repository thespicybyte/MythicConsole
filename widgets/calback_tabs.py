from rich.text import TextType
from textual import on
from textual.widgets import TabbedContent, Tabs

from backend import MythicInstance
from widgets.messages import NextTab, PreviousTab, CloseCurrentTab, TabClosed, UpdateCurrentCallback


class CallbackTabs(TabbedContent):
    close_pane = False

    def __init__(self, instance: MythicInstance, *titles: TextType):
        super().__init__(*titles)
        self.instance = instance

    @on(NextTab)
    def next_tab(self) -> None:
        self.query_one(Tabs).action_next_tab()

    @on(PreviousTab)
    def previous_tab(self) -> None:
        self.query_one(Tabs).action_previous_tab()

    @on(CloseCurrentTab)
    def close_tab(self) -> None:
        """
        Close tab unless it is the home tab
        """
        current_tab = self.active
        if current_tab == "home":
            return
        self.remove_pane(current_tab)
        self.post_message(TabClosed(current_tab))

    @on(TabbedContent.TabActivated)
    def tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """
        When a new table is activated, update the callback
        :param event: TabActivated event
        """
        tab_id = event.tab.id
        if "home" in tab_id:
            self.post_message(UpdateCurrentCallback(None))
            return

        if "callback" in tab_id:
            callback_uuid = tab_id.removeprefix("--content-tab-callback-")
            self.post_message(UpdateCurrentCallback(callback_uuid))
            return
